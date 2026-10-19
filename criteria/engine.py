"""Bounded declarative comparisons. No eval, code execution or guessed evidence."""
from django.db import transaction
from config.access import shared_queryset
from django.db.models import Prefetch
from integrations.models import EvaluationRule, ModuleSettings, CaseAction
from projects.services import day

# These are available source facts, not business thresholds. Rules live in the DB.
METRICS = {
    'planning': {
        'fix_newer': ('نگارش رفع کیس جدیدتر از نگارش فعلی مشتری است', 'bool'),
        'incident_type': ('نوع رکورد؛ Issue یا Backlog', 'text'),
        'case_category': ('دسته درخواست؛ مانند باگ یا قابلیت جدید', 'text'),
        'parent_type': ('نوع برنامه مرتبط', 'text'),
        'has_parent': ('رابطه برنامه موجود است', 'bool'),
        'parent_status': ('وضعیت برنامه مرتبط', 'text'),
        'source_status': ('وضعیت کیس', 'text'),
        'parent_title': ('عنوان برنامه مرتبط', 'text'),
        'title': ('عنوان کیس', 'text'),
        'note_age': ('قدمت آخرین یادداشت دریافت‌شده؛ روز', 'number'),
        'no_note': ('یادداشت در View موجود نیست', 'bool'),
        'open_count': ('تعداد اقدام محلی باز', 'number'),
        'overdue_days': ('بیشترین عبور از موعد اقدام محلی؛ روز', 'number'),
        'blocker_count': ('تعداد اقدام محلی دارای مانع', 'number'),
    },
    'projects': {
        'status': ('وضعیت پروژه', 'text'),
        'phase': ('مرحله پروژه', 'text'),
        'manager_missing': ('مدیر پروژه در داده موجود نیست', 'bool'),
        'planned_end_missing': ('موعد پایان ثبت نشده است', 'bool'),
        'overdue_days': ('عبور از موعد برنامه پروژه؛ روز', 'number'),
        'note_age': ('قدمت آخرین یادداشت دریافت‌شده؛ روز', 'number'),
        'no_note': ('یادداشت در View موجود نیست', 'bool'),
    },
}
OPERATORS = {'eq': 'برابر', 'ne': 'نابرابر', 'gt': 'بیشتر از', 'gte': 'بیشتر یا مساوی', 'lt': 'کمتر از', 'lte': 'کمتر یا مساوی', 'in': 'یکی از مقادیر', 'contains_any': 'شامل یکی از عبارت‌ها'}
ALLOWED = {'number': ('eq', 'ne', 'gt', 'gte', 'lt', 'lte'), 'bool': ('eq', 'ne'), 'text': ('in', 'contains_any')}


def ensure_rules(options):
    if not options.rules_initialized:
        from .defaults import definitions
        with transaction.atomic():
            locked = ModuleSettings.objects.select_for_update().get(pk=options.pk)
            if not locked.rules_initialized:
                for rule in definitions(locked):
                    EvaluationRule.objects.get_or_create(settings=locked, code=rule['code'], defaults={k: v for k, v in rule.items() if k != 'code'})
                locked.rules_initialized = True
                locked.save(update_fields=['rules_initialized'])
        options.rules_initialized = True
    return list(options.rules.order_by('priority', 'pk'))


def matches(rule, facts):
    if not rule.enabled:
        return False
    if rule.active_only:
        if facts.get('active') is None:
            return None
        if not facts['active']:
            return False
    actual = facts.get(rule.metric)
    if actual is None:
        return None
    value = rule.value
    try:
        if rule.operator == 'in':
            return str(actual).strip().casefold() in [str(v).strip().casefold() for v in value]
        if rule.operator == 'contains_any':
            return any(str(v).strip().casefold() in str(actual).casefold() for v in value if str(v).strip())
        if rule.operator == 'eq':
            return actual == value
        if rule.operator == 'ne':
            return actual != value
        if rule.operator == 'gt':
            return actual > value
        if rule.operator == 'gte':
            return actual >= value
        if rule.operator == 'lt':
            return actual < value
        if rule.operator == 'lte':
            return actual <= value
    except (TypeError, ValueError):
        return None
    return None


def note_facts(notes, loaded, today):
    stamps = [stamp for n in notes for stamp in [day(n.get('date'))] if stamp]
    return {'note_age': (today - max(stamps)).days if loaded and stamps else None,
            'no_note': not notes if loaded else None}


def planning_facts(cases, user, loaded, today):
    actions = shared_queryset(CaseAction.objects.filter(status='open'), user, 'actor')
    rows = cases.prefetch_related(Prefetch('local_actions', queryset=actions, to_attr='rule_actions'))
    result = []
    for case in rows:
        state = case.evidence.get('state')
        facts = {'fix_newer': None, 'incident_type': case.evidence.get('incident_type') or None, 'case_category': case.evidence.get('case_category') or None, 'parent_type': case.evidence.get('parent_details', {}).get('type') or None, 'active': state == 0 if state is not None else None,
                 'has_parent': bool(case.parent_id), 'parent_status': case.parent_status or None,
                 'source_status': case.source_status or None, 'parent_title': case.parent_title or None,
                 'title': case.title or None, 'open_count': len(case.rule_actions),
                 'overdue_days': max(((today-a.due_date).days for a in case.rule_actions if a.due_date), default=None),
                 'blocker_count': sum(bool(a.blocker.strip()) for a in case.rule_actions),
                 **note_facts(case.evidence.get('notes', []), loaded, today)}
        result.append((case, facts))
    return result


def project_facts(row, options, loaded, today):
    state = row.get('state')
    closed = {s.strip().casefold() for s in options.parent_review_statuses.split(',') if s.strip()}
    status = row.get('status')
    active = (state == 0 and status.strip().casefold() not in closed) if state is not None and status else None
    end = day(row.get('planned_end'))
    return {'active': active, 'status': status or None, 'phase': row.get('phase') or None,
            'manager_missing': not row.get('manager'), 'planned_end_missing': not row.get('planned_end'),
            'overdue_days': (today-end).days if end else None,
            **note_facts(row.get('notes', []), loaded, today)}


def evaluate_records(records, rules):
    selected = [r for r in rules if r.enabled and r.purpose == 'attention']
    counts = {r.pk: 0 for r in selected}
    unknown = {r.pk: 0 for r in selected}
    results = []
    for item, facts in records:
        hits = []
        for rule in selected:
            result = matches(rule, facts)
            if result is True:
                hits.append(rule)
                counts[rule.pk] += 1
            elif result is None:
                unknown[rule.pk] += 1
        if hits:
            results.append({'item': item, 'rules': hits, 'priority': min(r.priority for r in hits), 'facts': facts})
    return sorted(results, key=lambda r: r['priority']), [dict(rule=r, count=counts[r.pk], unknown=unknown[r.pk]) for r in selected]
