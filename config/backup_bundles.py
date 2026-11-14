"""Separate signed bundles for irreplaceable local work and replaceable CRM cache."""
import json
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import serializers, signing
from django.db import transaction
from integrations import models as crm
from planning import models as planning

SETTINGS_MODELS = (crm.SystemSettings, crm.CRMView, crm.ModuleSettings, crm.EvaluationRule)
LOCAL_MODELS = (Group, get_user_model(), *SETTINGS_MODELS, planning.GridPreference,
    planning.PersonalDashboard, planning.DashboardPublication, planning.Program,
    planning.Case, planning.FollowUp, planning.AuditEvent, planning.Mutation,
    crm.CRMCase, crm.CaseAction, crm.ActionAudit, crm.SettingsAudit, planning.InterventionEvent)
DATA_MODELS = (crm.SyncJob, crm.CRMCase, crm.PlanningSnapshot, crm.ProjectSnapshot, crm.BacklogSnapshot)
LABELS = {'local': 'تنظیمات، کاربران و اطلاعات محلی', 'crm': 'داده‌های دریافتی CRM'}
SALT = 'service-separated-backup-v2'


def idle():
    if crm.SyncJob.objects.filter(status__in=['running', 'queued']).exists():
        raise ValueError('ابتدا منتظر پایان دریافت CRM بمانید.')


def latest(model):
    seen = set(); result = []
    for row in model.objects.order_by('-fetched_at', '-pk').iterator():
        key = (row.owner_id, row.scope, row.selection_key)
        if key not in seen:
            seen.add(key); result.append(row)
    return result


def export_bundle(kind, key):
    if kind not in LABELS:
        raise ValueError('نوع پشتیبان معتبر نیست.')
    with transaction.atomic():
        idle()
        if kind == 'local':
            rows = []
            for model in LOCAL_MODELS:
                query = model.objects.all().order_by('pk')
                if model is crm.CRMCase:
                    query = query.filter(local_actions__isnull=False).distinct()
                rows.extend(query)
        else:
            snapshots = [row for model in (crm.PlanningSnapshot, crm.ProjectSnapshot, crm.BacklogSnapshot) for row in latest(model)]
            jobs = crm.SyncJob.objects.filter(pk__in=[row.job_id for row in snapshots]).order_by('pk')
            case_ids = {pk for row in snapshots if isinstance(row, crm.PlanningSnapshot) for pk in row.cases.values_list('pk', flat=True)}
            rows = [*jobs, *crm.CRMCase.objects.filter(pk__in=case_ids).order_by('pk'), *snapshots]
        records = json.loads(serializers.serialize('json', rows, use_natural_foreign_keys=True))
        if kind == 'local':
            # Keep only identity anchors needed by local actions, never notes/snapshots.
            for row in records:
                if row['model'] == 'integrations.crmcase':
                    row['fields']['evidence'] = {}
        else:
            for row in records:
                if row['model'] == 'integrations.syncjob':
                    row['fields']['config'] = {}
        data = {'schema': 2, 'kind': kind, 'records': records}
        return signing.dumps(data, key=key, salt=SALT, compress=True)


def decode_bundle(token, key, kind):
    data = signing.loads(token, key=key, salt=SALT)
    if not isinstance(data, dict) or data.get('schema') != 2 or data.get('kind') != kind:
        raise ValueError('نوع فایل با بخش بازیابی انتخاب‌شده یکسان نیست.')
    records = data.get('records')
    allowed = {model._meta.label_lower for model in (LOCAL_MODELS if kind == 'local' else DATA_MODELS)}
    if not isinstance(records, list) or len(records) > 200000 or any(not isinstance(row, dict) or row.get('model') not in allowed for row in records):
        raise ValueError('ساختار یا مدل‌های پشتیبان معتبر نیست.')
    return records


def restore_bundle(token, key, kind, actor):
    if kind not in LABELS:
        raise ValueError('نوع پشتیبان معتبر نیست.')
    records = decode_bundle(token, key, kind)
    with transaction.atomic():
        idle()
        for wrapper in serializers.deserialize('json', json.dumps(records)):
            item = wrapper.object
            old = type(item).objects.filter(pk=item.pk).first()
            # Do not silently assign saved work to a different account/CRM record.
            identity_fields = ('username',) if isinstance(item, get_user_model()) else ('scope', 'crm_id') if isinstance(item, crm.CRMCase) else ()
            if old and any(getattr(old, f) != getattr(item, f) for f in identity_fields):
                raise ValueError('شناسه پشتیبان با اطلاعات فعلی ناسازگار است؛ بازیابی لغو شد.')
            if isinstance(item, crm.CRMCase) and kind == 'local' and old:
                continue
            if isinstance(item, crm.SyncJob) and item.status in ('running', 'queued'):
                raise ValueError('پشتیبان نباید عملیات دریافت فعال داشته باشد.')
            if isinstance(item, get_user_model()) and item.pk == actor.pk:
                # Recovery must not deactivate/demote the admin executing it.
                item.is_active, item.is_staff, item.is_superuser = old.is_active, old.is_staff, old.is_superuser
            if isinstance(item, crm.SystemSettings):
                from integrations.client import validate_connection
                validate_connection(item.base_url, item.organization, item.api_version)
            if hasattr(item, 'revision'):
                item.revision = max(item.revision, old.revision if old else 0) + 1
            # DB constraints plus deserializer resolve FKs; JSON fields legitimately allow {}.
            wrapper.save()
        crm.SettingsAudit.objects.create(actor=actor, area='backup-restore-'+kind, after={'records': len(records)})
