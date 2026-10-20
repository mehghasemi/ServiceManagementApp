from types import SimpleNamespace
from django.test import TestCase
from django.contrib.auth import get_user_model
from integrations.analysis import normalize, FORMAT
from integrations.jobs import module_settings
from criteria.engine import ensure_rules
from planning.backlogs import visit_data


class VisitDashboardTests(TestCase):
    def test_onsite_uses_ticket_status_and_keeps_single_unlinked_ticket(self):
        import uuid
        from unittest.mock import patch
        from integrations.models import CRMCase
        user = get_user_model().objects.create_user('onsite-reviewer', is_staff=True)
        self.client.force_login(user)
        case = CRMCase.objects.create(scope=module_settings().scope, crm_id=uuid.uuid4(),
            title='تیکت نمونه حضوری', customer='مرکز نمونه', customer_id=str(uuid.uuid4()),
            source_status='Checking in Presence Services', evidence={'state': 0})
        with patch('planning.upgrade_views.current_cases', return_value=CRMCase.objects.filter(pk=case.pk)):
            response = self.client.get('/planning/visits/onsite/')
            self.assertEqual(response.context['total'], 1)
            self.assertEqual(response.context['without_parent'], 1)
            self.assertContains(response, 'تیکت نمونه حضوری')
            rule = next(r for r in ensure_rules(module_settings()) if r.dashboard == 'onsite')
            rule.enabled = False
            rule.save()
            self.assertEqual(self.client.get('/planning/visits/onsite/').context['total'], 0)

    def test_normalize_planning_labels(self):
        row = normalize([{'incidentid': '11111111-1111-1111-1111-111111111111',
            '_brd_sprinttime_value': '22222222-2222-2222-2222-222222222222',
            '_brd_sprinttime_value'+FORMAT: 'هفته نمونه',
            '_brd_releasetime_value'+FORMAT: 'ماه نمونه'}], '<fetch><entity name="incident"/></fetch>')[0]
        self.assertEqual(row['evidence']['sprint'], 'هفته نمونه')
        self.assertEqual(row['evidence']['release'], 'ماه نمونه')

    def test_configurable_selection_and_missing_evidence(self):
        rule = SimpleNamespace(enabled=True, active_only=True, metric='case_service', operator='in', value=['دوره‌ای'])
        rows = [{'crm_id': 'a', 'source_status': 'Plan', 'evidence': {'case_service': 'دوره‌ای', 'state': 0}},
                {'crm_id': 'b', 'source_status': 'Plan', 'evidence': {'state': 0}}]
        result, unknown, _, _ = visit_data(rows, [rule], {'a': 3})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['ticket_count'], 3)
        self.assertEqual(unknown, 1)
        rule.value = ['دیگر']
        self.assertEqual(visit_data(rows, [rule], {})[0], [])
        rule.enabled = False
        self.assertEqual(visit_data(rows, [rule], {})[0], [])

    def test_dashboards_and_editable_rules(self):
        user = get_user_model().objects.create_user('visit-operator', is_staff=True)
        self.client.force_login(user)
        for path in ['/planning/visits/onsite/', '/planning/visits/periodic/', '/planning/backlogs/criteria/', '/planning/backlogs/criteria/new/']:
            self.assertEqual(self.client.get(path).status_code, 200)
        opt = module_settings('backlogs')
        rules = ensure_rules(opt)
        self.assertEqual({r.dashboard for r in rules}, {'onsite', 'periodic'})
        rule = rules[0]; rule.value = ['انتخاب کاربر']; rule.save()
        self.assertEqual(ensure_rules(opt)[0].value, ['انتخاب کاربر'])

    def test_upgrade_rules_do_not_offer_onsite(self):
        user = get_user_model().objects.create_user('upgrade-operator', is_staff=True)
        self.client.force_login(user)
        response = self.client.get('/planning/upgrades/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual([r.dashboard for r in response.context['rules']], ['upgrade'])
