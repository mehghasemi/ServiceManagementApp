"""Small, accessible dashboard summaries over the selected CRM snapshot."""
from django.db.models import Count

def status_distribution(cases):
    rows = list(cases.values('source_status').annotate(count=Count('pk')).order_by('-count', 'source_status'))
    total = sum(row['count'] for row in rows)
    maximum = max((row['count'] for row in rows), default=0)
    return [{'source_status': row['source_status'], 'label': row['source_status'] or 'وضعیت نامشخص', 'count': row['count'], 'width': round(row['count'] * 100 / maximum, 2) if maximum else 0, 'percent': round(row['count'] * 100 / total, 1) if total else 0} for row in rows]


def creation_chart(cases, today):
    """Creation cohorts of the CURRENT View, never historical backlog size."""
    import jdatetime
    from django.utils.dateparse import parse_datetime
    from django.utils import timezone
    current = jdatetime.date.fromgregorian(date=today)
    serial = current.year * 12 + current.month - 1
    months = [(n // 12, n % 12 + 1) for n in range(serial - 5, serial + 1)]
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
        x = 30 + index * 100
        y = round(150 - (count / peak * 120 if peak else 0), 2)
        points.append(f'{x},{y}')
        rows.append({'label': f'{key[0]}/{key[1]:02}', 'count': count, 'x': x, 'y': y})
    return {'rows': rows, 'points': ' '.join(points), 'area': '30,150 ' + ' '.join(points) + ' 530,150', 'unknown': unknown, 'sum': sum(counts.values())}


def status_ring(rows):
    offset = 0
    result = []
    total = sum(row['count'] for row in rows)
    for row in rows:
        share = row['count'] * 100 / total if total else 0
        result.append({**row, 'share': share, 'offset': -offset})
        offset += share
    return result
