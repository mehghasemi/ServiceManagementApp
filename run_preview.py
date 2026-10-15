"""Loopback-only preview. Generates a per-process secret in environment, never on disk."""
import os
import secrets
import sys
from pathlib import Path

os.environ.setdefault('SERVICE_SECRET_KEY', secrets.token_urlsafe(64))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
(Path(__file__).parent / 'private').mkdir(exist_ok=True)
import django
django.setup()
from django.core.management import call_command

if __name__ == '__main__':
    call_command('migrate', interactive=False, verbosity=0)
    call_command('seed_demo')
    from django.contrib.auth import get_user_model
    from integrations.models import SyncJob
    from django.utils import timezone
    get_user_model().objects.filter(username='local-preview').update(is_staff=True)
    # This launcher is the single local process; interrupted jobs never publish snapshots.
    SyncJob.objects.filter(status__in=['queued', 'running']).update(status='failed', message='اجرا قطع شده بود؛ دریافت را دوباره شروع کنید. داده موفق قبلی حفظ شد.', finished_at=timezone.now())
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f'Local preview: http://127.0.0.1:{port}', flush=True)
    call_command('runserver', f'127.0.0.1:{port}', use_reloader=False)
