from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from integrations.jobs import start_job, run_job

class Command(BaseCommand):
    help = 'Run a read-only CRM operation synchronously; output only status and counts.'

    def add_arguments(self, parser):
        parser.add_argument('kind', choices=['test', 'catalog', 'sync'])

    def handle(self, kind, **options):
        import sys
        if hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8')
        user = get_user_model().objects.get(username='local-preview')
        job = start_job(user, kind, launch=False)
        run_job(job.pk)
        job.refresh_from_db()
        self.stdout.write(f'job={job.pk}; status={job.status}; processed={job.progress}; {job.message}')
        if job.status != 'success':
            raise CommandError('CRM operation did not complete.')
