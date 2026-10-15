from pathlib import Path
from django.conf import settings
from django.utils import timezone

def common(request):
    from config.modules import MODULES
    active = 'planning' if request.path.startswith(('/planning/', '/settings/planning/', '/crm/jobs/')) else ''
    return {'app_version': (Path(settings.BASE_DIR) / 'VERSION').read_text().strip(), 'today': timezone.localdate(), 'modules': MODULES, 'active_module': active}
