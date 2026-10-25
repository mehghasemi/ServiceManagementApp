from pathlib import Path
from django.conf import settings
from django.utils import timezone

def common(request):
    from config.modules import MODULES
    active = 'planning' if request.path.startswith(('/planning/', '/settings/planning/', '/crm/jobs/')) else ''
    if request.path.startswith('/projects/'):
        active = 'projects'
    header = receipt_context(request)
    return {**header, 'development_mode': settings.SERVICE_ENVIRONMENT == 'development', 'stable_mode': settings.SERVICE_ENVIRONMENT == 'stable', 'lan_mode': settings.SERVICE_LAN, 'can_configure': request.user.is_authenticated and (request.user.is_superuser or (not settings.SERVICE_LAN and request.user.is_staff)), 'app_version': (Path(settings.BASE_DIR) / 'VERSION').read_text().strip(), 'today': timezone.localdate(), 'modules': MODULES, 'active_module': active}



def receipt_context(request):
    from config.access import member, shared_queryset
    if not member(request.user): return {}
    from integrations.jobs import module_settings, configuration
    from integrations.models import SyncJob
    module='projects' if request.path.startswith('/projects/') else 'backlogs' if request.path.startswith(('/planning/backlogs/','/planning/visits/periodic/')) else 'planning'
    if module=='projects':
        from projects.views import snapshot_for
    elif module=='backlogs':
        from planning.backlogs import snapshot_for
    else:
        from integrations.views import active_snapshot as snapshot_for
    options=module_settings(module)
    system=configuration()
    job=shared_queryset(SyncJob.objects.all(),request.user).filter(scope=system.scope,config__module=module).order_by('-created_at').first()
    return {'header_receipt':True,'header_module':module,'header_options':options,'header_snapshot':snapshot_for(request.user),'header_job':job,'header_auto_enabled':system.auto_sync_enabled and options.auto_sync_enabled,'header_auto_minutes':options.auto_sync_minutes or system.auto_sync_minutes}
