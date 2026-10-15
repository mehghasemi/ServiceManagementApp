from pathlib import Path
from django.conf import settings
from django.utils import timezone

def common(request):
    return {'app_version': (Path(settings.BASE_DIR) / 'VERSION').read_text().strip(), 'today': timezone.localdate()}
