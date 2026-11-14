import uuid
from copy import deepcopy
from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model
from integrations.jobs import configuration, module_settings, selection_key
from integrations.models import CRMCase, PlanningSnapshot, BacklogSnapshot, SyncJob
from planning.models import PersonalDashboard, DashboardPublication
from planning.reporting.engine import execute, validate_query
from planning.reporting.configuration import validate_configuration


class QueryEngineTests(SimpleTestCase):
    def setUp(self):
        self.rows = [{'id': '1', 'customer': 'A', 'city': 'X', 'notes_count': 2, 'created': '2024-04-01T00:00:00Z'},
                     {'id': '2', 'customer': 'A', 'city': 'Y', 'notes_count': 4, 'created': '2026-04-01T00:00:00Z'},
                     {'id': '3', 'customer': 'B', 'city': None, 'notes_count': None, 'created': None}]
        self.query = {'source': 'cases', 'dimensions': [], 'metric': {'aggregate': 'count'}}

    def test_all_aggregations_and_missing(self):
        for aggregate, expected in [('count', 3), ('sum', 6), ('average', 3), ('min', 2), ('max', 4), ('distinct_count', 2)]:
            query = {**self.query, 'metric': {'aggregate': aggregate, 'field': 'notes_count'}}
            self.assertEqual(execute(self.rows, query)['rows'][0]['value'], expected)
        query = {**self.query, 'metric': {'aggregate': 'average', 'field': 'notes_count'}, 'empty': 'zero'}
        self.assertEqual(execute(self.rows, query)['rows'][0]['value'], 2)

    def test_nested_filters_and_multi_dimensions(self):
        query = {**self.query, 'dimensions': [{'field': 'customer'}, {'field': 'city'}], 'filter': {'logic': 'and', 'children': [
            {'field': 'customer', 'op': 'eq', 'value': 'A'}, {'logic': 'or', 'children': [
                {'field': 'city', 'op': 'eq', 'value': 'X'}, {'field': 'notes_count', 'op': 'gt', 'value': 3}]}]}}
        result = execute(self.rows, query)
        self.assertEqual(result['record_count'], 2)
        self.assertEqual(sum(r['value'] for r in result['rows']), 2)
        group = result['rows'][0]['group']
        self.assertEqual(execute(self.rows, query, group=group)['detail_count'], 1)
        self.assertEqual(execute(self.rows, query, group='forged')['detail_count'], 0)

    def test_arbitrary_date_range_not_six_months(self):
        query = {**self.query, 'dimensions': [{'field': 'created', 'bucket': 'month'}], 'filter': {'field': 'created', 'op': 'between', 'value': ['1403/01/01', '1405/12/29']}}
        result = execute(self.rows, query)
        self.assertEqual(result['record_count'], 2)
        self.assertEqual({r['label'] for r in result['rows']}, {'1403/01', '1405/01'})

    def test_safe_formula_and_zero_division(self):
        query = {**self.query, 'metric': {'aggregate': 'sum', 'formula': {'left': {'field': 'notes_count'}, 'operator': '*', 'right': 2}}}
        self.assertEqual(execute(self.rows, query)['rows'][0]['value'], 12)
        with self.assertRaises(ValueError):
            validate_query({**query, 'metric': {**query['metric'], 'aggregate': 'count'}})
        query['metric']['formula'].update(operator='/', right=0)
        self.assertIsNone(execute(self.rows, query)['rows'][0]['value'])
        for bad in ['__import__("os")', {'field': '__dict__'}, float('inf')]:
            query['metric']['formula']['right'] = bad
            with self.assertRaises(ValueError): validate_query(query)

    def test_persian_date_boundaries_and_reversed_range(self):
        from planning.reporting.engine import day
        self.assertEqual(str(day('۱۴۰۵/۰۱/۰۱')), '2026-03-21')
        self.assertIsNone(day('1400/12/30'))
        self.assertIsNotNone(day('1399/12/30'))
        with self.assertRaises(ValueError):
            validate_query({**self.query, 'filter': {'field':'created', 'op':'between', 'value':['1405/02/01','1405/01/01']}})

    def test_widget_date_range_filters_chart_and_details(self):
        query={**self.query, 'date_range':{'field':'created','start':'1405/01/01','end':'1405/12/29'}}
        result=execute(self.rows,query)
        self.assertEqual(result['rows'][0]['value'],1)
        self.assertEqual(result['detail_count'],1)
        self.assertEqual(result['records'][0]['id'],'2')
        with self.assertRaises(ValueError):
            validate_query({**query,'date_range':{'field':'customer','start':'1405/01/01','end':'1405/12/29'}})

    def test_invalid_fields_and_complexity_rejected(self):
        for change in [{'source': 'users'}, {'dimensions': [{'field': 'password'}]}, {'filter': {'field': 'id', 'op': 'sql', 'value': 'x'}}]:
            with self.assertRaises(ValueError): validate_query({**self.query, **change})
        node = {'field': 'id', 'op': 'eq', 'value': 'x'}
        for _ in range(6): node = {'logic': 'and', 'children': [node]}
        with self.assertRaises(ValueError): validate_query({**self.query, 'filter': node})


class ReportingRoutesTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('report-admin', is_staff=True, is_superuser=True)
        self.client.force_login(self.user)
        scope = configuration().scope; opt = module_settings()
        job = SyncJob.objects.create(owner=self.user, scope=scope, kind='sync', status='success', config={'module': 'planning'})
        snapshot = PlanningSnapshot.objects.create(owner=self.user, scope=scope, selection_key=selection_key(opt), job=job, source_name='Synthetic', coverage={'notes': True})
        parent = uuid.uuid4()
        for city in ['A', 'B']:
            case = CRMCase.objects.create(scope=scope, crm_id=uuid.uuid4(), customer_id=str(uuid.uuid4()), customer='Customer '+city,
                title='Synthetic', parent_id=str(parent), source_status='Done', evidence={'city': city, 'notes': [], 'state': 0}, fetched_at=snapshot.fetched_at)
            snapshot.cases.add(case)
        opt = module_settings('backlogs'); job = SyncJob.objects.create(owner=self.user, scope=scope, kind='sync', status='success', config={'module': 'backlogs'})
        BacklogSnapshot.objects.create(owner=self.user, scope=scope, selection_key=selection_key(opt), job=job, source_name='Synthetic', records=[{'crm_id': str(parent), 'title': 'Program', 'evidence': {'case_service': 'Upgrade'}}])
        self.widget = {'id': 'w-one', 'source': 'dynamic', 'kind': 'bars', 'width': 6, 'height': 'normal', 'hidden': False,
            'title': 'Generic report', 'query': {'source': 'cases', 'dimensions': [{'field': 'backlog.service'}, {'field': 'city'}], 'metric': {'aggregate': 'count'}}}
        self.payload = {'widgets': [self.widget], 'configuration': {'version': 2, 'filters': []}}

    def post(self, path, data):
        return self.client.post(path, data, content_type='application/json')

    def test_preview_valid_relation_and_scope(self):
        response = self.post('/dashboards/data/preview/', self.payload)
        self.assertEqual(response.status_code, 200, response.content)
        result = response.json()['widgets'][0]
        self.assertEqual(result['record_count'], 2)
        self.assertEqual(sum(r['value'] for r in result['rows']), 2)
        self.assertEqual({r['dimensions'][0] for r in result['rows']}, {'Upgrade'})
        other = get_user_model().objects.create_user('report-other', is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.post('/dashboards/data/preview/', self.payload).json()['widgets'][0]['record_count'], 0)

    def test_cascading_options_and_target_filters(self):
        f = {'id': 'f-city', 'label': 'City', 'source': 'cases', 'field': 'city', 'op': 'eq', 'control': 'single', 'parents': [], 'targets': ['w-one']}
        self.payload['configuration']['filters'] = [f]
        self.payload['values'] = {'f-city': 'A'}
        self.assertEqual(self.post('/dashboards/data/preview/', self.payload).json()['widgets'][0]['record_count'], 1)
        response = self.post('/dashboards/data/options/', {'source': 'cases', 'field': 'customer', 'filters': [{'field': 'city', 'op': 'eq', 'value': 'A'}]})
        self.assertEqual(response.json()['options'], ['Customer A'])
        f['parents'] = ['f-city']
        self.assertEqual(self.post('/dashboards/data/preview/', self.payload).status_code, 400)

    def test_save_reload_copy_publish_and_delete_no_crm_changes(self):
        before = list(CRMCase.objects.values())
        dashboard = PersonalDashboard.objects.create(user=self.user, key='custom-report', title='Blank')
        data = {**self.payload, 'revision': 1, 'title': 'Generic'}
        response = self.post('/preferences/dashboards/custom-report/', data)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertContains(self.client.get('/dashboards/custom-report/'), 'report-designer')
        dashboard.refresh_from_db(); self.assertEqual(dashboard.widgets, data['widgets'])
        self.assertEqual(self.post('/preferences/dashboards/custom-report/', data).status_code, 409)
        self.assertEqual(self.post('/preferences/dashboards/custom-report/publish/', {'revision': 2, 'publication_revision': 0}).status_code, 200)
        self.assertEqual(DashboardPublication.objects.get().configuration['version'], 2)
        self.assertContains(self.client.get('/dashboards/shared/custom-report/'), 'report-designer')
        self.assertEqual(self.client.post('/dashboards/custom-report/manage/', {'action': 'copy'}).status_code, 302)
        self.assertEqual(PersonalDashboard.objects.count(), 2)
        self.assertEqual(self.client.post('/dashboards/custom-report/manage/', {'action': 'delete'}).status_code, 302)
        self.assertEqual(list(CRMCase.objects.values()), before)

    def test_metadata_and_authentication_and_forbidden_fields(self):
        metadata = self.client.get('/dashboards/data/metadata/').json()['sources']
        self.assertIn('backlog.service', metadata['cases']['fields'])
        self.assertNotIn('password', metadata['cases']['fields'])
        self.assertNotIn('province', metadata['cases']['fields'])
        self.widget['query']['dimensions'] = [{'field': '__dict__'}]
        self.assertEqual(self.post('/dashboards/data/preview/', self.payload).status_code, 400)
        self.client.logout()
        self.assertEqual(self.client.get('/dashboards/data/metadata/').status_code, 403)
        self.assertEqual(self.post('/dashboards/data/preview/', self.payload).status_code, 403)


    def test_empty_publication_rejected_and_owner_edit_link(self):
        draft = PersonalDashboard.objects.create(user=self.user, key='custom-empty', title='Empty', configuration={'version': 2})
        response = self.post('/preferences/dashboards/custom-empty/publish/', {'revision': 1, 'publication_revision': 0})
        self.assertEqual(response.status_code, 400)
        self.assertFalse(DashboardPublication.objects.filter(key=draft.key).exists())
        draft.widgets = [self.widget]; draft.save()
        self.assertEqual(self.post('/preferences/dashboards/custom-empty/publish/', {'revision': 1, 'publication_revision': 0}).status_code, 200)
        self.assertContains(self.client.get('/dashboards/shared/custom-empty/'), 'ویرایش نسخه اصلی داشبورد')
        other = get_user_model().objects.create_user('publication-viewer', is_staff=True)
        self.client.force_login(other)
        self.assertNotContains(self.client.get('/dashboards/shared/custom-empty/'), 'ویرایش نسخه اصلی داشبورد')
