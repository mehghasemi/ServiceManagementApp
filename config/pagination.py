"""Bounded display page sizes, independent of business evaluation rules."""
def display_page_size(request, configured=10):
    value = request.GET.get('page_size')
    if value in ('10', '20', '50'):
        return int(value)
    return min(configured, 10)
