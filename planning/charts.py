"""Small, accessible dashboard summaries over the selected CRM snapshot."""
from django.db.models import Count

def status_distribution(cases):
    from planning.drilldown import widget_url
    rows = list(cases.values('source_status').annotate(count=Count('pk')).order_by('-count', 'source_status'))
    total = sum(row['count'] for row in rows)
    maximum = max((row['count'] for row in rows), default=0)
    return [{'url': widget_url('case-status',row['source_status'] or 'نامشخص'), 'source_status': row['source_status'], 'label': row['source_status'] or 'وضعیت نامشخص', 'count': row['count'], 'width': round(row['count'] * 100 / maximum, 2) if maximum else 0, 'percent': round(row['count'] * 100 / total, 1) if total else 0} for row in rows]


def creation_chart(cases, today, start=None, end=None):
    """Creation cohorts of the CURRENT View, never historical backlog size."""
    import jdatetime
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone
    current = jdatetime.date.fromgregorian(date=today)
    serial = current.year * 12 + current.month - 1
    from planning.reporting.engine import day
    lower, upper = day(start) if start else None, day(end) if end else today
    if (start and not lower) or not upper or (lower and lower > upper):
        return {'rows': [], 'sum': 0, 'unknown': 0, 'error': 'بازه تاریخ معتبر نیست؛ تاریخ شمسی مانند ۱۴۰۵/۰۱/۰۱ وارد کنید.'}
    last = jdatetime.date.fromgregorian(date=upper)
    end_serial = last.year * 12 + last.month - 1
    first = jdatetime.date.fromgregorian(date=lower) if lower else None
    start_serial = first.year * 12 + first.month - 1 if first else end_serial - 5
    if end_serial - start_serial > 239:
        return {'rows': [], 'sum': 0, 'unknown': 0, 'error': 'برای خوانایی و کنترل حجم، حداکثر ۲۴۰ ماه در یک نمودار انتخاب کنید.'}
    months = [(n // 12, n % 12 + 1) for n in range(start_serial, end_serial + 1)]
    counts = dict.fromkeys(months, 0)
    unknown = 0
    for case in cases:
        raw = case.evidence.get('created_on')
        try:
            value = parse_datetime(str(raw)) if raw else None
            if value is None:
                raise ValueError()
            date = timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
            if date > today:
                raise ValueError()
            if date > upper or (lower and date < lower):
                continue
            date = jdatetime.date.fromgregorian(date=date)
            key = (date.year, date.month)
            if key in counts:
                counts[key] += 1
        except (ValueError, TypeError, OverflowError):
            unknown += 1
    peak = max(counts.values(), default=0)
    points = []
    rows = []
    for index, (key, count) in enumerate(counts.items()):
        x = round(30 + index * 500 / max(1, len(months) - 1), 2)
        y = round(150 - (count / peak * 120 if peak else 0), 2)
        points.append(f'{x},{y}')
        rows.append({'label': f'{key[0]}/{key[1]:02}', 'count': count, 'x': x, 'y': y})
    from planning.drilldown import widget_url
    from urllib.parse import urlencode
    for row in rows:
        row['url']=widget_url('case-created',row['label'])
        if lower or end:
            row['url'] += '&' + urlencode({'trend_from': lower.isoformat() if lower else '', 'trend_to': upper.isoformat()})
    return {'rows': rows, 'points': ' '.join(points), 'area': '30,150 ' + ' '.join(points) + ' 530,150', 'unknown': unknown, 'sum': sum(counts.values()), 'range_label': f'{rows[0]["label"]} تا {rows[-1]["label"]}'}


def status_ring(rows):
    offset = 0
    result = []
    total = sum(row['count'] for row in rows)
    for row in rows:
        share = row['count'] * 100 / total if total else 0
        result.append({**row, 'share': share, 'offset': -offset})
        offset += share
    return result


def creation_month(case):
    import jdatetime
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime
    try:
        value=parse_datetime(str(case.evidence.get('created_on','')))
        if value is None:return ''
        day=timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
        if day>timezone.localdate():return ''
        value=jdatetime.date.fromgregorian(date=day)
        return f'{value.year}/{value.month:02}'
    except (ValueError,TypeError,OverflowError):return ''
