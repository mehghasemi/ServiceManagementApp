from django.http import HttpResponseForbidden
from django.conf import settings
from ipaddress import ip_address, ip_network


class LocalOnlyMiddleware:
    """The demo entry must never become a network authentication bypass."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        remote = request.META.get('REMOTE_ADDR', '')
        permitted = remote in ('127.0.0.1', '::1')
        if settings.SERVICE_LAN:
            try:
                permitted = permitted or any(ip_address(remote) in ip_network(cidr.strip()) for cidr in settings.SERVICE_LAN_SUBNETS if cidr.strip())
            except ValueError:
                permitted = False
            if request.path.startswith(('/demo/', '/programs/', '/decisions/')):
                permitted = False
        if not permitted:
            return HttpResponseForbidden('دسترسی از این نشانی یا به این بخش مجاز نیست.', content_type='text/plain; charset=utf-8')
        response = self.get_response(request)
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        response['Cache-Control'] = 'no-store'
        return response


class NetworkIdentityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if settings.SERVICE_LAN and request.user.is_authenticated:
            from config.access import member
            if not member(request.user):
                from django.contrib.auth import logout
                from django.shortcuts import redirect
                logout(request)
                return redirect('welcome')
        return self.get_response(request)
