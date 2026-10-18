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
def dashboard(request):
    rules=[r for r in ensure_rules(module_settings()) if r.enabled and r.purpose=='opportunity' and r.metric!='fix_newer']
    selected=request.GET.get('rule','')
    default=next((r for r in rules if r.code=='upgrade'),rules[0] if rules else None)
    rule=next((r for r in rules if str(r.pk)==selected),default if not selected else None)
    snapshot=active_snapshot(request.user)
    records=planning_facts(current_cases(request.user),request.user,bool(snapshot and snapshot.coverage.get('notes')),timezone.localdate())
    rows=customer_rows(records,rule)
    eligible=sum(r['qualifies'] for r in rows)
    related=sum(r['count'] for r in rows)
    missing=sum(not r['version_known'] for r in rows)
    versions=Counter(r['current'] for r in rows)
    peak=max(versions.values(),default=1)
    version_chart=[{'label':name,'count':count,'width':round(count*100/peak,1)} for name,count in versions.most_common(8)]
    top=[dict(r,width=round(r['count']*100/max(related and max(x['count'] for x in rows),1),1)) for r in rows if r['qualifies']][:6]
    total=len(rows)
    if request.GET.get('eligible')=='1':rows=[r for r in rows if r['qualifies']]
    rows = sort_rows(request, rows, {'customer':'customer','version':'current','count':'count','programs':'programs','status':'qualifies'})
    return render(request,'crm/upgrades.html',{'crm_mode':True,'mode':'upgrades','active_module':'planning','snapshot':snapshot,
        'rules':rules,'rule':rule,'eligible':eligible,'related':related,'missing':missing,'total':total,'version_chart':version_chart,'top_customers':top,
        'only_eligible':request.GET.get('eligible')=='1','page':Paginator(rows,10).get_page(request.GET.get('page'))})
