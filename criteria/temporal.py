"""Versioned temporal rules. Missing event coverage never means no response."""
from datetime import timedelta
from projects.services import day

METRICS = {'status_age': ('ماندگاری در وضعیت انتخابی؛ روز', 'number'),
           'note_silence': ('فاصله از آخرین یادداشت؛ روز', 'number'),
           'customer_wait': ('پیام مشتری بدون پیگیری معتبر؛ روز', 'number')}
RESPONSES = {'staff_note': 'پاسخ کارشناس', 'phone_call': 'تماس مرتبط', 'local_action': 'پیگیری محلی انجام‌شده', 'status_change': 'تغییر وضعیت'}

def validate(config):
    if not isinstance(config, dict) or config.get('version') != 1:
        raise ValueError('تنظیم معیار زمانی معتبر نیست.')
    if type(config.get('days')) is not int or not 0 <= config['days'] <= 3650:
        raise ValueError('مدت باید بین صفر و ۳۶۵۰ روز باشد.')
    if config.get('calendar') not in ('calendar', 'working'):
        raise ValueError('تقویم معتبر نیست.')
    for key in ('statuses', 'responses', 'weekends', 'holidays'):
        if not isinstance(config.get(key), list) or len(config[key]) > 100:
            raise ValueError('فهرست تنظیمات زمانی معتبر نیست.')
    if any(type(n) is not int or n not in range(7) for n in config['weekends']) or len(set(config['weekends'])) == 7:
        raise ValueError('حداقل یک روز هفته باید کاری باشد.')
    if any(not isinstance(s, str) or not s.strip() or len(s) > 200 for s in config['statuses']):
        raise ValueError('وضعیت معتبر نیست.')
    if any(s not in RESPONSES for s in config['responses']):
        raise ValueError('نوع پیگیری معتبر نیست.')
    if any(day(s) is None for s in config['holidays']):
        raise ValueError('تاریخ تعطیل معتبر نیست.')
    return config

def elapsed(start, today, config):
    if not start or start > today: return None
    distance = (today-start).days
    if config['calendar'] == 'calendar': return distance
    # Complete weeks plus at most six remaining days; no unbounded date loop.
    weeks, rest = divmod(distance, 7)
    weekends = set(config['weekends']); holidays = {day(s) for s in config['holidays']}
    count = weeks * (7-len(weekends))
    count += sum((start+timedelta(days=i)).weekday() not in weekends for i in range(1, rest+1))
    return count-sum(start < h <= today and h.weekday() not in weekends for h in holidays)

def outcome(rule, facts):
    try: config = validate(rule.value)
    except (ValueError, TypeError): return None
    if rule.operator not in ('gt', 'gte'): return None
    status = facts.get('source_status', facts.get('status'))
    if config['statuses']:
        if not status: return None
        if str(status).strip().casefold() not in {s.strip().casefold() for s in config['statuses']}: return False
    evidence = facts.get('_evidence', {}); today = facts.get('_today')
    if not today: return None
    if not isinstance(evidence, dict): return None
    temporal = evidence.get('temporal', {})
    if not isinstance(temporal, dict): return None
    if rule.metric == 'status_age':
        entry = temporal.get('status_entry', {})
        if not isinstance(entry, dict) or entry.get('verified') is not True or entry.get('status') != status: return None
        start = day(entry.get('at'))
    elif rule.metric == 'note_silence':
        if not facts.get('_notes_loaded'): return None
        notes = evidence.get('notes', [])
        if not isinstance(notes, list) or any(not isinstance(n, dict) for n in notes): return None
        stamps = [day(n.get('date')) for n in notes]
        if not stamps or any(s is None or s > today for s in stamps): return None
        start = max(stamps)
    else:
        # Adapter supplies complete, scoped event streams; current CRM notes lack author roles.
        coverage = temporal.get('coverage', {})
        if not isinstance(coverage, dict): return None
        kinds = ['customer_note'] + config['responses']
        if not config['responses'] or any(coverage.get(k) is not True for k in kinds): return None
        events = temporal.get('events', [])
        if not isinstance(events, list) or any(not isinstance(e, dict) for e in events): return None
        from django.utils.dateparse import parse_datetime
        from django.utils import timezone
        parsed = []
        for event in events:
            if event.get('kind') not in kinds: continue
            try: stamp = parse_datetime(str(event.get('at', '')))
            except ValueError: return None
            if stamp is None or timezone.is_naive(stamp) or day(stamp) > today: return None
            parsed.append((event['kind'], stamp))
        messages = [t for k,t in parsed if k == 'customer_note']
        if not messages: return False
        # Use the first outstanding message; reminders must not reset the waiting clock.
        replies = [t for k,t in parsed if k in config['responses']]
        pending = [t for t in messages if not replies or t >= max(replies)]
        if not pending: return False
        start = day(min(pending))
    age = elapsed(start, today, config)
    if age is None: return None
    return age > config['days'] if rule.operator == 'gt' else age >= config['days']

def describe(rule):
    c = rule.value
    if not isinstance(c, dict): return 'تنظیم زمانی نیازمند بررسی است.'
    unit = 'روز کاری' if c.get('calendar') == 'working' else 'روز تقویمی'
    status = '، '.join(c.get('statuses', [])) or 'همه وضعیت‌ها'
    comparison = 'بیش از' if rule.operator == 'gt' else 'حداقل'
    return f"{METRICS[rule.metric][0]}؛ {comparison} {c.get('days')} {unit}؛ {status}. شواهد ناقص، نتیجه نامشخص دارد."
