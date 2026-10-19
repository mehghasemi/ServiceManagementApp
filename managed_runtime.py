"""Task Scheduler entry point: no detached PowerShell/Start-Process children."""
import json
import os
from pathlib import Path
import runpy
import sys


def main():
    config = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8-sig'))
    source = Path(config['source']).resolve()
    os.environ.update(SERVICE_DATABASE_PATH=config['database'],
                      SERVICE_ENVIRONMENT=config['mode'], SERVICE_MODE='local')
    os.chdir(source)
    sys.path.insert(0, str(source))
    if os.name == 'nt':
        import socket
        from django.core.servers.basehttp import WSGIServer
        original_bind = WSGIServer.server_bind
        WSGIServer.allow_reuse_address = False
        def exclusive_bind(server):
            server.allow_reuse_address = False
            server.allow_reuse_port = False
            server.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
            return original_bind(server)
        WSGIServer.server_bind = exclusive_bind
    # Keep stdout/stderr local and persistent even with no terminal attached.
    log = open(config['log'], 'a', encoding='utf-8', buffering=1)
    sys.stdout = sys.stderr = log
    sys.argv = [str(source / 'run_preview.py'), str(config['port'])]
    if config.get('network'):
        sys.argv = [str(source / 'run_lan.py'), '--host', config['host'],
                    '--subnet', config['subnet'], '--port', str(config['port'])]
    # Managed tasks restart explicitly; no autoreloader can escape supervision.
    from django.core import management
    original_command = management.call_command
    def managed_command(name, *args, **kwargs):
        if name == 'runserver':
            kwargs['use_reloader'] = False
        return original_command(name, *args, **kwargs)
    management.call_command = managed_command
    runpy.run_path(sys.argv[0], run_name='__main__')


if __name__ == '__main__':
    main()
