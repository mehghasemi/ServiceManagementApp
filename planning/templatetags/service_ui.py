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
