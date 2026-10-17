"""Shared-action opportunities driven only by saved criteria and exact CRM IDs."""
from collections import defaultdict
from criteria.engine import planning_facts, matches


def grouped_recommendations(cases, user, today, rules, notes_loaded=False):
    records = planning_facts(cases, user, notes_loaded, today)
    opportunities = [r for r in rules if r.enabled and r.purpose == 'opportunity']
    closure_rules = [r for r in rules if r.enabled and r.closure_candidate and r.purpose == 'attention']
    result, seen = [], set()
    for rule in sorted(opportunities, key=lambda r: (r.priority, r.pk)):
        groups = defaultdict(list)
        for case, facts in records:
            if not case.customer_id or matches(rule, facts) is not True:
                continue
            if rule.grouping == 'customer_program' and not case.parent_id:
                continue
            key = (case.customer_id, case.parent_id if rule.grouping == 'customer_program' else '')
            groups[key].append((case, facts))
        for (customer_id, parent_id), members in groups.items():
            if len(members) < rule.min_count:
                continue
            signature = tuple(sorted(case.pk for case, _ in members))
            if signature in seen:
                continue
            seen.add(signature)
            first = members[0][0]
            candidate = sum(any(matches(r, facts) is True for r in closure_rules) for _, facts in members)
            result.append({'priority': rule.priority, 'title': rule.action_title or rule.label,
                'rule': rule, 'customer': first.customer or 'نام مشتری موجود نیست',
                'program': first.parent_title if parent_id else 'مراجعه یا هماهنگی در سطح مرکز',
                'customer_id': customer_id, 'parent_id': parent_id, 'count': len(members), 'candidate': candidate,
                'reason': f'{len(members)} کیس در یک گروه معتبر با معیار «{rule.label}» منطبق است.',
                'impact': rule.impact,
                'condition': 'تعداد قطعی قابل بستن از داده فعلی قابل تعیین نیست؛ رفع در نسخه هدف یا نتیجه مراجعه و تأیید هر کیس باید بررسی شود.'})
    return sorted(result, key=lambda r: (r['priority'], -r['count'], -r['candidate'], r['customer_id'], r['parent_id']))
