"""Presentation geometry only; input rows must already be scoped and filtered."""
from django import template
register = template.Library()

@register.inclusion_tag('visuals/distribution.html')
def distribution(rows, title, kind='ring', note=''):
    values = [dict(row) for row in rows]
    total = sum(max(0, int(row.get('count', 0))) for row in values)
    peak = max((max(0, int(row.get('count', 0))) for row in values), default=0)
    offset = 0
    for index, row in enumerate(values):
        count = max(0, int(row.get('count', 0)))
        share = count * 100 / total if total else 0
        row.setdefault('label',row.get('customer','نامشخص'))
        row.update(y=150-(count * 150 / peak if peak else 0),share=share, offset=-offset, height=count * 150 / peak if peak else 0, color=index % 6)
        offset += share
    return {'rows': values, 'total': total, 'title': title, 'kind': kind, 'note': note}

@register.inclusion_tag('visuals/visit_stack.html')
def visit_stack(row):
    done=float(row.get('done_width',0))
    pending=float(row.get('pending_width',0))
    return {'done':done,'pending':pending,'unknown':float(row.get('unknown_width',0)),'unknown_start':done+pending}
