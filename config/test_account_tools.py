from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.core import signing
from integrations.models import SystemSettings, SettingsAudit
from config.backups import export_settings, restore_settings

@override_settings(SERVICE_LAN=True)
class AccountToolsTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_user('admin',password='1',is_staff=True,is_superuser=True)
        self.other=get_user_model().objects.create_user('other',password='2')
        self.client.force_login(self.admin)
    def test_admin_changes_role_and_short_password(self):
        response=self.client.post(f'/network-users/{self.other.pk}/',{'username':'other','role':'operator','is_active':'on','new_password':'3','confirm_password':'3'})
        self.assertEqual(response.status_code,302)
        self.other.refresh_from_db();self.assertTrue(self.other.is_staff);self.assertTrue(self.other.check_password('3'))
    def test_reader_cannot_edit(self):
        from django.contrib.auth.models import Group
        self.other.groups.add(Group.objects.get_or_create(name='service-readers')[0])
        self.client.force_login(self.other)
        self.assertEqual(self.client.get(f'/network-users/{self.admin.pk}/').status_code,403)
    def test_last_admin_cannot_deactivate_self(self):
        self.client.post(f'/network-users/{self.admin.pk}/',{'username':'admin','role':'reader'})
        self.admin.refresh_from_db();self.assertTrue(self.admin.is_superuser);self.assertTrue(self.admin.is_active)
    def test_change_requires_old_password(self):
        self.client.post('/account/password/',{'old_password':'wrong','new_password1':'4','new_password2':'4'})
        self.admin.refresh_from_db();self.assertTrue(self.admin.check_password('1'))
        self.client.post('/account/password/',{'old_password':'1','new_password1':'4','new_password2':'4'})
        self.admin.refresh_from_db();self.assertTrue(self.admin.check_password('4'))
    def test_settings_backup_roundtrip_and_tamper(self):
        setting=SystemSettings.objects.create(ai_model='old')
        token=export_settings('test-secret')
        setting.ai_model='new';setting.save()
        restore_settings(token,'test-secret',self.admin)
        setting.refresh_from_db();self.assertEqual(setting.ai_model,'old')
        with self.assertRaises(signing.BadSignature):restore_settings(token+'x','test-secret',self.admin)
        self.assertFalse('password' in token)

    def test_new_pages_render_for_admin(self):
        for url in ['/account/password/', f'/network-users/{self.other.pk}/', '/settings/backups/', '/planning/visits/periodic/']:
            self.assertEqual(self.client.get(url).status_code,200,url)
