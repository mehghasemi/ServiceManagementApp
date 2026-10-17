"""Single Windows host, shared local SQLite file, authenticated LAN access."""
import argparse
import ipaddress
import os
import secrets


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', required=True, help='Office network IPv4 address of this host')
    parser.add_argument('--subnet', required=True, help='Allowed company CIDR, e.g. 172.16.5.0/24')
    parser.add_argument('--port', type=int, default=8766)
    args = parser.parse_args()
    host, subnet = ipaddress.ip_address(args.host), ipaddress.ip_network(args.subnet)
    if host.version != 4 or not host.is_private or host.is_loopback or host.is_unspecified or host not in subnet or subnet.prefixlen < 16:
        parser.error('Use the specific private office address and a restricted company subnet.')
    os.environ.update(SERVICE_MODE='lan', SERVICE_LAN_HOST=str(host), SERVICE_LAN_SUBNETS=str(subnet))
    os.environ.setdefault('SERVICE_SECRET_KEY', secrets.token_urlsafe(64))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    import django
    django.setup()
    from django.core.management import call_command
    call_command('migrate', interactive=False, verbosity=0)
    from django.conf import settings
    from django.db import connection
    # The database stays on the server's disk, never a network share.
    with connection.cursor() as cursor:
        cursor.execute('PRAGMA journal_mode=WAL')
    from django.core.wsgi import get_wsgi_application
    from waitress import serve
    print(f'LAN application: http://{host}:{args.port}/', flush=True)
    print('Create individual accounts from the local app /network-users/ before signing in.', flush=True)
    serve(get_wsgi_application(), host=str(host), port=args.port, threads=4, max_request_body_size=2*1024*1024, channel_timeout=60)


if __name__ == '__main__':
    main()
