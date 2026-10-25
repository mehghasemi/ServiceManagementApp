import uuid
from datetime import timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from integrations.jobs import configuration, module_settings, selection_key
from integrations.models import CRMView, SyncJob
from integrations.scheduler import reserve_due

class ScheduleTests(TestCase):
    def setUp(self):
        self.user=get_user_model().objects.create_user('scheduler',is_staff=True)
        self.system=configuration()
        self.opt=module_settings()
        self.opt.case_view=CRMView.objects.create(scope=self.system.scope,kind='savedqueries',crm_id=uuid.uuid4(),name='Synthetic',entity='incident')
        self.opt.save()
    def finish(self,pk,status='success',at=None):
        SyncJob.objects.filter(pk=pk).update(status=status,finished_at=at or timezone.now())
    def test_default_hour_and_duplicate_prevention(self):
        now=timezone.now()
        first=reserve_due(now)
        self.assertIsNotNone(first)
        self.assertIsNone(reserve_due(now))
        self.finish(first,at=now)
        self.assertIsNone(reserve_due(now+timedelta(minutes=59)))
        self.assertIsNotNone(reserve_due(now+timedelta(minutes=60)))
    def test_override_and_disable(self):
        self.opt.auto_sync_minutes=240;self.opt.save()
        now=timezone.now();first=reserve_due(now);self.finish(first,'failed',now)
        self.assertIsNone(reserve_due(now+timedelta(hours=2)))
        self.system.auto_sync_enabled=False;self.system.save()
        self.assertIsNone(reserve_due(now+timedelta(hours=8)))
    def test_missing_view_does_not_start(self):
        self.opt.case_view=None;self.opt.save()
        self.assertIsNone(reserve_due())
    def test_current_source_only(self):
        self.opt.scope='other';self.opt.save()
        self.assertIsNone(reserve_due())
    def test_module_off(self):
        self.opt.auto_sync_enabled=False;self.opt.save()
        self.assertIsNone(reserve_due())
    def test_header_and_global_tabs(self):
        self.client.force_login(self.user)
        response=self.client.get('/settings/')
        self.assertContains(response,'پشتیبان‌گیری و بازیابی')
        self.assertNotContains(response,'href="/settings/planning/"')
        response=self.client.get('/projects/settings/')
        self.assertContains(response,'/projects/jobs/sync/',status_code=200)


    def test_schedule_saved_and_invalid_interval_rejected(self):
        self.client.force_login(self.user)
        payload={'auto_sync_enabled':'on','auto_sync_minutes':120,'base_url':self.system.base_url,'organization':self.system.organization,'api_version':self.system.api_version,'request_timeout':60,'ai_key_env':'SERVICE_AI_KEY','revision':1,'confirm':'on'}
        self.assertEqual(self.client.post('/settings/',payload).status_code,302)
        self.system.refresh_from_db();self.assertEqual(self.system.auto_sync_minutes,120)
        payload.update(auto_sync_minutes=17,revision=self.system.revision)
        self.assertEqual(self.client.post('/settings/',payload).status_code,200)
        self.system.refresh_from_db();self.assertEqual(self.system.auto_sync_minutes,120)
