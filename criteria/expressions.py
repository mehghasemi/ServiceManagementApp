"""Bounded, typed condition trees shared by editor, preview and evaluation."""
from types import SimpleNamespace
from .temporal import METRICS as TEMPORAL, validate as validate_time

KEY = 'expression'

def validate(document, module):
    from .engine import METRICS, ALLOWED
    if not isinstance(document, dict) or set(document) != {'version', 'root'} or document['version'] != 1:
        raise ValueError('ساختار معیار ترکیبی معتبر نیست.')
    count = 0
    def visit(node, depth):
        nonlocal count
        count += 1
        if depth > 4 or count > 40 or not isinstance(node, dict):
            raise ValueError('حداکثر ۴ سطح و ۴۰ جزء برای هر معیار مجاز است.')
        if 'join' in node:
            if set(node) != {'join', 'children'} or node['join'] not in ('all', 'any') or not isinstance(node['children'], list) or not 1 <= len(node['children']) <= 20:
                raise ValueError('هر گروه باید ۱ تا ۲۰ شرط داشته باشد.')
            for child in node['children']: visit(child, depth+1)
            return
        if set(node) != {'metric', 'operator', 'value'} or not isinstance(node['metric'], str) or node['metric'] not in METRICS[module]:
            raise ValueError('فیلد شرط در این ماژول قابل استفاده نیست.')
        metric, operator, value = node['metric'], node['operator'], node['value']
        kind = METRICS[module][metric][1]
        if operator not in ALLOWED[kind]: raise ValueError('عملگر با فیلد انتخابی سازگار نیست.')
        if metric in TEMPORAL:
            if isinstance(value, dict) and isinstance(value.get('holidays'), list):
                from planning.reporting.engine import day
                parsed = [day(v) if isinstance(v,str) else None for v in value['holidays']]
                if any(v is None for v in parsed): raise ValueError('تاریخ تعطیل معتبر نیست.')
                value['holidays'] = [v.isoformat() for v in parsed]
            validate_time(value)
            if operator not in ('gt', 'gte') or (metric == 'customer_wait' and not value['responses']):
                raise ValueError('شرط زمانی یا پیگیری معتبر را کامل کنید.')
        elif kind == 'number':
            if type(value) is not int or not -100000 <= value <= 100000: raise ValueError('مقدار عددی شرط معتبر نیست.')
        elif kind == 'bool':
            if type(value) is not bool: raise ValueError('مقدار شرط باید بله یا خیر باشد.')
        elif not isinstance(value, list) or not 1 <= len(value) <= 50 or any(not isinstance(v,str) or not v.strip() or len(v)>200 for v in value):
            raise ValueError('برای شرط متنی، دست‌کم یک مقدار معتبر وارد کنید.')
    visit(document['root'], 1)
    return document


def evaluate(document, facts, module):
    from .engine import matches
    try: validate(document, module)
    except (ValueError, TypeError, KeyError): return None
    def visit(node):
        if 'join' not in node:
            return matches(SimpleNamespace(enabled=True, active_only=False, **node), facts)
        values = [visit(child) for child in node['children']]
        if node['join'] == 'all':
            return False if False in values else None if None in values else True
        return True if True in values else None if None in values else False
    return visit(document['root'])


def describe(document, module):
    from .engine import METRICS, OPERATORS
    from .temporal import describe as time_description
    try: validate(document, module)
    except (ValueError, TypeError, KeyError): return 'ساختار معیار نیازمند بررسی است.'
    def visit(node):
        if 'join' in node:
            return '(' + (' و ' if node['join']=='all' else ' یا ').join(visit(c) for c in node['children']) + ')'
        if node['metric'] in TEMPORAL: return time_description(SimpleNamespace(**node))
        value=node['value']
        shown=('بله' if value else 'خیر') if isinstance(value,bool) else '، '.join(value) if isinstance(value,list) else str(value)
        return f"{METRICS[module][node['metric']][0]} {OPERATORS[node['operator']]} «{shown}»"
    return visit(document['root'])


def catalogue(module):
    from .engine import METRICS, ALLOWED, OPERATORS
    return [{'key':key,'label':label,'kind':kind,'temporal':key in TEMPORAL,
             'operators':[{'key':op,'label':OPERATORS[op]} for op in (('gt','gte') if key in TEMPORAL else ALLOWED[kind])]} for key,(label,kind) in METRICS[module].items()]
