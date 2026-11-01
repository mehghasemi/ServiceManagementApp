"""Bounded typed query algebra over authorized records. No eval or SQL input."""
from collections import defaultdict
from datetime import date, datetime, timedelta
from hashlib import sha256
import json
import math
import jdatetime
from django.utils.dateparse import parse_datetime, parse_date
from django.utils import timezone
from .sources import schema

AGGREGATES = ('count', 'sum', 'average', 'min', 'max', 'distinct_count')
OPERATORS = ('eq', 'ne', 'in', 'contains', 'gt', 'gte', 'lt', 'lte', 'between', 'empty', 'not_empty')
KINDS = ('kpi', 'bars', 'columns', 'line', 'ring', 'pie', 'stacked', 'table', 'pivot')


def day(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return timezone.localtime(value).date() if timezone.is_aware(value) else value.date()
    if isinstance(value, date):
        return value
    value = str(value)
    try:
        if '/' in value:
            y, m, d = map(int, value.split('/'))
            return jdatetime.date(y, m, d).togregorian()
        parsed = parse_datetime(value) or parse_date(value)
        return day(parsed) if isinstance(parsed, datetime) else parsed
    except (ValueError, TypeError):
        return None


def typed(value, kind):
    if value in (None, ''):
        return None
    if kind == 'date':
        return day(value)
    if kind == 'number':
        try:
            number = float(value)
            return number if math.isfinite(number) else None
        except (ValueError, TypeError):
            return None
    return str(value)


def validate_filter(node, fields, depth=0, budget=None):
    if node in (None, {}):
        return
    if budget is None:
        budget = [0]
    budget[0] += 1
    if depth > 4 or budget[0] > 40 or not isinstance(node, dict):
        raise ValueError('فیلتر بیش از حد پیچیده است.')
    if 'logic' in node:
        if set(node) != {'logic', 'children'} or node['logic'] not in ('and', 'or') or not isinstance(node['children'], list) or not 1 <= len(node['children']) <= 20:
            raise ValueError('گروه شرط معتبر نیست.')
        for child in node['children']:
            validate_filter(child, fields, depth + 1, budget)
        return
    if set(node) - {'field', 'op', 'value'} or node.get('field') not in fields or node.get('op') not in OPERATORS:
        raise ValueError('فیلد یا عملگر فیلتر مجاز نیست.')
    op, value, kind = node['op'], node.get('value'), fields[node['field']]['type']
    if op in ('empty', 'not_empty'):
        return
    values = value if op in ('in', 'between') else [value]
    if not isinstance(values, list) or not 1 <= len(values) <= 200 or (op == 'between' and len(values) != 2):
        raise ValueError('مقدار فیلتر معتبر نیست.')
    if op == 'contains' and kind != 'text':
        raise ValueError('شرط شامل فقط برای متن است.')
    if any(not isinstance(v, (str, int, float)) or isinstance(v, bool) or len(str(v)) > 500 or typed(v, kind) is None for v in values):
        raise ValueError('نوع مقدار شرط با فیلد سازگار نیست.')


def matches(row, node, fields):
    if not node:
        return True
    if 'logic' in node:
        values = (matches(row, child, fields) for child in node['children'])
        return all(values) if node['logic'] == 'and' else any(values)
    op, key = node['op'], node['field']
    kind = fields[key]['type']; actual = typed(row.get(key), kind)
    if op == 'empty': return actual is None
    if op == 'not_empty': return actual is not None
    if actual is None: return False
    value = node.get('value')
    if op == 'in': return actual in [typed(v, kind) for v in value]
    if op == 'between': return typed(value[0], kind) <= actual <= typed(value[1], kind)
    value = typed(value, kind)
    if op == 'eq': return actual == value
    if op == 'ne': return actual != value
    if op == 'contains': return value.casefold() in actual.casefold()
    if op == 'gt': return actual > value
    if op == 'gte': return actual >= value
    if op == 'lt': return actual < value
    if op == 'lte': return actual <= value
    return False


def validate_query(query):
    if not isinstance(query, dict) or set(query) - {'source', 'dimensions', 'metric', 'filter', 'empty', 'order', 'columns'}:
        raise ValueError('طرح گزارش معتبر نیست.')
    source = schema().get(query.get('source'))
    if not source:
        raise ValueError('منبع داده مجاز نیست.')
    fields = source['fields']
    dimensions = query.get('dimensions', [])
    if not isinstance(dimensions, list) or len(dimensions) > 4:
        raise ValueError('حداکثر چهار بُعد انتخاب کنید.')
    for dim in dimensions:
        if not isinstance(dim, dict) or set(dim) - {'field', 'bucket'} or dim.get('field') not in fields:
            raise ValueError('بُعد گزارش معتبر نیست.')
        if dim.get('bucket', '') not in ('', 'day', 'week', 'month', 'year'):
            raise ValueError('دوره زمانی معتبر نیست.')
        if dim.get('bucket') and fields[dim['field']]['type'] != 'date':
            raise ValueError('گروه زمانی فقط برای تاریخ مجاز است.')
    metric = query.get('metric', {'aggregate': 'count'})
    if not isinstance(metric, dict) or set(metric) - {'aggregate', 'field', 'formula'} or metric.get('aggregate') not in AGGREGATES:
        raise ValueError('شاخص معتبر نیست.')
    aggregate = metric['aggregate']
    if 'formula' in metric:
        if aggregate == 'count':
            raise ValueError('برای تجمیع نتیجه فرمول، جمع، میانگین، کمینه، بیشینه یا تعداد یکتا انتخاب کنید.')
        formula = metric['formula']
        if not isinstance(formula, dict) or set(formula) != {'left', 'operator', 'right'} or formula['operator'] not in ('+', '-', '*', '/'):
            raise ValueError('فرمول محاسباتی معتبر نیست.')
        for operand in (formula['left'], formula['right']):
            if isinstance(operand, dict) and set(operand) == {'field'} and fields.get(operand['field'], {}).get('type') == 'number':
                continue
            if isinstance(operand, (int, float)) and not isinstance(operand, bool) and math.isfinite(operand) and abs(operand) <= 1e12:
                continue
            raise ValueError('عملوند باید فیلد عددی یا عدد محدود باشد.')
    elif aggregate != 'count':
        field = fields.get(metric.get('field'))
        if not field or (aggregate != 'distinct_count' and field['type'] != 'number'):
            raise ValueError('برای این تجمیع فیلد مناسب انتخاب کنید.')
    if query.get('empty', 'keep') not in ('keep', 'exclude', 'zero') or query.get('order', 'value_desc') not in ('value_desc', 'value_asc', 'label_asc', 'label_desc'):
        raise ValueError('تنظیم نمایش معتبر نیست.')
    columns = query.get('columns', [])
    if not isinstance(columns, list) or len(columns) > 20 or any(c not in fields for c in columns):
        raise ValueError('ستون‌های جدول معتبر نیستند.')
    validate_filter(query.get('filter'), fields)
    return query


def dimension(row, spec, fields):
    value = typed(row.get(spec['field']), fields[spec['field']]['type'])
    if value is None:
        return None
    bucket = spec.get('bucket')
    if isinstance(value, date):
        if bucket == 'week':
            value -= timedelta(days=(value.weekday() + 2) % 7)
        stamp = jdatetime.date.fromgregorian(date=value)
        return stamp.strftime('%Y' if bucket == 'year' else '%Y/%m' if bucket == 'month' else '%Y/%m/%d')
    return str(value)


def measure(row, metric):
    if 'formula' not in metric:
        return row.get(metric.get('field'))
    formula = metric['formula']
    def operand(value):
        return typed(row.get(value['field']) if isinstance(value, dict) else value, 'number')
    left, right = operand(formula['left']), operand(formula['right'])
    if left is None or right is None or (formula['operator'] == '/' and right == 0):
        return None
    result = {'+': lambda: left + right, '-': lambda: left - right, '*': lambda: left * right, '/': lambda: left / right}[formula['operator']]()
    return result if math.isfinite(result) else None


def execute(rows, query, extra_filters=None, group=None, page=1):
    validate_query(query)
    fields = schema()[query['source']]['fields']
    filters = [query.get('filter')] + (extra_filters or [])
    for node in filters: validate_filter(node, fields)
    selected = [row for row in rows if all(matches(row, node, fields) for node in filters)]
    dims = query.get('dimensions', []); groups = defaultdict(list)
    for row in selected:
        key = tuple(dimension(row, dim, fields) for dim in dims)
        if query.get('empty') == 'exclude' and None in key: continue
        groups[key].append(row)
    if not dims and not groups: groups[()] = []
    if len(groups) > 2000: raise ValueError('بیش از ۲۰۰۰ گروه ایجاد شد؛ فیلتر دقیق‌تر یا بُعد کم‌تنوع‌تر انتخاب کنید.')
    metric = query.get('metric', {'aggregate': 'count'}); agg = metric['aggregate']; result = []; details = []
    for key, items in groups.items():
        token = sha256(json.dumps(key, ensure_ascii=False).encode()).hexdigest()[:24]
        raw = [measure(row, metric) for row in items]
        if agg == 'count': value = len(items); missing = 0
        elif agg == 'distinct_count':
            values = [v for v in raw if v not in (None, '')]; value = len({str(v) for v in values}); missing = len(raw) - len(values)
        else:
            values = [typed(v, 'number') for v in raw]; missing = values.count(None)
            values = [v if v is not None else 0 for v in values] if query.get('empty') == 'zero' else [v for v in values if v is not None]
            value = None if not values else sum(values) if agg == 'sum' else sum(values)/len(values) if agg == 'average' else min(values) if agg == 'min' else max(values)
        result.append({'group': token, 'dimensions': list(key), 'label': ' · '.join(v or 'نامشخص' for v in key) or 'کل',
                       'value': value, 'count': len(items), 'missing': missing})
        if group == token: details = items
    order = query.get('order', 'value_desc')
    result.sort(key=lambda r: r['label'] if order.startswith('label') else (r['value'] is not None, r['value'] or 0), reverse=order.endswith('desc'))
    if group is None: details = selected
    columns = query.get('columns') or [key for key in ('number', 'title', 'customer', 'status') if key in fields]
    page = max(1, min(int(page), max(1, (len(details)+49)//50)))
    return {'rows': result, 'record_count': len(selected), 'detail_count': len(details), 'page': page,
            'columns': [{'key': key, **fields[key]} for key in columns],
            'records': [{'id': row['id'], 'url': row.get('_url', ''), 'values': [row.get(key) for key in columns]} for row in details[(page-1)*50:page*50]]}
