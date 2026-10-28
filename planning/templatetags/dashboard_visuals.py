"""Presentation geometry only; input rows must already be scoped and filtered."""
from django import template
import math
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
        start=math.radians(offset*3.6-90); end=math.radians((offset+share)*3.6-90)
        row['pie_path']=f'M60 60 L{60+46*math.cos(start):.4f} {60+46*math.sin(start):.4f} A46 46 0 {1 if share>50 else 0} 1 {60+46*math.cos(end):.4f} {60+46*math.sin(end):.4f} Z'
        row['bar_width']=count*100/peak if peak else 0
        offset += share
    return {'rows': values, 'total': total, 'title': title, 'kind': kind, 'note': note}

@register.inclusion_tag('visuals/visit_stack.html')
def visit_stack(row):
    done=float(row.get('done_width',0))
    pending=float(row.get('pending_width',0))
    return {'done':done,'pending':pending,'unknown':float(row.get('unknown_width',0)),'unknown_start':done+pending}
