from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class SystemSettings(models.Model):
    auto_sync_enabled = models.BooleanField(default=True, verbose_name="دریافت خودکار فعال باشد")
    auto_sync_minutes = models.PositiveIntegerField(default=60, choices=[(60, 'یک ساعت'), (120, 'دو ساعت'), (240, 'چهار ساعت'), (480, 'هشت ساعت'), (1440, 'یک روز')], verbose_name="فاصله دریافت خودکار پیش‌فرض")
    base_url = models.URLField(default='https://crm.baridsoft.ir')
    organization = models.CharField(max_length=80, default='Main')
    api_version = models.CharField(max_length=20, default='v9.1')
    request_timeout = models.PositiveIntegerField(default=60)
    ai_provider = models.CharField(max_length=100, blank=True)
    ai_model = models.CharField(max_length=100, blank=True)
    ai_key_env = models.CharField(max_length=100, default='SERVICE_AI_KEY')
    revision = models.PositiveIntegerField(default=1)

    @property
    def api_root(self):
        return f'{self.base_url.rstrip("/")}/{self.organization}/api/data/{self.api_version}'

    @property
    def scope(self):
        import hashlib
        return hashlib.sha256(self.api_root.lower().encode()).hexdigest()


class CRMView(models.Model):
    scope = models.CharField(max_length=64)
    kind = models.CharField(max_length=20)
    crm_id = models.UUIDField()
    name = models.CharField(max_length=300)
    entity = models.CharField(max_length=50)
    refreshed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['scope', 'kind', 'crm_id'], name='unique_crm_view')]

    def __str__(self):
        return f'{self.name} — {"شخصی" if self.kind == "userqueries" else "سازمانی"} ({self.entity})'


class ModuleSettings(models.Model):
    auto_sync_enabled = models.BooleanField(default=True, verbose_name="دریافت خودکار این ماژول فعال باشد")
    auto_sync_minutes = models.PositiveIntegerField(default=0, choices=[(0, "از تنظیمات عمومی (پیش‌فرض یک ساعت)")] + [(60, 'یک ساعت'), (120, 'دو ساعت'), (240, 'چهار ساعت'), (480, 'هشت ساعت'), (1440, 'یک روز')], verbose_name="فاصله دریافت این ماژول")
    last_auto_attempt = models.DateTimeField(null=True, blank=True)
    module = models.CharField(max_length=50, default='planning')
    scope = models.CharField(max_length=64)
    case_view = models.ForeignKey(CRMView, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    note_view = models.ForeignKey(CRMView, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    activity_view = models.ForeignKey(CRMView, null=True, blank=True, on_delete=models.PROTECT, related_name='+')
    stale_days = models.PositiveIntegerField(default=30)
    parent_review_statuses = models.CharField(max_length=500, default='Canceled,Out of Planning,Done,Problem Solved')
    page_size = models.PositiveIntegerField(default=20)
    revision = models.PositiveIntegerField(default=1)
    rules_initialized = models.BooleanField(default=False)
    action_templates = models.TextField(blank=True, default='پیگیری ارتقا\nهماهنگی مراجعه حضوری\nهماهنگی پشتیبانی ریموت\nپیگیری رفع توسط تولید\nتأیید نتیجه با مشتری')

    class Meta:
        constraints = [models.UniqueConstraint(fields=['module', 'scope'], name='unique_module_source')]


class SettingsAudit(models.Model):
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    area = models.CharField(max_length=50)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)


class SyncJob(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kind = models.CharField(max_length=20)
    scope = models.CharField(max_length=64)
    config = models.JSONField(default=dict)
    status = models.CharField(max_length=20, default='queued')
    progress = models.PositiveIntegerField(default=0)
    message = models.CharField(max_length=500, default='در صف اجرا')
    cancel_requested = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    finished_at = models.DateTimeField(null=True)
    active_slot = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['active_slot'], condition=Q(status__in=['queued', 'running']), name='single_active_crm_job')]


class CRMCase(models.Model):
    scope = models.CharField(max_length=64)
    crm_id = models.UUIDField()
    number = models.CharField(max_length=100, blank=True)
    title = models.TextField(blank=True)
    customer_id = models.CharField(max_length=50, blank=True)
    customer = models.CharField(max_length=300, blank=True)
    source_status = models.CharField(max_length=100, blank=True)
    parent_id = models.CharField(max_length=50, blank=True)
    parent_title = models.TextField(blank=True)
    parent_status = models.CharField(max_length=100, blank=True)
    evidence = models.JSONField(default=dict)
    fetched_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['scope', 'crm_id'], name='unique_crm_case_source')]


class PlanningSnapshot(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    scope = models.CharField(max_length=64)
    selection_key = models.CharField(max_length=100)
    cases = models.ManyToManyField(CRMCase)
    job = models.OneToOneField(SyncJob, on_delete=models.PROTECT)
    fetched_at = models.DateTimeField(default=timezone.now)
    source_name = models.CharField(max_length=300)
    coverage = models.JSONField(default=dict)


class CaseAction(models.Model):
    case = models.ForeignKey(CRMCase, on_delete=models.PROTECT, related_name='local_actions')
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    title = models.CharField(max_length=500)
    responsible = models.CharField(max_length=120, blank=True)
    due_date = models.DateField(null=True, blank=True)
    selected_preset = models.CharField(max_length=500, blank=True)
    blocker = models.TextField(blank=True, max_length=2000)
    status = models.CharField(max_length=20, choices=[('open', 'باز'), ('done', 'پیگیری انجام شده')], default='open')
    result = models.TextField(blank=True, max_length=3000)
    request_key = models.UUIDField(unique=True)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True)


class ActionAudit(models.Model):
    action = models.ForeignKey(CaseAction, on_delete=models.PROTECT)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    event = models.CharField(max_length=100)
    data = models.JSONField(default=dict)
    created_at = models.DateTimeField(default=timezone.now)


class ProjectSnapshot(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    scope = models.CharField(max_length=64)
    selection_key = models.CharField(max_length=100)
    job = models.OneToOneField(SyncJob, on_delete=models.PROTECT)
    source_name = models.CharField(max_length=300)
    fetched_at = models.DateTimeField(default=timezone.now)
    records = models.JSONField(default=list)
    coverage = models.JSONField(default=dict)


class BacklogSnapshot(models.Model):
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    scope = models.CharField(max_length=64)
    selection_key = models.CharField(max_length=100)
    job = models.OneToOneField(SyncJob, on_delete=models.PROTECT)
    source_name = models.CharField(max_length=300)
    fetched_at = models.DateTimeField(default=timezone.now)
    records = models.JSONField(default=list)
    coverage = models.JSONField(default=dict)


class EvaluationRule(models.Model):
    dashboard = models.CharField(max_length=20, blank=True, default='', choices=[('', 'عمومی'), ('upgrade', 'ارتقا'), ('onsite', 'مراجعه حضوری'), ('periodic', 'بازدید دوره‌ای')])
    settings = models.ForeignKey(ModuleSettings, on_delete=models.PROTECT, related_name='rules')
    code = models.CharField(max_length=80)
    label = models.CharField(max_length=200)
    enabled = models.BooleanField(default=True)
    purpose = models.CharField(max_length=20, default='attention')
    attention_group = models.CharField(max_length=20, blank=True, default='', choices=[('', 'گروه تعیین نشده'), ('decision', 'نیازمند تصمیم شما'), ('clarification', 'نیازمند روشن‌شدن وضعیت'), ('information', 'نیازمند تکمیل اطلاعات')])
    metric = models.CharField(max_length=50)
    operator = models.CharField(max_length=20)
    value = models.JSONField(default=dict)
    priority = models.PositiveIntegerField(default=3)
    active_only = models.BooleanField(default=True)
    closure_candidate = models.BooleanField(default=False)
    grouping = models.CharField(max_length=30, default='customer_program')
    min_count = models.PositiveIntegerField(default=2)
    action_title = models.CharField(max_length=250, blank=True)
    impact = models.CharField(max_length=600, blank=True)
    revision = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['settings', 'code'], name='unique_module_rule')]
