import uuid
from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import DatabaseError
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
from .models import Program, Case, AuditEvent, FollowUp
from .forms import ProgramForm
from .services import save_program, record_followup, Conflict

class PlanningTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('tester')
        self.other = get_user_model().objects.create_user('other')
        self.client.force_login(self.user)
        self.data = dict(customer='مشتری نمونه', title='آزمون برنامه', owner='کارشناس نمونه', status='ready', next_step='هماهنگی جلسه', due_date=timezone.localdate(), blocker='', notes='', revision=0, request_id=uuid.uuid4(), confirm=True)
        self.program = save_program(self.user, self.data)

    def payload(self, **changes):
        return {**self.data, 'revision': self.program.revision, 'request_id': uuid.uuid4(), **changes}

    def test_duplicate_create_is_idempotent(self):
        again = save_program(self.user, self.data)
        self.assertEqual(again.pk, self.program.pk)
        self.assertEqual(Program.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)

    def test_reused_key_with_changed_payload_rejected(self):
        with self.assertRaises(Conflict):
            save_program(self.user, {**self.data, 'title': 'متفاوت'})

    def test_stale_edit_does_not_overwrite(self):
        save_program(self.user, self.payload(title='نسخه جدید'), self.program.pk)
        with self.assertRaises(Conflict):
            save_program(self.user, self.payload(title='نسخه قدیمی'), self.program.pk)
        self.program.refresh_from_db()
        self.assertEqual(self.program.title, 'نسخه جدید')
        self.assertEqual(AuditEvent.objects.count(), 2)

    def test_due_baseline_and_audit_preserved(self):
        original = self.program.due_date
        save_program(self.user, self.payload(due_date=original + timedelta(days=3)), self.program.pk)
        self.program.refresh_from_db()
        self.assertEqual(self.program.baseline_due, original)
        event = self.program.events.latest('id')
        self.assertEqual(event.before['due_date'], str(original))

    def test_followup_never_resolves_cases_and_retry_not_duplicated(self):
        case = Case.objects.create(program=self.program, code='DEMO-TEST', title='نمونه')
        data = dict(result='کار انجام شد', next_step='دریافت تأیید', due_date=timezone.localdate(), revision=1, request_id=uuid.uuid4(), confirm=True)
        record_followup(self.user, self.program.pk, data)
        record_followup(self.user, self.program.pk, data)
        self.assertEqual(FollowUp.objects.count(), 1)
        case.refresh_from_db()
        self.assertEqual(case.outcome, 'تأییدنشده')

    def test_cross_user_read_write_denied(self):
        self.client.force_login(self.other)
        for route in ('detail', 'edit', 'followup'):
            self.assertEqual(self.client.get(reverse(route, args=[self.program.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse('edit', args=[self.program.pk]), self.payload()).status_code, 404)

    def test_remote_demo_access_denied(self):
        self.assertEqual(self.client.get('/welcome/', REMOTE_ADDR='192.168.1.20').status_code, 403)

    def test_authentication_required(self):
        self.client.logout()
        self.assertEqual(self.client.get('/programs/').status_code, 302)

    def test_csrf_enforced(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)
        self.assertEqual(client.post(reverse('edit', args=[self.program.pk]), self.payload()).status_code, 403)

    def test_blocked_requires_blocker(self):
        form = ProgramForm(data=self.payload(status='blocked'))
        self.assertFalse(form.is_valid())
        self.assertIn('blocker', form.errors)

    def test_ready_requires_owner_and_date(self):
        form = ProgramForm(data=self.payload(owner='', due_date=''))
        self.assertFalse(form.is_valid())
        self.assertIn('owner', form.errors)
        self.assertIn('due_date', form.errors)

    def test_future_program_not_in_today_or_attention(self):
        save_program(self.user, self.payload(due_date=timezone.localdate()+timedelta(days=10)), self.program.pk)
        for route in ('today', 'decisions'):
            self.assertNotContains(self.client.get(reverse(route)), 'آزمون برنامه')

    def test_pages_render_and_escape_content(self):
        Program.objects.filter(pk=self.program.pk).update(title='<script>alert(1)</script>')
        for route in ('today', 'programs', 'decisions', 'versions'):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, 'lang="fa-IR" dir="rtl"')
            self.assertNotContains(response, '<script>alert(1)</script>')
        self.assertEqual(self.client.get(reverse('detail', args=[self.program.pk])).status_code, 200)

    def test_database_error_preserves_form_input(self):
        with patch('planning.views.save_program', side_effect=DatabaseError):
            response = self.client.post(reverse('edit', args=[self.program.pk]), self.payload(title='متن حفظ شود'))
        self.assertEqual(response.status_code, 503)
        self.assertContains(response, 'متن حفظ شود', status_code=503)

    def test_audit_failure_rolls_back_business_change(self):
        with patch('planning.services.AuditEvent.objects.create', side_effect=DatabaseError):
            with self.assertRaises(DatabaseError):
                save_program(self.user, self.payload(title='نباید ذخیره شود'), self.program.pk)
        self.program.refresh_from_db()
        self.assertEqual(self.program.title, 'آزمون برنامه')

    def test_explicit_confirmation_required(self):
        response = self.client.post(reverse('edit', args=[self.program.pk]), self.payload(confirm=''))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)

    def test_seed_does_not_reset_edits(self):
        from django.core.management import call_command
        call_command('seed_demo', verbosity=0)
        demo = Program.objects.filter(created_by__username='local-preview').first()
        Program.objects.filter(pk=demo.pk).update(title='تغییر محفوظ')
        call_command('seed_demo', verbosity=0)
        demo.refresh_from_db()
        self.assertEqual(demo.title, 'تغییر محفوظ')
