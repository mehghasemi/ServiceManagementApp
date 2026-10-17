import uuid
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.utils import timezone
from integrations.models import CRMCase, CRMView, PlanningSnapshot, SyncJob, CaseAction, SettingsAudit
from integrations.jobs import module_settings, selection_key

@override_settings(SERVICE_LAN=True, SERVICE_LAN_SUBNETS=['172.16.5.0/24'])
class NetworkTests(TestCase):
    def setUp(self):
        cache.clear()
        self.manager = get_user_model().objects.create_user('manager', password='Synthetic-test-only-941!', is_staff=True, is_superuser=True)
        self.reader = get_user_model().objects.create_user('reader', password='Synthetic-test-only-942!')
        self.reader.groups.add(Group.objects.create(name='service-readers'))
        self.operator = get_user_model().objects.create_user('operator', is_staff=True)
        self.local = get_user_model().objects.create_user('local-preview', is_staff=True)
        options = module_settings()
        options.case_view = CRMView.objects.create(scope=options.scope, entity='incident', kind='userqueries', crm_id=uuid.uuid4(), name='Synthetic view')
        options.save()
        self.case = CRMCase.objects.create(scope=options.scope, crm_id=uuid.uuid4(), title='Synthetic shared case', evidence={'state':0})
        job = SyncJob.objects.create(owner=self.local, scope=options.scope, kind='sync', status='success')
        snapshot = PlanningSnapshot.objects.create(owner=self.local, scope=options.scope, selection_key=selection_key(options), job=job)
        snapshot.cases.add(self.case)
        CaseAction.objects.create(case=self.case, actor=self.local, title='Synthetic shared action', responsible='Test', due_date=timezone.localdate(), request_key=uuid.uuid4())

    def test_network_boundary_and_spoofed_forwarding(self):
        self.assertEqual(self.client.get('/welcome/', REMOTE_ADDR='172.16.5.30').status_code, 200)
        self.assertEqual(self.client.get('/welcome/', REMOTE_ADDR='172.16.6.30', HTTP_X_FORWARDED_FOR='172.16.5.30').status_code, 403)
        with override_settings(SERVICE_LAN=False):
            self.assertEqual(self.client.get('/welcome/', REMOTE_ADDR='172.16.5.30').status_code, 403)

    def test_no_passwordless_or_local_session_on_network(self):
        self.client.post('/welcome/', {})
        self.assertNotIn('_auth_user_id', self.client.session)
        self.client.force_login(self.local)
        self.assertRedirects(self.client.get('/planning/'), '/welcome/', fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_login_and_failed_attempt_limit(self):
        response = self.client.post('/welcome/', {'username':'reader', 'password':'Synthetic-test-only-942!'})
        self.assertEqual(response.status_code, 302)
        self.client.logout()
        for _ in range(10):
            self.client.post('/welcome/', {'username':'reader', 'password':'wrong'})
        self.assertEqual(self.client.post('/welcome/', {}).status_code, 429)

    def test_shared_data_with_source_view_scope_and_reader_permissions(self):
        self.client.force_login(self.reader)
        self.assertContains(self.client.get('/planning/'), 'Synthetic shared case')
        self.assertContains(self.client.get('/planning/actions/'), 'Synthetic shared action')
        self.assertEqual(self.client.post(f'/planning/cases/{self.case.pk}/actions/new/', {}).status_code, 403)
        self.assertEqual(self.client.get('/settings/').status_code, 403)
        foreign = CRMCase.objects.create(scope='other-source', crm_id=uuid.uuid4())
        self.assertEqual(self.client.get(f'/planning/cases/{foreign.pk}/').status_code, 404)
        options=module_settings(); options.case_view=None; options.save()
        self.assertNotContains(self.client.get('/planning/'), 'Synthetic shared case')

    def test_operator_and_manager_configuration_permissions(self):
        self.client.force_login(self.operator)
        for url in ['/settings/', '/settings/planning/', '/projects/settings/', '/planning/criteria/', '/planning/criteria/new/', '/network-users/']:
            self.assertEqual(self.client.get(url).status_code, 403, url)
        self.client.force_login(self.manager)
        self.assertEqual(self.client.get('/network-users/').status_code, 200)
        self.assertEqual(self.client.get('/settings/').status_code, 200)

    def test_account_creation_hashes_password_and_audits_role_only(self):
        self.client.force_login(self.manager)
        response=self.client.post('/network-users/', {'username':'new-reader', 'password1':'Synthetic-strong-376!', 'password2':'Synthetic-strong-376!', 'role':'reader', 'confirm':'on'})
        self.assertEqual(response.status_code, 302)
        user=get_user_model().objects.get(username='new-reader')
        self.assertTrue(user.check_password('Synthetic-strong-376!'))
        self.assertFalse(user.is_staff)
        self.assertEqual(SettingsAudit.objects.get(area='network-user').after['role'], 'reader')
        self.assertNotIn('password', str(SettingsAudit.objects.get(area='network-user').after))

    def test_legacy_routes_never_available_on_lan(self):
        self.client.force_login(self.manager)
        for url in ['/demo/today/', '/programs/', '/decisions/']:
            self.assertEqual(self.client.get(url).status_code,403)
