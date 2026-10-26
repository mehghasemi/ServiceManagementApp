"""One dispatcher in the managed stable local server; no browser dependency."""
import logging
import threading
from datetime import timedelta
from django.db import transaction, close_old_connections
from django.utils import timezone
from django.contrib.auth import get_user_model
from .models import ModuleSettings, SyncJob, SystemSettings
from .jobs import configuration, selection_key, start_job, run_job
from config.access import member


def reserve_due(now=None):
    now=now or timezone.now()
    with transaction.atomic():
        system=SystemSettings.objects.select_for_update().get(pk=configuration().pk)
        SyncJob.objects.filter(status__in=['running','queued'],created_at__lt=now-timedelta(minutes=20)).update(status='failed',finished_at=now,message='مهلت دریافت قبلی پایان یافته؛ داده موفق قبلی حفظ شد.')
        if not system.auto_sync_enabled or SyncJob.objects.filter(status__in=['running','queued']).exists(): return None
        options=ModuleSettings.objects.filter(scope=system.scope,auto_sync_enabled=True,case_view__isnull=False,module__in=['planning','projects','backlogs','periodic']).order_by('last_auto_attempt','pk')
        for opt in options:
            interval=opt.auto_sync_minutes or system.auto_sync_minutes
            if interval not in (60,120,240,480,1440): continue
            latest=SyncJob.objects.filter(scope=system.scope,kind='sync',status='success',config__module=opt.module,config__selection_key=selection_key(opt)).order_by('-finished_at').first()
            stamps=[stamp for stamp in (opt.last_auto_attempt,latest.finished_at if latest else None) if stamp]
            if stamps and now-max(stamps)<timedelta(minutes=interval): continue
            owner=latest.owner if latest and member(latest.owner) and latest.owner.is_staff else get_user_model().objects.filter(is_active=True,is_staff=True).order_by('-is_superuser','pk').first()
            if not owner or not member(owner): continue
            job=start_job(owner,'sync',launch=False,module=opt.module)
            job.config['automatic']=True
            job.save(update_fields=['config'])
            opt.last_auto_attempt=now
            opt.save(update_fields=['last_auto_attempt'])
            return job.pk
    return None


def start_dispatcher():
    def loop():
        while True:
            close_old_connections()
            try:
                job=reserve_due()
                if job: run_job(job)
            except Exception:
                logging.getLogger(__name__).exception('Automatic CRM dispatcher failed')
            finally:
                close_old_connections()
            threading.Event().wait(60)
    threading.Thread(target=loop,daemon=True,name='crm-auto-sync').start()
