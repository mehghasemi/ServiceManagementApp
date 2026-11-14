import json
import uuid
from copy import deepcopy
from types import SimpleNamespace
from django.test import SimpleTestCase, TestCase, override_settings
from django.contrib.auth import get_user_model
from integrations.models import EvaluationRule, SettingsAudit, CRMCase, CRMView, PlanningSnapshot, SyncJob
from integrations.jobs import module_settings, selection_key
from .engine import ensure_rules, matches
from .expressions import validate, evaluate


def leaf(metric='source_status', operator='in', value=None):
    return dict(metric=metric,operator=operator,value=['Planned'] if value is None else value)

def tree(join='all',children=None):
    return {'version':1,'root':{'join':join,'children':children or [leaf(),leaf('note_age','gt',30)]}}

class ExpressionTests(SimpleTestCase):
    def test_three_valued_logic(self):
        cases=[({'source_status':'Planned','note_age':31},True,True),({'source_status':'Other','note_age':None},False,None),({'source_status':'Planned','note_age':None},None,True),({'source_status':'Other','note_age':1},False,False)]
        for facts,and_result,or_result in cases:
            self.assertIs(evaluate(tree(),facts,'planning'),and_result)
            self.assertIs(evaluate(tree('any'),facts,'planning'),or_result)
    def test_nested_and_invalid_structures(self):
        doc=tree(children=[leaf(),{'join':'any','children':[leaf('note_age','gt',30),leaf('has_parent','eq',False)]}])
        self.assertTrue(evaluate(doc,{'source_status':'Planned','note_age':1,'has_parent':False},'planning'))
        for bad in [tree(children=[leaf('unknown')]),tree(children=[leaf('note_age','contains_any',['1'])]),tree(children=[leaf('note_age','gt',True)]),tree(children=[{'join':'all','children':[]}]),tree(children=[leaf()]*21)]:
            with self.assertRaises(ValueError): validate(bad,'planning')
        with self.assertRaises(ValueError): validate(tree(),'backlogs')
        for _ in range(5): doc=tree(children=[doc['root']])
        with self.assertRaises(ValueError): validate(doc,'planning')
    def test_active_scope_and_temporal_unknown(self):
        rule=SimpleNamespace(enabled=True,active_only=True,metric='expression',settings=SimpleNamespace(module='planning'),value=tree())
        self.assertFalse(matches(rule,{'active':False,'source_status':'Planned','note_age':60}))
        self.assertIsNone(matches(rule,{'source_status':'Planned','note_age':60}))
        config=dict(version=1,days=3,calendar='working',weekends=[4],holidays=['۱۴۰۵/۰۱/۰۱'],statuses=[],responses=['staff_note'])
        doc=tree(children=[leaf('customer_wait','gt',config)])
        self.assertIsNone(evaluate(doc,{},'planning'))
        self.assertEqual(doc['root']['children'][0]['value']['holidays'],['2026-03-21'])

@override_settings(SERVICE_LAN=False)
class ExpressionPersistenceTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('expression-admin',is_staff=True)
        self.client.force_login(self.user)
        self.options=module_settings()
        self.options.case_view=CRMView.objects.create(scope=self.options.scope,entity='incident',kind='userqueries',crm_id=uuid.uuid4(),name='Synthetic expression View')
        self.options.save(); ensure_rules(self.options)
        self.data=dict(label='معیار ترکیبی آزمایشی',enabled='on',purpose='attention',metric='expression',operator='eq',expression_data=json.dumps(tree(children=[leaf()])),priority=2,active_only='on',grouping='customer',min_count=2,confirm='on',revision=0,request_key=str(uuid.uuid4()))
        for user,status in [(self.user,'Planned'),(get_user_model().objects.create_user('other'), 'Planned')]:
            job=SyncJob.objects.create(owner=user,scope=self.options.scope,kind='sync',status='success')
            snap=PlanningSnapshot.objects.create(owner=user,scope=self.options.scope,selection_key=selection_key(self.options),job=job)
            case=CRMCase.objects.create(scope=self.options.scope,crm_id=uuid.uuid4(),number=str(user.pk),source_status=status,evidence={'state':0})
            from django.utils import timezone
            snap.fetched_at=timezone.now();snap.save(update_fields=['fetched_at'])
            snap.cases.add(case)
    def test_preview_no_save_and_scoped_then_persist(self):
        before=(EvaluationRule.objects.count(),SettingsAudit.objects.count())
        response=self.client.post('/planning/criteria/new/',{**self.data,'intent':'preview','confirm':''})
        self.assertEqual(response.status_code,200)
        self.assertEqual(response.context['preview']['total'],1)
        self.assertEqual(response.context['preview']['matched'],1)
        self.assertEqual(before,(EvaluationRule.objects.count(),SettingsAudit.objects.count()))
        self.assertEqual(self.client.post('/planning/criteria/new/',self.data).status_code,302)
        rule=EvaluationRule.objects.get(label=self.data['label'])
        edit=self.client.get(f'/planning/criteria/{rule.pk}/')
        self.assertEqual(json.loads(edit.context['form'].initial['expression_data']),rule.value)
        self.assertContains(edit,'criteria-builder.js')
        stale={**self.data,'revision':0}
        self.assertEqual(self.client.post(f'/planning/criteria/{rule.pk}/',stale).status_code,409)
        self.assertEqual(self.client.post('/planning/criteria/new/',self.data).status_code,302)
        self.assertEqual(EvaluationRule.objects.filter(label=self.data['label']).count(),1)
    def test_invalid_expression_and_permission(self):
        bad={**self.data,'expression_data':json.dumps(tree(children=[leaf('arbitrary_field')]))}
        response=self.client.post('/planning/criteria/new/',bad)
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.context['form'].errors)
        self.assertFalse(EvaluationRule.objects.filter(label=self.data['label']).exists())
        self.client.force_login(get_user_model().objects.get(username='other'))
        self.assertIn(self.client.post('/planning/criteria/new/',{**self.data,'intent':'preview'}).status_code,[302,403])
