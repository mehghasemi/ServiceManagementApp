import uuid
from django.conf import settings
from django.db import models
from django.utils import timezone


class Program(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'نیازمند تعیین تکلیف'
        READY = 'ready', 'آماده اجرا'
        BLOCKED = 'blocked', 'منتظر پیش‌نیاز'
        ACTIVE = 'active', 'در حال اجرا'
        VERIFY = 'verify', 'منتظر تأیید نتیجه'

    customer = models.CharField('مشتری', max_length=120)
    title = models.CharField('عنوان برنامه', max_length=180)
    owner = models.CharField('مسئول پیگیری', max_length=100, blank=True)
    status = models.CharField('وضعیت', max_length=20, choices=Status.choices, default=Status.DRAFT)
    next_step = models.CharField('اقدام بعدی', max_length=500, blank=True)
    due_date = models.DateField('موعد پیگیری', null=True, blank=True)
    baseline_due = models.DateField(null=True, blank=True)
    blocker = models.TextField('مانع یا پیش‌نیاز', blank=True, max_length=1500)
    notes = models.TextField('شرح برنامه', blank=True, max_length=3000)
    revision = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def reasons(self):
        reasons = []
        if self.status == self.Status.DRAFT:
            reasons.append('برنامه هنوز تعیین تکلیف نشده است')
        if not self.owner.strip():
            reasons.append('مسئول پیگیری مشخص نیست')
        if not self.next_step.strip():
            reasons.append('اقدام بعدی مشخص نیست')
        if not self.due_date:
            reasons.append('موعد پیگیری مشخص نیست')
        elif self.due_date < timezone.localdate():
            reasons.append('موعد پیگیری گذشته است')
        return reasons


class Case(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='cases')
    code = models.CharField(max_length=40, unique=True)
    title = models.CharField(max_length=200)
    source_status = models.CharField(max_length=80, default='رفع در نسخه؛ نصب تأیید نشده')
    outcome = models.CharField(max_length=80, default='تأییدنشده')


class FollowUp(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='followups')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    result = models.TextField(max_length=3000)
    created_at = models.DateTimeField(default=timezone.now)
    request_id = models.UUIDField(default=uuid.uuid4, unique=True)


class AuditEvent(models.Model):
    program = models.ForeignKey(Program, on_delete=models.PROTECT, related_name='events')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    action = models.CharField(max_length=100)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)


class Mutation(models.Model):
    key = models.UUIDField(unique=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fingerprint = models.CharField(max_length=64)
    program = models.ForeignKey(Program, on_delete=models.PROTECT)
