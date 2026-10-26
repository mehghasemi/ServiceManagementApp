import uuid
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from integrations.models import CRMCase, PlanningSnapshot, CaseAction, CRMView, EvaluationRule, SyncJob, ProjectSnapshot
from integrations.jobs import configuration,module_settings,selection_key

class TodayTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('today',is_staff=True)
        self.client.force_login(self.user)
        self.scope=configuration().scope
        self.opt=module_settings();self.opt.rules_initialized=True;self.opt.save()
        self.job=SyncJob.objects.create(owner=self.user,scope=self.scope,kind='sync',status='success',config={'module':'planning'})
        self.snapshot=PlanningSnapshot.objects.create(owner=self.user,scope=self.scope,selection_key=selection_key(self.opt),job=self.job,source_name='Synthetic',coverage={'notes':False})
        self.case=CRMCase.objects.create(scope=self.scope,crm_id=uuid.uuid4(),number='TEST',title='Synthetic',source_status='Open',evidence={'state':0,'created_on':timezone.now().isoformat()},fetched_at=self.snapshot.fetched_at)
        self.snapshot.cases.add(self.case)
    def action(self,case=None,days=0):
        return CaseAction.objects.create(case=case or self.case,actor=self.user,title='Follow up',due_date=timezone.localdate()+timedelta(days=days),request_key=uuid.uuid4())
    def test_unique_case_multiple_actions_and_reasons(self):
        self.action(days=-2);self.action()
        EvaluationRule.objects.create(settings=self.opt,code='test',label='Decision',metric='source_status',operator='in',value=['Open'],attention_group='decision')
        r=self.client.get('/planning/today/')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.context['counts']['due'],1)
        self.assertEqual(r.context['counts']['decision'],1)
        self.assertEqual(r.context['action_count'],2)
        self.assertEqual(r.context['page'].paginator.count,1)
        self.assertContains(r,'نمای اصلی')
    def test_future_null_and_outside_view_excluded(self):
        self.action(days=1)
        a=self.action();a.due_date=None;a.save()
        other=CRMCase.objects.create(scope=self.scope,crm_id=uuid.uuid4(),title='Hidden')
        self.action(other,-1)
        self.assertEqual(self.client.get('/planning/today/').context['counts']['due'],0)
    def test_preference_reversible_and_no_rule_changes(self):
        before=list(EvaluationRule.objects.values())
        self.assertEqual(self.client.post('/planning/view-preference/',{'view':'today'}).status_code,302)
        self.assertRedirects(self.client.get('/'),'/planning/today/')
        self.client.post('/planning/view-preference/',{'view':'classic'})
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertEqual(before,list(EvaluationRule.objects.values()))
    def test_filter_counts_all_planning_components(self):
        other=CRMCase.objects.create(scope=self.scope,crm_id=uuid.uuid4(),title='Other',source_status='Closed',fetched_at=self.snapshot.fetched_at)
        self.snapshot.cases.add(other)
        r=self.client.get('/planning/',{'q':'Synthetic','status':'Open'})
        self.assertEqual(r.context['total'],1)
        self.assertEqual(sum(x['count'] for x in r.context['chart_rows']),1)
        self.assertEqual(r.context['page'].paginator.count,1)
    def test_other_user_cannot_see_snapshot_or_queue(self):
        self.action(days=-1)
        other=get_user_model().objects.create_user('another',is_staff=True)
        self.client.force_login(other)
        r=self.client.get('/planning/today/')
        self.assertEqual(r.context['queue_total'],0)
        self.assertIsNone(r.context['snapshot'])
    def test_unknown_status_drilldown(self):
        self.case.source_status='';self.case.save()
        r=self.client.get('/planning/',{'status_missing':'1'})
        self.assertEqual(r.context['total'],1)
        self.assertContains(self.client.get('/planning/today/'),'status_missing=1')
    def test_project_query_filters_kpis_and_charts(self):
        from projects.services import normalize_projects
        opt=module_settings('projects')
        job=SyncJob.objects.create(owner=self.user,scope=self.scope,kind='sync',status='success',config={'module':'projects'})
        records=normalize_projects([{'brd_projectid':str(uuid.uuid4()),'brd_name':'Selected','statecode':0},{'brd_projectid':str(uuid.uuid4()),'brd_name':'Other','statecode':0}],[])
        ProjectSnapshot.objects.create(owner=self.user,scope=self.scope,selection_key=selection_key(opt),job=job,source_name='Synthetic',records=records,coverage={'notes':True})
        r=self.client.get('/projects/',{'q':'Selected'})
        self.assertEqual(r.context['total'],1)
        self.assertEqual(sum(x['count'] for x in r.context['phase_chart']),1)
        self.assertEqual(sum(x['count'] for x in r.context['chart_rows']),1)
        self.assertEqual(r.context['page'].paginator.count,1)
    def test_upgrade_eligible_filters_every_aggregate(self):
        self.case.customer_id=str(uuid.uuid4());self.case.customer='Selected';self.case.save()
        other=CRMCase.objects.create(scope=self.scope,crm_id=uuid.uuid4(),customer_id=str(uuid.uuid4()),customer='Other',source_status='Closed',fetched_at=self.snapshot.fetched_at)
        self.snapshot.cases.add(other)
        EvaluationRule.objects.create(settings=self.opt,code='upgrade',label='Synthetic rule',dashboard='upgrade',purpose='opportunity',metric='source_status',operator='in',value=['Open'],grouping='customer',min_count=1)
        r=self.client.get('/planning/upgrades/',{'eligible':'1'})
        self.assertEqual(r.context['total'],1)
        self.assertEqual(sum(x['count'] for x in r.context['version_chart']),1)
        self.assertEqual(r.context['page'].paginator.count,1)
