import uuid
from unittest.mock import patch
from django.test import TestCase, SimpleTestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from .models import CRMView, CRMCase, PlanningSnapshot, CaseAction, SyncJob, ActionAudit
from .jobs import configuration, module_settings, start_job, run_job
from .client import Client, CRMError, validate_connection
from .analysis import normalize

CASE_ID = '11111111-1111-1111-1111-111111111111'
VIEW_ID = '22222222-2222-2222-2222-222222222222'
XML = '<fetch><entity name="incident"><attribute name="incidentid"/><filter><condition attribute="statecode" operator="eq" value="0"/></filter></entity></fetch>'
ROWS = [{'incidentid': CASE_ID, 'title': 'کیس ساختگی', 'ticketnumber': 'TEST-01', 'statuscode': 1, 'statecode': 0}]

class IntegrationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('operator', is_staff=True)
        self.client.force_login(self.user)
        self.config = configuration()
        view = CRMView.objects.create(scope=self.config.scope, kind='userqueries', crm_id=VIEW_ID, name='ویوی تست', entity='incident')
        self.options = module_settings()
        self.options.case_view = view
        self.options.save()

    def sync(self, rows=None):
        job = start_job(self.user, 'sync', launch=False)
        with patch('integrations.jobs.Client.fetch_view', return_value=(ROWS if rows is None else rows, XML, 'ویوی تست')):
            run_job(job.pk)
        job.refresh_from_db()
        return job

    def test_full_sync_preserves_local_actions_and_is_unique(self):
        self.assertEqual(self.sync().status, 'success')
        case = CRMCase.objects.get()
        action = CaseAction.objects.create(case=case, actor=self.user, title='اقدام', responsible='نمونه', due_date=timezone.localdate(), request_key=uuid.uuid4())
        self.sync()
        self.assertEqual(CRMCase.objects.count(), 1)
        action.refresh_from_db()
        self.assertEqual(action.title, 'اقدام')
        self.assertEqual(PlanningSnapshot.objects.count(), 2)

    def test_failed_sync_does_not_publish_partial_snapshot(self):
        self.sync()
        job = start_job(self.user, 'sync', launch=False)
        with patch('integrations.jobs.Client.fetch_view', side_effect=CRMError('خطای شبکه ساختگی')):
            run_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(PlanningSnapshot.objects.count(), 1)
        self.assertEqual(CRMCase.objects.count(), 1)

    def test_cancel_before_publish_keeps_previous_snapshot(self):
        self.sync()
        job = start_job(self.user, 'sync', launch=False)
        SyncJob.objects.filter(pk=job.pk).update(cancel_requested=True)
        with patch('integrations.jobs.Client.fetch_view', return_value=([], XML, 'ویوی تست')):
            run_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'cancelled')
        self.assertEqual(PlanningSnapshot.objects.count(), 1)

    def test_view_absence_does_not_delete_actions(self):
        self.sync()
        case = CRMCase.objects.get()
        CaseAction.objects.create(case=case, actor=self.user, title='اقدام', responsible='نمونه', due_date=timezone.localdate(), request_key=uuid.uuid4())
        self.sync([])
        self.assertEqual(CRMCase.objects.count(), 1)
        self.assertEqual(CaseAction.objects.count(), 1)
        self.assertEqual(self.client.get(f'/planning/cases/{case.pk}/').status_code, 404)
        self.assertContains(self.client.get('/planning/actions/'), 'خارج از View فعلی')

    def test_settings_locked_during_job(self):
        start_job(self.user, 'sync', launch=False)
        payload = dict(base_url='https://crm.baridsoft.ir', organization='Main', api_version='v9.1', request_timeout=30, ai_provider='', ai_model='', ai_key_env='SERVICE_AI_KEY', revision=1, confirm=True)
        response = self.client.post('/settings/', payload)
        self.assertEqual(response.status_code, 409)
        self.config.refresh_from_db()
        self.assertEqual(self.config.request_timeout, 60)

    def test_settings_and_case_pages_render(self):
        self.sync()
        for url in ('/', '/planning/', '/settings/', '/settings/planning/', '/planning/actions/', f'/planning/cases/{CRMCase.objects.get().pk}/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_chart_totals_and_empty_coverage(self):
        response = self.client.get('/planning/')
        self.assertIsNone(response.context['action_coverage'])
        self.assertEqual(response.context['chart_rows'], [])
        self.sync()
        response = self.client.get('/planning/')
        self.assertEqual(sum(row['count'] for row in response.context['chart_rows']), 1)
        self.assertEqual(response.context['chart_rows'][0]['percent'], 100)
        self.assertEqual(response.context['action_coverage'], 0)

    def test_home_lists_modules_without_fake_project_routes(self):
        response = self.client.get('/')
        self.assertContains(response, 'داشبورد')
        self.assertContains(response, 'مدیریت پروژه‌ها')
        self.assertContains(response, 'هنوز پیاده‌سازی نشده است')
        self.assertNotContains(response, 'href="/projects/"')

    def test_switching_views_never_presents_mixed_snapshot(self):
        self.sync()
        old_view = self.options.case_view
        new_view = CRMView.objects.create(scope=self.config.scope, kind='savedqueries', crm_id=uuid.uuid4(), name='نمای دوم', entity='incident')
        self.options.case_view = new_view
        self.options.save()
        self.sync()
        self.options.case_view = old_view
        self.options.save()
        from .views import active_snapshot
        self.assertIsNone(active_snapshot(self.user))

    def test_action_creation_retry_and_completion(self):
        self.sync()
        case = CRMCase.objects.get()
        payload = dict(title='هماهنگی', responsible='نمونه', due_date=str(timezone.localdate()), blocker='', request_key=str(uuid.uuid4()), confirm=True)
        for _ in range(2):
            self.assertEqual(self.client.post(f'/planning/cases/{case.pk}/actions/new/', payload).status_code, 302)
        self.assertEqual(CaseAction.objects.count(), 1)
        action = CaseAction.objects.get()
        result = dict(result='هماهنگی انجام شد', revision=1, confirm=True)
        for _ in range(2):
            self.assertEqual(self.client.post(f'/planning/actions/{action.pk}/complete/', result).status_code, 302)
        self.assertEqual(ActionAudit.objects.count(), 2)
        case.refresh_from_db()
        self.assertEqual(case.source_status, '1')

    def test_nonstaff_and_other_operator_cannot_read_data(self):
        self.sync()
        case = CRMCase.objects.get()
        other = get_user_model().objects.create_user('another', is_staff=False)
        self.client.force_login(other)
        self.assertEqual(self.client.get('/settings/').status_code, 403)
        other.is_staff = True
        other.save()
        self.assertEqual(self.client.get(f'/planning/cases/{case.pk}/').status_code, 404)

class TransportTests(SimpleTestCase):
    def test_unapproved_hosts_and_path_injection_rejected(self):
        for url in ('https://evil.example', 'http://crm.baridsoft.ir', 'https://crm.baridsoft.ir@evil.example', 'https://crm.baridsoft.ir/x'):
            with self.assertRaises(CRMError):
                validate_connection(url, 'Main', 'v9.1')
        with self.assertRaises(CRMError):
            validate_connection('https://crm.baridsoft.ir', '../admin', 'v9.1')

    def test_external_nextlink_is_rejected_before_transport(self):
        client = Client(dict(base_url='https://crm.baridsoft.ir', organization='Main', api_version='v9.1'))
        with patch('integrations.client.subprocess.run') as runner:
            with self.assertRaises(CRMError):
                client.get('https://evil.example/steal')
            runner.assert_not_called()

    def test_fetchxml_paging_preserves_view_filters(self):
        client = Client(dict(base_url='https://crm.baridsoft.ir', organization='Main', api_version='v9.1'))
        with patch.object(client, 'get', side_effect=[{'name': 'نمونه', 'fetchxml': XML}, {'value': ROWS, '@odata.nextLink': client.root+'/incidents?next=2'}, {'value': []}]) as get, patch.object(client, 'paged', return_value=[{'LogicalName':'incidentid'}]):
            rows, _, _ = client.fetch_view(dict(kind='userqueries', crm_id=VIEW_ID, entity='incident', name='نمونه'))
        from urllib.parse import unquote
        self.assertIn('attribute="statecode"', unquote(get.call_args_list[1].args[0]))
        self.assertEqual(len(rows), 1)

    def test_duplicate_case_rows_deduplicated_without_title_grouping(self):
        records = normalize(ROWS + ROWS, XML)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]['parent_id'], '')


class RecommendationTests(TestCase):
    def test_priority_scope_and_actor_isolation(self):
        from datetime import timedelta
        from planning.recommendations import recommendations
        user = get_user_model().objects.create_user('suggestion-owner')
        other = get_user_model().objects.create_user('suggestion-other')
        today = timezone.localdate()
        cases = [CRMCase.objects.create(scope='test', crm_id=uuid.uuid4(), number=str(i), parent_id='parent') for i in range(4)]
        def action(case, actor, days, **extra):
            return CaseAction.objects.create(case=case, actor=actor, title='synthetic', responsible='test', due_date=today + timedelta(days=days), request_key=uuid.uuid4(), **extra)
        action(cases[0], user, -2)
        action(cases[1], user, 1, blocker='synthetic blocker')
        action(cases[2], other, -20)
        action(cases[3], user, -30)
        rows = recommendations(CRMCase.objects.filter(pk__in=[c.pk for c in cases[:3]]), user, [], today)
        self.assertEqual([r['priority'] for r in rows], [1, 2, 5])
        self.assertEqual([r['case'].pk for r in rows], [c.pk for c in cases[:3]])
        self.assertTrue(all(r['reason'] and r['impact'] for r in rows))

    def test_empty_and_completed_actions(self):
        from planning.recommendations import recommendations
        user = get_user_model().objects.create_user('empty-owner')
        today = timezone.localdate()
        self.assertEqual(recommendations(CRMCase.objects.none(), user, [], today), [])
        case = CRMCase.objects.create(scope='test', crm_id=uuid.uuid4(), parent_id='p')
        CaseAction.objects.create(case=case, actor=user, title='synthetic', responsible='test', due_date=today, status='done', blocker='old blocker', request_key=uuid.uuid4())
        rows = recommendations(CRMCase.objects.all(), user, [], today)
        self.assertEqual(rows[0]['priority'], 5)
