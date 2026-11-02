from pathlib import Path
from datetime import datetime
import json
from django.core.management.base import BaseCommand, CommandError
from config.backups import load_config, config_path
from config.backup_bundles import export_bundle, decode_bundle

class Command(BaseCommand):
    help = 'Create a separate local-work backup by default; CRM data is opt-in.'
    def add_arguments(self, parser):
        parser.add_argument('--kind', choices=['local', 'crm'], default='local')
    def handle(self, *args, **options):
        config=load_config();kind=options['kind']
        try:
            token=export_bundle(kind,config['key'])
            records=decode_bundle(token,config['key'],kind)
            directory=Path(config['directory'])/kind
            directory.mkdir(parents=True,exist_ok=True)
            config_path().write_text(json.dumps(config),encoding='utf-8')
            path=directory/(kind+'-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.smbak')
            path.write_text(token,encoding='utf-8')
            self.stdout.write(f'{kind}: {len(records)} records; {path.stat().st_size} bytes; {path}')
        except (ValueError,OSError) as error:
            raise CommandError(str(error)) from error
