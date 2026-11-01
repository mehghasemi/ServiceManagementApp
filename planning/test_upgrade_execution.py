import uuid
from types import SimpleNamespace
from django.test import TestCase, SimpleTestCase
from django.contrib.auth import get_user_model
from integrations.jobs import configuration, module_settings, selection_key
from integrations.models import CRMCase, PlanningSnapshot, BacklogSnapshot, SyncJob, EvaluationRule
from criteria.engine import ensure_rules
from criteria.upgrade_defaults import READY, PROGRAM
from .upgrade_execution import execution_rows


class ExecutionTests(SimpleTestCase):
    def test_unique_cases_and_relationship_categories(self):
        ready = SimpleNamespace(enabled=True, **READY)
        program = SimpleNamespace(enabled=True, **PROGRAM)
        def case(pk, parent):
            return SimpleNamespace(pk=pk, parent_id=parent, customer_id='a', customer='Synthetic', parent_title='Plan')
        a, b, c, d = case(1, 'p'), case(2, None), case(3, 'missing'), case(4, 'other')
        facts = {'active': True, 'source_status': 'Done'}
        backlogs = [{'crm_id': 'p', 'evidence': {'case_service': PROGRAM['value'][0]}}, {'crm_id': 'other', 'evidence': {}}]
        rows = execution_rows([(r, facts) for r in [a, a, b, c, d]], backlogs, [ready], [program])
        self.assertEqual(sum(r['count'] for r in rows), 4)
        self.assertEqual({r['category'] for r in rows}, {'upgrade', 'unlinked', 'unreceived', 'other'})
        ready.enabled = False
        self.assertEqual(execution_rows([(a, facts)], backlogs, [ready], [program]), [])
        ready.enabled = True
        ready.value = ['Open']
        self.assertEqual(execution_rows([(a, facts)], backlogs, [ready], [program]), [])


class ExecutionRouteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('upgrade-operator', is_staff=True)
        self.client.force_login(self.user)
        scope = configuration().scope
        opt = module_settings(); ensure_rules(opt)
        job = SyncJob.objects.create(owner=self.user, scope=scope, kind='sync', status='success', config={'module': 'planning'})
        snapshot = PlanningSnapshot.objects.create(owner=self.user, scope=scope, selection_key=selection_key(opt), job=job, source_name='Synthetic')
        self.parents = [uuid.uuid4(), uuid.uuid4()]
        for index, parent in enumerate(self.parents):
            for number in range(index + 1):
                case = CRMCase.objects.create(scope=scope, crm_id=uuid.uuid4(), customer_id=uuid.uuid4(), customer='Synthetic', parent_id=parent,
                    source_status='Done', title='Synthetic case', number=f'T-{index}-{number}', evidence={'state': 0}, fetched_at=snapshot.fetched_at)
                snapshot.cases.add(case)
        opt = module_settings('backlogs'); ensure_rules(opt)
        job = SyncJob.objects.create(owner=self.user, scope=scope, kind='sync', status='success', config={'module': 'backlogs'})
        BacklogSnapshot.objects.create(owner=self.user, scope=scope, selection_key=selection_key(opt), job=job, source_name='Synthetic', records=[
            {'crm_id': str(parent), 'number': f'B-{index}', 'title': 'Upgrade', 'source_status': 'Submit',
             'evidence': {'case_service': PROGRAM['value'][0], 'release': f'M{index}'}} for index, parent in enumerate(self.parents)])

    def test_month_counts_chart_grid_and_program_drilldown_agree(self):
        response = self.client.get('/planning/upgrades/', {'release': 'M1'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['potential'], 2)
        self.assertEqual(response.context['linked'], 2)
        self.assertEqual(response.context['program_count'], 1)
        self.assertEqual(response.context['page'].paginator.count, 1)
        self.assertEqual(sum(r['count'] for r in response.context['top_programs']), 2)
        link = response.context['top_programs'][0]['url']
        self.assertIn('release=M1', link)
        detail = self.client.get('/planning/upgrades/' + link)
        self.assertEqual(detail.context['case_page'].paginator.count, 2)
        self.assertEqual({str(c.parent_id) for c in detail.context['case_page']}, {str(self.parents[1])})

    def test_scope_and_disabled_configuration(self):
        other = get_user_model().objects.create_user('other-operator', is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get('/planning/upgrades/').context['potential'], 0)
        self.client.force_login(self.user)
        EvaluationRule.objects.filter(purpose='upgrade_ready').update(enabled=False)
        response = self.client.get('/planning/upgrades/')
        self.assertEqual(response.context['potential'], 0)
        self.assertContains(response, 'فعال نیست')

    def test_customer_view_remains_available(self):
        self.assertEqual(self.client.get('/planning/upgrades/?view=customers').status_code, 200)
