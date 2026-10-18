"""Single-record refresh through the selected Views; local decisions untouched."""
from django.db import transaction
from django.utils import timezone
from django.shortcuts import get_object_or_404
from django.http import Http404
from config.access import member
from .client import CRMError, Cancelled
from .models import PlanningSnapshot, ProjectSnapshot, CRMCase, SyncJob
from .analysis import normalize


def row_context(user, module, target):
    if module == 'planning':
        from .views import active_snapshot, current_cases
        record = get_object_or_404(current_cases(user), pk=target)
        snapshot = active_snapshot(user)
        identifier = str(record.crm_id)
    else:
        from projects.views import snapshot_for
        snapshot = snapshot_for(user)
        identifier = str(target)
        if not snapshot or not any(row['id'] == identifier for row in snapshot.records):
            raise Http404
    return {'target_id': identifier, 'snapshot_id': snapshot.pk}


def refresh_row(job, client, checkpoint):
    from .jobs import configuration, module_settings, selection_key
    from projects.services import normalize_projects
    module = job.config['module']
    views = job.config['views']
    identifier = job.config['target_id']
    rows, xml, _ = client.fetch_view(views['case_view'], related_ids=[identifier])
    base = normalize(rows, xml) if module == 'planning' else normalize_projects(rows, None)
    key = 'crm_id' if module == 'planning' else 'id'
    if len(base) != 1 or base[0][key] != identifier:
        raise CRMError('این مورد در View انتخابی برنگشت؛ ممکن است از محدوده خارج شده باشد. داده قبلی حفظ شد؛ دریافت کامل را بررسی کنید.')
    targets = sorted({identifier, base[0].get('parent_id', '')} - {''})
    notes = client.fetch_view(views['note_view'], related_ids=targets)[0] if 'note_view' in views else None
    activities = client.fetch_view(views['activity_view'], related_ids=targets)[0] if 'activity_view' in views and module == 'planning' else None
    record = normalize(rows, xml, notes, activities)[0] if module == 'planning' else normalize_projects(rows, notes)[0]
    checkpoint('ذخیره اطلاعات تازه همین مورد', 1)
    with transaction.atomic():
        locked_job = SyncJob.objects.select_for_update().get(pk=job.pk)
        if locked_job.cancel_requested:
            raise Cancelled('دریافت لغو شد؛ داده قبلی حفظ شد.')
        if not member(job.owner) or not job.owner.is_staff:
            raise CRMError('مجوز دریافت دیگر معتبر نیست؛ داده قبلی حفظ شد.')
        if configuration().scope != job.scope or selection_key(module_settings(module)) != job.config['selection_key']:
            raise CRMError('منبع انتخابی تغییر کرده است؛ داده قبلی حفظ شد.')
        snapshot_model = PlanningSnapshot if module == 'planning' else ProjectSnapshot
        snapshot = snapshot_model.objects.select_for_update().get(pk=job.config['snapshot_id'], scope=job.scope, selection_key=job.config['selection_key'])
        now = timezone.now()
        if module == 'planning':
            case = snapshot.cases.select_for_update().get(crm_id=identifier, scope=job.scope)
            record.pop('crm_id')
            record['evidence']['refresh_selection_key'] = snapshot.selection_key
            for name, value in record.items():
                setattr(case, name, value)
            case.fetched_at = now
            case.save(update_fields=[*record, 'fetched_at'])
        else:
            record['refreshed_at'] = now.isoformat()
            if not any(row['id'] == identifier for row in snapshot.records):
                raise CRMError('مورد در دریافت فعلی موجود نیست.')
            snapshot.records = [record if row['id'] == identifier else row for row in snapshot.records]
            snapshot.save(update_fields=['records'])
        SyncJob.objects.filter(pk=job.pk).update(status='success', finished_at=now, progress=1, message='همین مورد و شواهد Viewهای انتخابی به‌روز شد؛ اقدام‌های محلی حفظ شدند.')
