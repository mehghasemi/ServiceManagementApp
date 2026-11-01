"""Read-only record drilldowns, always resolved against the viewer's current scope."""
from urllib.parse import urlencode
from django.urls import reverse
from django.shortcuts import render
from django.http import Http404
from django.core.paginator import Paginator
from integrations.views import operator_required

def chart_url(request, **values):
    params=request.GET.copy();params.pop('page',None)
    for key,value in values.items(): params[key]=value
    params['drill']='1'
    return '?'+params.urlencode()+'#chart-records'

def widget_url(source, category, split='', series=''):
    return reverse('chart-records')+'?'+urlencode({'source':source,'category':category,'split':split,'series':series})

@operator_required
def records(request):
    from .dashboard_service import CATALOG, FIELDS, dimension
    from integrations.views import current_cases
    from projects.views import snapshot_for as project_snapshot
    from .backlogs import snapshot_for
    source=request.GET.get('source','');split=request.GET.get('split','')
    if source not in CATALOG or (split and (split not in FIELDS or CATALOG[split][1]!=CATALOG[source][1])):raise Http404
    module=CATALOG[source][1]
    if module=='planning': rows=list(current_cases(request.user))
    else:
        snapshot=project_snapshot(request.user) if module=='projects' else snapshot_for(request.user,module)
        rows=snapshot.records if snapshot else []
    category=request.GET.get('category','');series=request.GET.get('series','')
    if source=='case-created':
        from .charts import creation_month
        rows=[r for r in rows if creation_month(r)==category]
        from .reporting.engine import day
        lower, upper = day(request.GET.get('trend_from')), day(request.GET.get('trend_to'))
        if lower or upper:
            rows=[r for r in rows if (stamp:=day(r.evidence.get('created_on'))) and (not lower or stamp>=lower) and (not upper or stamp<=upper)]
    else: rows=[r for r in rows if dimension(r,source)==category and (not split or dimension(r,split)==series)]
    output=[]
    for r in rows:
        if module=='planning':
            output.append({'title':r.title,'customer':r.customer,'number':r.number,'status':r.source_status,'url':reverse('crm-case',args=[r.pk])})
        else:
            identifier=r.get('id') if module=='projects' else r.get('crm_id')
            route={'projects':'project-detail','periodic':'periodic-detail','backlogs':'backlog-detail'}[module]
            output.append({'title':r.get('title',''),'customer':r.get('customer',''),'number':r.get('number',''),'status':r.get('status',r.get('source_status','')),'url':reverse(route,args=[identifier])})
    return render(request,'dashboards/records.html',{'title':CATALOG[source][0]+' · '+category+(' · '+series if split else ''),'page':Paginator(output,20).get_page(request.GET.get('page'))})
