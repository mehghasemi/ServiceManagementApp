from .sources import schema
from .engine import validate_filter


def validate_configuration(config, widgets):
    if not isinstance(config, dict) or set(config) - {'description', 'filters', 'version'}:
        raise ValueError('تنظیمات داشبورد معتبر نیست.')
    if not isinstance(config.get('description', ''), str) or len(config.get('description', '')) > 2000:
        raise ValueError('توضیحات بیش از حد طولانی است.')
    filters = config.get('filters', [])
    if not isinstance(filters, list) or len(filters) > 12:
        raise ValueError('حداکثر ۱۲ فیلتر عمومی مجاز است.')
    ids = set(); lookup = {}; specs = {w['id']: w for w in widgets}
    for item in filters:
        if not isinstance(item, dict) or set(item) - {'id', 'label', 'source', 'field', 'op', 'control', 'parents', 'targets', 'default'}:
            raise ValueError('تعریف فیلتر عمومی معتبر نیست.')
        key = item.get('id')
        if not isinstance(key, str) or not key.startswith('f-') or len(key) > 70 or key in ids:
            raise ValueError('شناسه فیلتر معتبر نیست.')
        ids.add(key); lookup[key] = item
        if not isinstance(item.get('label'), str) or not 1 <= len(item['label']) <= 100:
            raise ValueError('عنوان فیلتر را وارد کنید.')
        source = schema().get(item.get('source'))
        if not source or item.get('field') not in source['fields']:
            raise ValueError('فیلد فیلتر عمومی مجاز نیست.')
        if item.get('control') not in ('single', 'multi', 'text', 'number', 'range', 'date_range'):
            raise ValueError('نوع کنترل فیلتر معتبر نیست.')
        if item.get('op') not in ('eq', 'in', 'contains', 'between', 'gte', 'lte'):
            raise ValueError('عملگر فیلتر معتبر نیست.')
        if not isinstance(item.get('targets', []), list) or not isinstance(item.get('parents', []), list):
            raise ValueError('وابستگی و مقصد فیلتر باید فهرست باشند.')
        for target in item.get('targets', []):
            if target not in specs or specs[target].get('query', {}).get('source') != item['source']:
                raise ValueError('فیلتر فقط به ابزارک‌های همین منبع قابل اتصال است.')
        if item.get('default') not in (None, '', []):
            validate_filter({'field': item['field'], 'op': item['op'], 'value': item['default']}, source['fields'])
    def visit(key, trail):
        if key in trail: raise ValueError('وابستگی فیلترها دارای چرخه است.')
        for parent in lookup[key].get('parents', []):
            if parent not in lookup or lookup[parent]['source'] != lookup[key]['source']:
                raise ValueError('فیلتر وابسته باید از همین منبع باشد.')
            visit(parent, trail | {key})
    for key in ids: visit(key, set())
    return config


def effective_filters(config, widget, values):
    result = []
    for item in config.get('filters', []):
        if item['source'] != widget['query']['source'] or (item.get('targets') and widget['id'] not in item['targets']):
            continue
        value = values.get(item['id'], item.get('default'))
        if value in (None, '', []): continue
        result.append({'field': item['field'], 'op': item['op'], 'value': value})
    return result
