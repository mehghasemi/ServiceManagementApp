"""Upgrade potential from saved rules and scoped current snapshots, never closure."""
from criteria.engine import matches


def execution_rows(records, backlogs, ready_rules, program_rules):
    backlog_map = {str(row['crm_id']).lower(): row for row in backlogs}
    groups = {}
    seen = set()
    for case, facts in records:
        if case.pk in seen:
            continue
        seen.add(case.pk)
        outcomes = [matches(rule, facts) for rule in ready_rules]
        if True not in outcomes:
            continue
        key = str(case.parent_id).lower() if case.parent_id else ''
        backlog = backlog_map.get(key)
        evidence = backlog.get('evidence', {}) if backlog else {}
        state = evidence.get('state')
        program_facts = {**evidence, 'source_status': backlog.get('source_status') if backlog else None,
                         'active': state == 0 if state is not None else None}
        matches_program = any(matches(rule, program_facts) is True for rule in program_rules) if backlog else False
        category = 'upgrade' if matches_program else 'other' if backlog else 'unreceived' if key else 'unlinked'
        # Unlinked cases remain grouped per customer, with unknown identities separate.
        group_key = key or 'unlinked:' + str(case.customer_id or case.pk)
        row = groups.setdefault(group_key, {'key': group_key, 'category': category, 'backlog': backlog,
            'customer': case.customer or 'مشتری نامشخص', 'cases': [], 'count': 0,
            'title': backlog.get('title', '') if backlog else case.parent_title or 'بدون بکلاگ',
            'status': (backlog.get('source_status') or 'نامشخص') if backlog else 'دریافت نشده',
            'release': evidence.get('release') or 'ثبت نشده', 'sprint': evidence.get('sprint') or 'ثبت نشده',
            'service': evidence.get('case_service') or 'ثبت نشده',
            'notes': sorted(evidence.get('notes') or [], key=lambda note: str(note.get('date') or ''), reverse=True)})
        row['cases'].append(case)
        row['count'] += 1
    return sorted(groups.values(), key=lambda row: (-row['count'], row['customer'], row['key']))
