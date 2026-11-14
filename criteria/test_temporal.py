from datetime import date
from types import SimpleNamespace
from django.test import SimpleTestCase
from .engine import matches
from .temporal import elapsed
from .forms import RuleForm
from integrations.models import EvaluationRule

class TemporalTests(SimpleTestCase):
    def setUp(self):
        self.config=dict(version=1, days=3, calendar='calendar', statuses=['Planned'], weekends=[4], holidays=[], responses=['staff_note'])
        self.rule=SimpleNamespace(enabled=True, active_only=True, metric='status_age', operator='gt', value=self.config)
        self.facts={'active':True,'source_status':'Planned','_today':date(2026,11,4),'_notes_loaded':True,'_evidence':{}}
    def test_verified_status_and_scope(self):
        self.assertIsNone(matches(self.rule,self.facts))
        self.facts['_evidence']['temporal']={'status_entry':{'status':'Planned','at':'2026-10-30','verified':True}}
        self.assertTrue(matches(self.rule,self.facts))
        self.facts['source_status']='Done'
        self.assertFalse(matches(self.rule,self.facts))
    def test_notes_coverage_and_future(self):
        self.rule.metric='note_silence'
        self.facts['_evidence']['notes']=[{'date':'2026-10-01'}]
        self.assertTrue(matches(self.rule,self.facts))
        self.facts['_notes_loaded']=False
        self.assertIsNone(matches(self.rule,self.facts))
        self.facts['_notes_loaded']=True
        self.facts['_evidence']['notes'].append({'date':'2027-01-01'})
        self.assertIsNone(matches(self.rule,self.facts))
    def test_pending_customer_reminders_do_not_reset_clock(self):
        self.rule.metric='customer_wait'
        stream={'coverage':{'customer_note':True,'staff_note':True},'events':[{'kind':'customer_note','at':'2026-10-20T10:00:00+03:30'},{'kind':'customer_note','at':'2026-11-04T09:00:00+03:30'}]}
        self.facts['_evidence']['temporal']=stream
        self.assertTrue(matches(self.rule,self.facts))
        stream['events'].append({'kind':'staff_note','at':'2026-11-04T10:00:00+03:30'})
        self.assertFalse(matches(self.rule,self.facts))
        stream['coverage']['staff_note']=False
        self.assertIsNone(matches(self.rule,self.facts))
    def test_working_days_holiday_and_threshold(self):
        self.config.update(calendar='working',holidays=['2026-11-01'])
        self.assertEqual(elapsed(date(2026,10,29),date(2026,11,4),self.config),4)
        self.assertIsNone(elapsed(date(2027,1,1),date(2026,11,4),self.config))
    def test_form_roundtrip_and_invalid_calendar(self):
        data=dict(label='نمونه',enabled='on',purpose='attention',metric='customer_wait',operator='gt',target_value='3',priority=2,active_only='on',grouping='customer',min_count=2,confirm='on',revision=0,request_key='12000000-0000-0000-0000-000000000001',time_statuses='Planned',time_calendar='working',time_weekends=['4'],time_holidays='۱۴۰۵/۰۱/۰۱',time_responses=['staff_note'])
        form=RuleForm(data,module='planning')
        self.assertTrue(form.is_valid(),form.errors)
        rule=form.save(commit=False);rule.pk=1
        loaded=RuleForm(instance=rule,module='planning')
        self.assertEqual(loaded.initial['target_value'],3)
        self.assertEqual(loaded.initial['time_holidays'],'1405/01/01')
        data['time_weekends']=[str(n) for n in range(7)]
        self.assertFalse(RuleForm(data,module='planning').is_valid())


from django.test import TestCase
from django.contrib.auth import get_user_model
from integrations.models import SettingsAudit

class TemporalPersistenceTests(TestCase):
    def test_saved_rule_roundtrip_and_audit(self):
        self.client.force_login(get_user_model().objects.create_user('temporal-admin', is_staff=True))
        data=dict(label='آزمون فاصله یادداشت', enabled='on', purpose='attention', metric='note_silence', operator='gt', target_value='30', priority=2, active_only='on', grouping='customer', min_count=2, confirm='on', revision=0, request_key='12000000-0000-0000-0000-000000000002', time_calendar='calendar', time_statuses='Planned')
        response=self.client.post('/planning/criteria/new/',data)
        self.assertEqual(response.status_code,302)
        rule=EvaluationRule.objects.get(code='12000000000000000000000000000002')
        self.assertEqual(rule.value['days'],30)
        self.assertEqual(rule.value['statuses'],['Planned'])
        self.assertTrue(SettingsAudit.objects.filter(area='planning:rule').exists())
        response=self.client.get(f'/planning/criteria/{rule.pk}/')
        self.assertEqual(response.status_code,200)
        self.assertContains(response,'criteria-temporal.js')
        self.assertEqual(response.context['form'].initial['target_value'],30)
