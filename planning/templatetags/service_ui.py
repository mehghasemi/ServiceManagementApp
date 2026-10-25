from django import template
from django.utils import timezone
from projects.services import day
from criteria.help import explain_rule

register = template.Library()

@register.filter
def rule_help(rule):
    return explain_rule(rule)

@register.filter
def elapsed(value):
    stamp = day(value)
    if not stamp:
        return 'تاریخ نامشخص'
    days = (timezone.localdate() - stamp).days
    return 'تاریخ آینده؛ نیازمند بررسی' if days < 0 else 'امروز' if days == 0 else f'{days} روز'

@register.inclusion_tag('crm/case_timing.html')
def case_timing(case, loaded):
    notes = case.evidence.get('notes', [])
    dates = [day(n.get('date')) for n in notes]
    valid = [d for d in dates if d]
    return {'created': case.evidence.get('created_on'), 'active': case.evidence.get('state') == 0,
            'loaded': loaded, 'has_notes': bool(notes), 'last_note': max(valid).isoformat() if valid else None}


@register.simple_tag(takes_context=True)
def sort_header(context, key, label):
    from django.utils.html import format_html
    request = context['request']
    active = request.GET.get('sort') == key
    descending = active and request.GET.get('direction') == 'desc'
    params = request.GET.copy()
    params['sort'] = key
    params['direction'] = 'asc' if descending else 'desc' if active else 'asc'
    params.pop('page', None)
    state = ('descending' if descending else 'ascending') if active else 'none'
    arrow = ('▼' if descending else '▲') if active else '↕'
    return format_html('<th data-column="{}" aria-sort="{}"><a class="sort-header" href="?{}" aria-label="مرتب‌سازی بر اساس {}">{} <span aria-hidden="true">{}</span></a></th>', key, state, params.urlencode(), label, label, arrow)


@register.simple_tag
def customer_link(name, identifier=None):
    from uuid import UUID
    from django.urls import reverse
    from django.utils.html import format_html
    try:
        identifier = str(UUID(str(identifier)))
    except (ValueError, TypeError, AttributeError):
        return format_html('<span data-tooltip="شناسه مشتری دریافت نشده؛ پس از بازخوانی قابل پیوند است.">{}</span>', name or 'نامشخص')
    return format_html('<a class="customer-link" href="{}?customer={}" aria-label="کیس‌های برنامه‌ریزی مشتری {}" data-tooltip="نمایش همه کیس‌های مجاز این مشتری در View برنامه‌ریزی"><span class="grid-text">{}</span><span aria-hidden="true">↗</span></a>', reverse('planning-dashboard'), identifier, name or 'نامشخص', name or 'نامشخص')

from config.dates import persian_date
register.filter("persian_date", persian_date)


@register.filter
def latest_note_date(notes):
    from django.utils.dateparse import parse_datetime
    from datetime import timezone as dt_timezone
    stamps=[]
    for note in notes or []:
        try:
            stamp=parse_datetime(str(note.get('date') or ''))
            if stamp:
                if stamp.tzinfo is None: stamp=stamp.replace(tzinfo=dt_timezone.utc)
                stamps.append(stamp)
        except (ValueError, TypeError): pass
    return max(stamps) if stamps else None


@register.filter
def stale_receipt(value):
    from datetime import timedelta
    from django.utils import timezone
    return bool(value and timezone.now() - value > timedelta(hours=24))


@register.simple_tag(takes_context=True)
def dashboard_query(context, **changes):
    query=context['request'].GET.copy()
    query.pop('page',None)
    for key,value in changes.items():
        if value is None: query.pop(key,None)
        else: query[key]=value
    return '?' + query.urlencode() + '#case-list'
