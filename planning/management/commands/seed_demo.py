from datetime import timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from planning.models import Program, Case, AuditEvent

class Command(BaseCommand):
    help = 'Create synthetic demo data once; never resets user edits.'

    @transaction.atomic
    def handle(self, **options):
        user, created = get_user_model().objects.get_or_create(username='local-preview', defaults={'first_name': 'مدیر', 'last_name': 'نمونه'})
        if created:
            user.set_unusable_password()
            user.save()
        if Program.objects.filter(created_by=user).exists():
            self.stdout.write('Demo already exists; changes preserved.')
            return
        today = timezone.localdate()
        rows = [
            ('شرکت نمونه آفتاب', 'ارتقای نسخه و بررسی گردش مکاتبات', 'کارشناس نمونه اول', 'ready', 'تأیید نهایی زمان نصب با نماینده مشتری', 0, ''),
            ('مؤسسه نمونه سپیدار', 'آماده‌سازی دسترسی برای استقرار', 'کارشناس نمونه دوم', 'blocked', 'پیگیری دسترسی از مسئول فناوری مشتری', -2, 'دسترسی آزمایشی هنوز آماده نشده است.'),
            ('شرکت نمونه باران', 'کنترل نتیجه پس از نصب نسخه', 'کارشناس نمونه اول', 'verify', 'دریافت نتیجه آزمون سه کیس از مشتری', 0, ''),
            ('مجموعه نمونه سرو', 'برنامه‌ریزی آموزش کاربران', '', 'draft', '', None, 'زمان پیشنهادی مشتری هنوز مشخص نیست.'),
            ('شرکت نمونه آبان', 'بازبینی تنظیمات گردش تأیید', 'کارشناس نمونه دوم', 'active', 'اجرای سناریوی آزمایشی با نماینده مشتری', 1, ''),
            ('مؤسسه نمونه روشن', 'بررسی پیش‌نیازهای ارتقای سامانه', 'کارشناس نمونه اول', 'blocked', 'تأیید سازگاری نسخه با محیط آزمایشی', 3, 'نتیجه آزمون نسخه مورد نیاز است.'),
        ]
        for index, (customer, title, owner, status, step, offset, blocker) in enumerate(rows, 1):
            due = today + timedelta(days=offset) if offset is not None else None
            program = Program.objects.create(customer=customer, title=title, owner=owner, status=status, next_step=step, due_date=due, baseline_due=due, blocker=blocker, created_by=user, notes='این برنامه و تمام اطلاعات مرتبط ساختگی و صرفاً برای تجربه رابط کاربری هستند.')
            for number in range(1, 4):
                Case.objects.create(program=program, code=f'DEMO-{index:02}-{number:02}', title=['بررسی نمایش فهرست مکاتبات', 'کنترل دسترسی کاربران', 'آزمون گردش تأیید'][number - 1])
            AuditEvent.objects.create(program=program, actor=user, action='ایجاد داده نمونه', after={'source': 'synthetic'})
        self.stdout.write('Created 6 synthetic programs; no CRM connection.')
