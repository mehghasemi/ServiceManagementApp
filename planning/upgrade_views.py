from .drilldown import chart_url
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
    if request.GET.get('center'): rows=[r for r in rows if str(r['case'].customer_id)==request.GET['center']]
    counts = Counter(str(r['case'].customer_id) for r in rows if r['case'].customer_id)
    names = {str(r['case'].customer_id): r['case'].customer for r in rows if r['case'].customer_id}
    peak = max(counts.values(), default=1)
    chart = [{'url':chart_url(request,center=key),'label': names[key], 'count': count, 'width': round(count*100/peak, 1)} for key, count in counts.most_common(10)]
    total = len(rows)
    without_parent = sum(not r['case'].parent_id for r in rows)
    rows = sort_rows(request, rows, {'title':'case.title', 'customer':'case.customer', 'status':'case.source_status', 'parent':'case.parent_title', 'sprint':'backlog.evidence.sprint', 'release':'backlog.evidence.release'})
    return render(request, 'crm/onsite.html', {'crm_mode':True, 'active_module':'planning', 'mode':'onsite',
        'rules':rules, 'snapshot':snapshot, 'backlog_snapshot':backlog_snapshot, 'total':total, 'customers':len(counts),
        'without_parent':without_parent, 'unknown':unknown, 'chart':chart, 'page':Paginator(rows,20).get_page(request.GET.get('page'))})


@operator_required
def dashboard(request):
    if request.GET.get('view') != 'customers' and 'version' not in request.GET and 'rule' not in request.GET and 'eligible' not in request.GET:
        return execution_dashboard(request)
    rules=[r for r in ensure_rules(module_settings()) if r.enabled and r.purpose=='opportunity' and r.metric!='fix_newer' and r.dashboard=='upgrade']
    selected=request.GET.get('rule','')
    default=next((r for r in rules if r.code=='upgrade'),rules[0] if rules else None)
    rule=next((r for r in rules if str(r.pk)==selected),default if not selected else None)
    snapshot=active_snapshot(request.user)
    records=planning_facts(current_cases(request.user),request.user,bool(snapshot and snapshot.coverage.get('notes')),timezone.localdate())
    rows=customer_rows(records,rule)
    if request.GET.get('eligible')=='1':rows=[r for r in rows if r['qualifies']]
    if request.GET.get('center'): rows=[r for r in rows if str(r['customer_id'])==request.GET['center']]
    if 'version' in request.GET: rows=[r for r in rows if r['current']==request.GET['version']]
    eligible=sum(r['qualifies'] for r in rows)
    related=sum(r['count'] for r in rows)
    missing=sum(not r['version_known'] for r in rows)
    versions=Counter(r['current'] for r in rows)
    peak=max(versions.values(),default=1)
    version_chart=[{'url':chart_url(request,version=name),'label':name,'count':count,'width':round(count*100/peak,1)} for name,count in versions.most_common()]
    top=[dict(r,width=round(r['count']*100/max(related and max(x['count'] for x in rows),1),1)) for r in rows if r['qualifies']][:6]
    for item in top: item['url']=chart_url(request,center=item['customer_id'])
    total=len(rows)
    rows = sort_rows(request, rows, {'customer':'customer','version':'current','count':'count','programs':'programs','status':'qualifies'})
    return render(request,'crm/upgrades.html',{'crm_mode':True,'mode':'upgrades','active_module':'planning','snapshot':snapshot,
        'rules':rules,'rule':rule,'eligible':eligible,'related':related,'missing':missing,'total':total,'version_chart':version_chart,'top_customers':top,
        'only_eligible':request.GET.get('eligible')=='1','page':Paginator(rows,10).get_page(request.GET.get('page'))})


def execution_dashboard(request):
    from .backlogs import snapshot_for
    from .upgrade_execution import execution_rows
    ready_rules = [r for r in ensure_rules(module_settings()) if r.enabled and r.purpose == 'upgrade_ready' and r.dashboard == 'upgrade']
    program_rules = [r for r in ensure_rules(module_settings('backlogs')) if r.enabled and r.purpose == 'upgrade_program' and r.dashboard == 'upgrade']
    snapshot = active_snapshot(request.user)
    backlog_snapshot = snapshot_for(request.user)
    records = planning_facts(current_cases(request.user), request.user, bool(snapshot and snapshot.coverage.get('notes')), timezone.localdate())
    if request.GET.get('center'):
        records = [(case, facts) for case, facts in records if str(case.customer_id) == request.GET['center']]
    rows = execution_rows(records, backlog_snapshot.records if backlog_snapshot else [], ready_rules, program_rules)
    months = sorted({r['release'] for r in rows})
    for field in ('release', 'category', 'status'):
        if request.GET.get(field):
            rows = [r for r in rows if r[field] == request.GET[field]]
    if request.GET.get('program'):
        rows = [r for r in rows if r['key'] == request.GET['program']]
    counts = Counter()
    for row in rows:
        counts[row['category']] += row['count']
    programs = [r for r in rows if r['category'] == 'upgrade']
    top = [{'label': r['customer'] + ' · ' + (r['backlog'].get('number') or r['title']), 'count': r['count'],
            'url': chart_url(request, program=r['key'])} for r in programs[:8]]
    statuses = Counter(r['status'] for r in programs)
    status_chart = [{'label': key, 'count': count, 'url': chart_url(request, status=key, category='upgrade')} for key, count in statuses.items()]
    selected_cases = [case for row in rows for case in row['cases']] if request.GET.get('drill') else []
    for row in rows:
        row['url'] = chart_url(request, program=row['key'])
    rows = sort_rows(request, rows, {'customer': 'customer', 'count': 'count', 'status': 'status', 'release': 'release', 'sprint': 'sprint'})
    return render(request, 'crm/upgrade_execution.html', {
        'crm_mode': True, 'mode': 'upgrades', 'active_module': 'planning', 'snapshot': snapshot,
        'backlog_snapshot': backlog_snapshot, 'ready_rules': ready_rules, 'program_rules': program_rules,
        'months': months, 'potential': sum(counts.values()), 'program_count': len(programs),
        'linked': counts['upgrade'], 'unlinked': counts['unlinked'], 'unreceived': counts['unreceived'], 'other': counts['other'],
        'top_programs': top, 'status_chart': status_chart, 'page': Paginator(rows, 15).get_page(request.GET.get('page')),
        'case_page': Paginator(selected_cases, 20).get_page(request.GET.get('case_page')),
    })
