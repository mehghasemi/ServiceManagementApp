from config.sorting import sort_rows
from collections import Counter
from django.shortcuts import render
from django.core.paginator import Paginator
from django.utils import timezone
from integrations.views import operator_required, current_cases, active_snapshot
from integrations.jobs import module_settings
from criteria.engine import ensure_rules, planning_facts
from .upgrade_analysis import customer_rows


@operator_required
def onsite(request):
    from .backlogs import snapshot_for
    from criteria.engine import matches
    rules = [r for r in ensure_rules(module_settings()) if r.enabled and r.dashboard == 'onsite']
    snapshot = active_snapshot(request.user)
    backlog_snapshot = snapshot_for(request.user)
    backlogs = {r['crm_id']: r for r in backlog_snapshot.records} if backlog_snapshot else {}
    records = planning_facts(current_cases(request.user), request.user, bool(snapshot and snapshot.coverage.get('notes')), timezone.localdate())
    rows = []
    unknown = 0
    for case, facts in records:
        outcomes = [matches(rule, facts) for rule in rules]
        if True in outcomes:
            rows.append({'case': case, 'backlog': backlogs.get(str(case.parent_id), {})})
        elif None in outcomes:
            unknown += 1
    counts = Counter(str(r['case'].customer_id) for r in rows if r['case'].customer_id)
    names = {str(r['case'].customer_id): r['case'].customer for r in rows if r['case'].customer_id}
    peak = max(counts.values(), default=1)
    chart = [{'label': names[key], 'count': count, 'width': round(count*100/peak, 1)} for key, count in counts.most_common(10)]
    total = len(rows)
    without_parent = sum(not r['case'].parent_id for r in rows)
    rows = sort_rows(request, rows, {'title':'case.title', 'customer':'case.customer', 'status':'case.source_status', 'parent':'case.parent_title', 'sprint':'backlog.evidence.sprint', 'release':'backlog.evidence.release'})
    return render(request, 'crm/onsite.html', {'crm_mode':True, 'active_module':'planning', 'mode':'onsite',
        'rules':rules, 'snapshot':snapshot, 'backlog_snapshot':backlog_snapshot, 'total':total, 'customers':len(counts),
        'without_parent':without_parent, 'unknown':unknown, 'chart':chart, 'page':Paginator(rows,20).get_page(request.GET.get('page'))})


@operator_required
def dashboard(request):
    rules=[r for r in ensure_rules(module_settings()) if r.enabled and r.purpose=='opportunity' and r.metric!='fix_newer' and r.dashboard=='upgrade']
    selected=request.GET.get('rule','')
    default=next((r for r in rules if r.code=='upgrade'),rules[0] if rules else None)
    rule=next((r for r in rules if str(r.pk)==selected),default if not selected else None)
    snapshot=active_snapshot(request.user)
    records=planning_facts(current_cases(request.user),request.user,bool(snapshot and snapshot.coverage.get('notes')),timezone.localdate())
    rows=customer_rows(records,rule)
    if request.GET.get('eligible')=='1':rows=[r for r in rows if r['qualifies']]
    eligible=sum(r['qualifies'] for r in rows)
    related=sum(r['count'] for r in rows)
    missing=sum(not r['version_known'] for r in rows)
    versions=Counter(r['current'] for r in rows)
    peak=max(versions.values(),default=1)
    version_chart=[{'label':name,'count':count,'width':round(count*100/peak,1)} for name,count in versions.most_common()]
    top=[dict(r,width=round(r['count']*100/max(related and max(x['count'] for x in rows),1),1)) for r in rows if r['qualifies']][:6]
    total=len(rows)
    rows = sort_rows(request, rows, {'customer':'customer','version':'current','count':'count','programs':'programs','status':'qualifies'})
    return render(request,'crm/upgrades.html',{'crm_mode':True,'mode':'upgrades','active_module':'planning','snapshot':snapshot,
        'rules':rules,'rule':rule,'eligible':eligible,'related':related,'missing':missing,'total':total,'version_chart':version_chart,'top_customers':top,
        'only_eligible':request.GET.get('eligible')=='1','page':Paginator(rows,10).get_page(request.GET.get('page'))})
