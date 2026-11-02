import uuid
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import signing
from integrations.models import SystemSettings, CRMCase, CaseAction, SyncJob, PlanningSnapshot
from planning.models import PersonalDashboard
from config.backup_bundles import export_bundle, restore_bundle, decode_bundle

@override_settings(SERVICE_LAN=True)
class SeparateBackupTests(TestCase):
    def setUp(self):
        self.admin=get_user_model().objects.create_user('admin',password='test',is_staff=True,is_superuser=True)
        self.user=get_user_model().objects.create_user('reader',password='secret')
        self.user.groups.add(Group.objects.create(name='service-readers'))
        self.setting=SystemSettings.objects.create(ai_model='original')
        self.case=CRMCase.objects.create(scope='scope',crm_id=uuid.uuid4(),evidence={'notes':[{'text':'CRM note'}]})
        self.action=CaseAction.objects.create(case=self.case,actor=self.user,title='Local followup',request_key=uuid.uuid4())
        self.dashboard=PersonalDashboard.objects.create(user=self.user,key='custom-test',configuration={'version':2},title='Original')
        self.job=SyncJob.objects.create(owner=self.admin,scope='scope',kind='sync',status='success')
        self.snapshot=PlanningSnapshot.objects.create(owner=self.admin,scope='scope',selection_key='view',job=self.job,source_name='Synthetic')
        self.snapshot.cases.add(self.case)

    def test_local_restores_users_actions_and_layout_without_crm_notes(self):
        token=export_bundle('local','key')
        records=decode_bundle(token,'key','local')
        self.assertNotIn('CRM note',str(records))
        self.assertNotIn('integrations.planningsnapshot',{r['model'] for r in records})
        self.user.set_password('changed');self.user.groups.clear();self.user.save()
        self.dashboard.title='Changed';self.dashboard.save()
        self.case.evidence={'notes':['new CRM data']};self.case.save()
        self.action.title='changed';self.action.save()
        restore_bundle(token,'key','local',self.admin)
        self.user.refresh_from_db();self.dashboard.refresh_from_db();self.case.refresh_from_db();self.action.refresh_from_db()
        self.assertTrue(self.user.check_password('secret'))
        self.assertTrue(self.user.groups.filter(name='service-readers').exists())
        self.assertEqual(self.dashboard.title,'Original');self.assertEqual(self.action.title,'Local followup')
        self.assertEqual(self.case.evidence,{'notes':['new CRM data']})

    def test_crm_only_latest_and_never_changes_local(self):
        second=SyncJob.objects.create(owner=self.admin,scope='scope',kind='sync',status='success')
        newer=PlanningSnapshot.objects.create(owner=self.admin,scope='scope',selection_key='view',job=second,source_name='Latest')
        newer.cases.add(self.case)
        token=export_bundle('crm','key');records=decode_bundle(token,'key','crm')
        models={r['model'] for r in records}
        self.assertNotIn('auth.user',models);self.assertNotIn('integrations.caseaction',models)
        self.assertEqual(sum(r['model']=='integrations.planningsnapshot' for r in records),1)
        self.action.title='Keep local';self.action.save()
        self.case.evidence={};self.case.save()
        restore_bundle(token,'key','crm',self.admin)
        self.case.refresh_from_db();self.action.refresh_from_db()
        self.assertIn('notes',self.case.evidence);self.assertEqual(self.action.title,'Keep local')

    def test_wrong_kind_tamper_and_active_sync_rejected(self):
        token=export_bundle('local','key')
        with self.assertRaises(ValueError):restore_bundle(token,'key','crm',self.admin)
        with self.assertRaises(signing.BadSignature):restore_bundle(token+'x','key','local',self.admin)
        SyncJob.objects.create(owner=self.admin,scope='scope',kind='sync',status='running')
        with self.assertRaises(ValueError):restore_bundle(token,'key','local',self.admin)

    def test_non_admin_forbidden(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.post('/settings/backups/',{'operation':'backup','kind':'local','directory':'C:/temp'}).status_code,403)

    def test_local_work_recovers_without_crm_cache(self):
        token=export_bundle('local','key')
        self.action.delete();self.case.delete()
        restore_bundle(token,'key','local',self.admin)
        action=CaseAction.objects.get(title='Local followup')
        self.assertEqual(action.case.crm_id,self.case.crm_id)
        self.assertEqual(action.case.evidence,{})

    def test_identity_collision_rolls_back(self):
        token=export_bundle('local','key')
        self.setting.ai_model='Keep';self.setting.save()
        self.user.username='other';self.user.save()
        with self.assertRaises(ValueError):restore_bundle(token,'key','local',self.admin)
        self.setting.refresh_from_db();self.assertEqual(self.setting.ai_model,'Keep')
