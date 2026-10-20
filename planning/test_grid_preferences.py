from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, Client
from planning.models import GridPreference


class GridPreferenceTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('reader')
        self.user.groups.add(Group.objects.get_or_create(name='service-readers')[0])
        self.client.force_login(self.user)
        self.url = '/preferences/grids/backlogs/'
        self.columns = [{'id': 'customer', 'width': 240, 'visible': True},
                        {'id': 'title', 'width': 120, 'visible': False}]

    def save(self, columns):
        return self.client.post(self.url, {'columns': columns}, content_type='application/json')

    def test_reader_can_save_and_restore_order_width_visibility(self):
        self.assertEqual(self.save(self.columns).status_code, 200)
        self.assertEqual(self.client.get(self.url).json()['columns'], self.columns)

    def test_other_user_cannot_read_or_overwrite_layout(self):
        self.save(self.columns)
        other = get_user_model().objects.create_user('other', is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.client.get(self.url).json()['columns'], [])
        self.save([])
        self.assertEqual(GridPreference.objects.get(user=self.user).columns, self.columns)

    def test_invalid_settings_do_not_replace_saved_layout(self):
        self.save(self.columns)
        for columns in [None, {}, self.columns * 2,
                        [{'id': 'title', 'width': 40, 'visible': True}],
                        [{'id': 'title', 'width': 120, 'visible': False}],
                        [{'id': '<script>', 'width': 120, 'visible': True}]]:
            self.assertEqual(self.save(columns).status_code, 400)
        self.assertEqual(self.client.get(self.url).json()['columns'], self.columns)

    def test_auth_csrf_and_key_boundaries(self):
        self.assertEqual(self.client.get('/preferences/grids/unknown/').status_code, 404)
        csrf = Client(enforce_csrf_checks=True)
        csrf.force_login(self.user)
        self.assertEqual(csrf.post(self.url, {'columns': []}, content_type='application/json').status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_reset_and_malformed_json(self):
        self.save(self.columns)
        self.assertEqual(self.save([]).status_code, 200)
        self.assertEqual(self.client.post(self.url, '{', content_type='application/json').status_code, 400)
