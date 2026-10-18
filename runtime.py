"""Release snapshots and isolated development; never stop an existing server."""
from contextlib import closing
import argparse
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parent
PRIVATE = ROOT / 'private'
SOURCE_DIRS = ('config', 'criteria', 'integrations', 'planning', 'projects', 'templates', 'static')
SOURCE_FILES = ('runtime.py', 'manage.py', 'run_preview.py', 'run_lan.py', 'VERSION', 'CHANGELOG.json', 'requirements.txt')

def prepare_release():
    releases = PRIVATE / 'releases'
    releases.mkdir(parents=True, exist_ok=True)
    target = releases / datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
    target.mkdir()
    for name in SOURCE_DIRS:
        shutil.copytree(ROOT / name, target / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    for name in SOURCE_FILES:
        shutil.copy2(ROOT / name, target / name)
    pointer = PRIVATE / 'release-next.txt'
    pointer.write_text(target.name, encoding='utf-8')
    return target

def release_path():
    name = (PRIVATE / 'release-next.txt').read_text(encoding='utf-8').strip()
    root = (PRIVATE / 'releases').resolve()
    path = (root / name).resolve()
    if path.parent != root or not (path / 'manage.py').is_file():
        raise ValueError('Invalid release path')
    return path

def clone_database(source, target):
    # SQLite backup handles WAL consistently. Never overwrite existing development work.
    if target.exists():
        raise ValueError('Development database already exists; it will not be overwritten.')
    source = source.resolve(); target = target.resolve()
    if source == target:
        raise ValueError('Development and live databases must differ.')
    with closing(sqlite3.connect(source.as_uri()+'?mode=ro', uri=True)) as src, closing(sqlite3.connect(target)) as dest:
        src.backup(dest)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('mode', choices=['prepare', 'stable', 'development'])
    parser.add_argument('--copy-current', action='store_true')
    parser.add_argument('--network', action='store_true')
    parser.add_argument('--host', default='172.16.5.18')
    parser.add_argument('--subnet', default='172.16.5.0/24')
    parser.add_argument('--port', type=int)
    args=parser.parse_args()
    PRIVATE.mkdir(exist_ok=True)
    if args.mode=='prepare':
        print(prepare_release()); return
    if args.network and args.mode!='stable':
        parser.error('Development is loopback-only.')
    database = PRIVATE / ('development.sqlite3' if args.mode=='development' else 'preview.sqlite3')
    if args.copy_current:
        if args.mode!='development': parser.error('Only development can copy data.')
        clone_database(PRIVATE/'preview.sqlite3', database)
    source = ROOT if args.mode=='development' else release_path()
    env=os.environ.copy()
    env.update(SERVICE_DATABASE_PATH=str(database),SERVICE_ENVIRONMENT=args.mode,SERVICE_MODE='local')
    # Match the existing network database visibility for local stable access as well.
    port=args.port or (8766 if args.network else 8769 if args.mode=='stable' else 8768)
    if args.network:
        command=[sys.executable,str(source/'run_lan.py'),'--host',args.host,'--subnet',args.subnet,'--port',str(port)]
    else:
        command=[sys.executable,str(source/'run_preview.py'),str(port)]
    subprocess.run(command,cwd=source,env=env,check=True)

if __name__=='__main__':
    main()
