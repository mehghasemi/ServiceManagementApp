"""Customer planning groups use saved criteria; no closure prediction."""
from collections import defaultdict
from criteria.engine import matches


def customer_rows(records, rule):
    customers = defaultdict(list)
    for case, facts in records:
        if case.customer_id:
            customers[case.customer_id].append((case, facts))
    rows=[]
    for customer_id, entries in customers.items():
        versions={case.evidence.get('automation_version') for case, _ in entries}
        known=len(versions)==1 and bool(next(iter(versions)))
        groups=defaultdict(list)
        unknown=0
        for case,facts in entries:
            outcome=matches(rule,facts) if rule else None
            unknown+=outcome is None
            if outcome is True and (rule.grouping!='customer_program' or case.parent_id):
                groups[case.parent_id if rule.grouping=='customer_program' else customer_id].append(case)
        matched=[case for members in groups.values() if len(members)>=rule.min_count for case in members] if rule else []
        rows.append({'customer_id':customer_id,'customer':entries[0][0].customer,'current':next(iter(versions)) if known else 'نامشخص یا ناسازگار',
                     'version_known':known,'count':len({case.pk for case in matched}),'total':len(entries),'unknown':unknown,
                     'programs':len({case.parent_id for case in matched if case.parent_id}),'qualifies':bool(matched)})
    return sorted(rows,key=lambda row:(not row['qualifies'],-row['count'],row['customer']))
