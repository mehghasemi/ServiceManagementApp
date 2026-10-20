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

    def test_notes_are_scoped_and_parent_notes_stay_separate(self):
        parent = '33333333-3333-3333-3333-333333333333'
        self.options.note_view = CRMView.objects.create(scope=self.config.scope, kind='savedqueries', crm_id=uuid.uuid4(), name='یادداشت ساختگی', entity='annotation')
        self.options.save()
        def fetch(view, related_ids=None):
            if view['entity'] == 'incident':
                return [dict(ROWS[0], _brd_plannedcase_value=parent)], XML, 'ویوی تست'
            self.assertEqual(set(related_ids), {CASE_ID, parent})
            return [{'annotationid': str(uuid.uuid4()), '_objectid_value': CASE_ID, 'subject': 'یادداشت کیس'}, {'annotationid': str(uuid.uuid4()), '_objectid_value': parent, 'subject': 'یادداشت برنامه'}], '', 'یادداشت'
        job = start_job(self.user, 'sync', launch=False)
        with patch('integrations.jobs.Client.fetch_view', side_effect=fetch):
            run_job(job.pk)
        job.refresh_from_db()
        self.assertEqual(job.status, 'success')
        case = CRMCase.objects.get()
        self.assertEqual(case.evidence['notes'][0]['title'], 'یادداشت کیس')
        self.assertEqual(case.evidence['parent_notes'][0]['title'], 'یادداشت برنامه')
        self.assertTrue(PlanningSnapshot.objects.get().coverage['notes'])

    def test_single_row_refresh_preserves_membership_and_actions(self):
        from .views import active_snapshot
        self.sync()
        case = CRMCase.objects.get()
        original_snapshot = active_snapshot(self.user)
        action = CaseAction.objects.create(case=case, actor=self.user, title='محلی', responsible='نمونه', due_date=timezone.localdate(), request_key=uuid.uuid4())
        job = start_job(self.user, 'row', launch=False, target=case.pk)
        def fetch(view, related_ids=None):
            self.assertEqual(related_ids, [CASE_ID])
            return [dict(ROWS[0], title='به‌روز')], XML, 'ویوی تست'
        with patch('integrations.jobs.Client.fetch_view', side_effect=fetch):
            run_job(job.pk)
        job.refresh_from_db(); case.refresh_from_db(); action.refresh_from_db()
        self.assertEqual(job.status, 'success')
        self.assertEqual(case.title, 'به‌روز')
        self.assertEqual(action.title, 'محلی')
        self.assertEqual(active_snapshot(self.user).pk, original_snapshot.pk)
        self.assertGreater(case.fetched_at, original_snapshot.fetched_at)

    def test_single_row_absent_from_view_preserves_old_data(self):
        self.sync(); case = CRMCase.objects.get(); stamp = case.fetched_at
        job = start_job(self.user, 'row', launch=False, target=case.pk)
        with patch('integrations.jobs.Client.fetch_view', return_value=([], XML, 'ویوی تست')):
            run_job(job.pk)
        job.refresh_from_db(); case.refresh_from_db()
        self.assertEqual(job.status, 'failed')
        self.assertEqual(case.fetched_at, stamp)

    def test_full_sync_json_keeps_user_on_dashboard(self):
        from types import SimpleNamespace
        with patch('integrations.views.start_job', return_value=SimpleNamespace(pk=456)):
            response=self.client.post('/crm/jobs/start/sync/',HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code,202)
        self.assertEqual(response.json()['url'],'/crm/jobs/456/?format=json')

    def test_row_refresh_json_stays_in_page(self):
        from types import SimpleNamespace
        with patch('integrations.views.start_job', return_value=SimpleNamespace(pk=123)):
            response = self.client.post('/planning/cases/1/refresh/', HTTP_ACCEPT='application/json')
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()['url'], '/crm/jobs/123/?format=json')

    def test_row_endpoint_rejects_outside_view_and_get(self):
        self.sync(); case = CRMCase.objects.get()
        self.assertEqual(self.client.get(f'/planning/cases/{case.pk}/refresh/').status_code, 405)
        self.assertEqual(self.client.post('/planning/cases/999999/refresh/').status_code, 404)

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

    def test_planning_job_history_excludes_projects_and_preserves_legacy(self):
        legacy = SyncJob.objects.create(owner=self.user, scope=self.scope if hasattr(self, 'scope') else self.config.scope, kind='test', status='success', config={})
        SyncJob.objects.create(owner=self.user, scope=self.config.scope, kind='test', status='success', config={'module': 'projects'})
        response = self.client.get('/planning/')
        self.assertEqual(response.context['last_job'].pk, legacy.pk)

    def test_home_lists_modules_without_fake_project_routes(self):
        response = self.client.get('/')
        self.assertContains(response, 'داشبورد')
        self.assertContains(response, 'مدیریت پروژه‌ها')
        self.assertContains(response, 'هنوز پیاده‌سازی نشده است')
        self.assertContains(response, 'href="/projects/"')

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
        payload = dict(title='هماهنگی', responsible='نمونه', due_date=__import__('config.dates',fromlist=['persian_date']).persian_date(timezone.localdate()), blocker='', request_key=str(uuid.uuid4()), confirm=True)
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
