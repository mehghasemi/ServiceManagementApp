import logging
import threading
from django.db import transaction, close_old_connections, IntegrityError
from django.utils import timezone
from .models import SystemSettings, ModuleSettings, CRMView, SyncJob, CRMCase, PlanningSnapshot
from .client import Client, CRMError, Cancelled
from .analysis import normalize

def configuration():
    obj, _ = SystemSettings.objects.get_or_create(pk=1)
    return obj

def module_settings(module="planning"):
    obj = configuration()
    defaults = {'parent_review_statuses': 'Completed,Canceled,Cancelled'} if module == 'projects' else {}
    return ModuleSettings.objects.get_or_create(module=module, scope=obj.scope, defaults=defaults)[0]

def selection_key(options):
    return str(options.case_view_id or '') + ':' + str(options.note_view_id or '') + ':' + str(options.activity_view_id or '')

def start_job(owner, kind, launch=True, module="planning"):
    if module not in ('planning', 'projects'):
        raise CRMError('ماژول معتبر نیست.')
    if kind not in ('test', 'catalog', 'sync'):
        raise CRMError('نوع عملیات معتبر نیست.')
    with transaction.atomic():
        system = SystemSettings.objects.select_for_update().get(pk=configuration().pk)
        options = module_settings(module)
        config = {name: getattr(system, name) for name in ('base_url', 'organization', 'api_version', 'request_timeout')}
        config['module'] = module
        config['selection_key'] = selection_key(options)
        config['views'] = {}
        for name in ('case_view', 'note_view', 'activity_view'):
            view = getattr(options, name)
            if view:
                config['views'][name] = {'crm_id': str(view.crm_id), 'kind': view.kind, 'entity': view.entity, 'name': view.name}
        if kind == 'sync' and 'case_view' not in config['views']:
            raise CRMError('ابتدا View اصلی را در تنظیمات ماژول انتخاب و ذخیره کنید.')
        try:
            job = SyncJob.objects.create(owner=owner, kind=kind, scope=system.scope, config=config)
        except IntegrityError as error:
            raise CRMError('یک دریافت در حال اجراست؛ تا پایان یا لغو آن منتظر بمانید.') from error
    if launch:
        threading.Thread(target=run_job, args=(job.pk,), daemon=True).start()
    return job

def run_job(pk):
    close_old_connections()
    job = SyncJob.objects.get(pk=pk)
    def checkpoint(message='', count=0):
        current = SyncJob.objects.get(pk=pk)
        if current.cancel_requested:
            raise Cancelled('دریافت لغو شد؛ آخرین داده موفق حفظ شد.')
        SyncJob.objects.filter(pk=pk).update(message=message[:500], progress=count)
    try:
        SyncJob.objects.filter(pk=pk).update(status='running', message='شروع دریافت')
        client = Client(job.config, checkpoint)
        if job.kind == 'test':
            result = client.get('WhoAmI')
            if not result.get('UserId'):
                raise CRMError('هویت CRM تأیید نشد.')
            checkpoint('اتصال فقط‌خواندنی با هویت ویندوز تأیید شد', 1)
        elif job.kind == 'catalog':
            catalog = client.catalog()
            checkpoint('ذخیره فهرست Viewهای مجاز', len(catalog))
            with transaction.atomic():
                for row in catalog:
                    CRMView.objects.update_or_create(scope=job.scope, kind=row['kind'], crm_id=row['crm_id'], defaults={'name': row['name'], 'entity': row['entity'], 'refreshed_at': timezone.now()})
        elif job.config.get('module') == 'projects':
            from projects.services import publish_snapshot
            publish_snapshot(job, client, checkpoint)
            return
        else:
            views = job.config['views']
            rows, xml, name = client.fetch_view(views['case_view'])
            notes = client.fetch_view(views['note_view'])[0] if 'note_view' in views else None
            activities = client.fetch_view(views['activity_view'])[0] if 'activity_view' in views else None
            records = normalize(rows, xml, notes, activities)
            checkpoint('آماده ذخیره دریافت کامل', len(records))
            with transaction.atomic():
                # Cancellation wins until the atomic publish begins.
                locked = SyncJob.objects.select_for_update().get(pk=pk)
                if locked.cancel_requested:
                    raise Cancelled('دریافت لغو شد؛ داده قبلی حفظ شد.')
                snapshot = PlanningSnapshot.objects.create(owner=job.owner, scope=job.scope, selection_key=job.config['selection_key'], job=job, source_name=name, coverage={'notes': notes is not None, 'activities': activities is not None, 'mode': 'full', 'raw_rows': len(rows), 'unique_cases': len(records), 'notes_view': views.get('note_view', {}).get('name'), 'activities_view': views.get('activity_view', {}).get('name')})
                ids = []
                for row in records:
                    identifier = row.pop('crm_id')
                    case, _ = CRMCase.objects.update_or_create(scope=job.scope, crm_id=identifier, defaults={**row, 'fetched_at': snapshot.fetched_at})
                    ids.append(case.pk)
                snapshot.cases.add(*ids)
                # Scope absence never deletes a case or any local action.
                SyncJob.objects.filter(pk=pk).update(status='success', finished_at=timezone.now(), message=f'{len(ids)} کیس یکتا از View دریافت شد', progress=len(ids))
            return
        SyncJob.objects.filter(pk=pk).update(status='success', finished_at=timezone.now())
    except Cancelled as error:
        SyncJob.objects.filter(pk=pk).update(status='cancelled', message=str(error), finished_at=timezone.now())
    except Exception as error:
        message = str(error) if isinstance(error, (CRMError, ValueError)) else f'دریافت ناموفق بود؛ داده قبلی حفظ شد. شناسه پیگیری: {pk}'
        # Never log raw CRM payload, credentials or transport exception bodies.
        logging.getLogger(__name__).warning('CRM job %s failed (%s)', pk, type(error).__name__)
        SyncJob.objects.filter(pk=pk).update(status='failed', message=message[:500], finished_at=timezone.now())
    finally:
        close_old_connections()
