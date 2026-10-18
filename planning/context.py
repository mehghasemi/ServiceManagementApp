from pathlib import Path
from django.conf import settings
from django.utils import timezone

def common(request):
    from config.modules import MODULES
    active = 'planning' if request.path.startswith(('/planning/', '/settings/planning/', '/crm/jobs/')) else ''
    if request.path.startswith('/projects/'):
        active = 'projects'
    return {'development_mode': settings.SERVICE_ENVIRONMENT == 'development', 'stable_mode': settings.SERVICE_ENVIRONMENT == 'stable', 'lan_mode': settings.SERVICE_LAN, 'can_configure': request.user.is_authenticated and (request.user.is_superuser or (not settings.SERVICE_LAN and request.user.is_staff)), 'app_version': (Path(settings.BASE_DIR) / 'VERSION').read_text().strip(), 'today': timezone.localdate(), 'modules': MODULES, 'active_module': active}
