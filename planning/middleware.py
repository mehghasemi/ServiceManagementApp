from django.http import HttpResponseForbidden


class LocalOnlyMiddleware:
    """The demo entry must never become a network authentication bypass."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.META.get('REMOTE_ADDR') not in ('127.0.0.1', '::1'):
            return HttpResponseForbidden('این نسخه فقط روی رایانه میزبان قابل استفاده است.', content_type='text/plain; charset=utf-8')
        response = self.get_response(request)
        response['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self'; font-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
        response['Cache-Control'] = 'no-store'
        return response
