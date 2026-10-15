"""Small, accessible dashboard summaries over the selected CRM snapshot."""
from django.db.models import Count

def status_distribution(cases):
    rows = list(cases.values('source_status').annotate(count=Count('pk')).order_by('-count', 'source_status'))
    total = sum(row['count'] for row in rows)
    maximum = max((row['count'] for row in rows), default=0)
    return [{'label': row['source_status'] or 'وضعیت نامشخص', 'count': row['count'], 'width': round(row['count'] * 100 / maximum, 2) if maximum else 0, 'percent': round(row['count'] * 100 / total, 1) if total else 0} for row in rows]
