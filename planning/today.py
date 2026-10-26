"""Optional decision view; retains saved rules and source/object access boundaries."""
from django.shortcuts import render, redirect
from django.utils import timezone
from django.urls import reverse
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import HttpResponseForbidden, HttpResponseBadRequest
from config.access import shared_queryset, member
from integrations.views import operator_required, active_snapshot, current_cases
from integrations.models import CaseAction, SyncJob
from integrations.jobs import configuration, module_settings
from criteria.engine import ensure_rules, planning_facts, evaluate_records
from planning.charts import status_distribution


@login_required
@require_POST
def preference(request):
    if not member(request.user): return HttpResponseForbidden('دسترسی مجاز نیست.')
    choice=request.POST.get('view')
    if choice not in ('today','classic'): return HttpResponseBadRequest('نمای معتبر انتخاب کنید.')
    request.session['dashboard_view']=choice
    return redirect('planning-today' if choice=='today' else 'home')


@operator_required
def dashboard(request):
    today=timezone.localdate()
    snapshot=active_snapshot(request.user)
    cases=current_cases(request.user)
    rules=ensure_rules(module_settings())
    hits, _=evaluate_records(planning_facts(cases,request.user,bool(snapshot and snapshot.coverage.get('notes')),today),rules)
    # Counts are unique cases, not a misleading sum of actions and cases.
    queue={}
    for entry in hits:
        case=entry['item']
        queue[case.pk]={'case':case,'reasons':[r.label for r in entry['rules']], 'priority':entry['priority'],
                        'groups':{r.attention_group for r in entry['rules']},'due':None,'actions':0}
    actions=shared_queryset(CaseAction.objects.filter(case__in=cases,status='open',due_date__lte=today),request.user,'actor').select_related('case').order_by('due_date','pk')
    action_count=0
    for action in actions:
        action_count+=1
        entry=queue.setdefault(action.case_id,{'case':action.case,'reasons':[],'priority':None,'groups':set(),'due':None,'actions':0})
        entry['actions']+=1
        if entry['due'] is None or action.due_date<entry['due']: entry['due']=action.due_date
    from projects.services import day
    for entry in queue.values():
        if entry['due']:
            entry['groups'].add('due')
            entry['reasons'].insert(0,'پیگیری موعدگذشته' if entry['due']<today else 'پیگیری با موعد امروز')
        created=day(entry['case'].evidence.get('created_on'))
        entry['age']=(today-created).days if created and created<=today else None
    counts={key:sum(key in e['groups'] for e in queue.values()) for key in ('due','decision','information')}
    group=request.GET.get('group','')
    entries=[e for e in queue.values() if not group or group in e['groups']]
    entries.sort(key=lambda e:(e['due'] is None,e['due'] or today,e['priority'] if e['priority'] is not None else float('inf'),-(e['age'] or 0),e['case'].pk))
    full=request.GET.get('all')=='1'
    from projects.views import snapshot_for as project_snapshot
    from planning.backlogs import snapshot_for as backlog_snapshot
    sources=[]
    for module,label,snap,route in [('planning','کیس‌ها',snapshot,'planning-dashboard'),('projects','پروژه‌ها',project_snapshot(request.user),'projects-dashboard'),('backlogs','بکلاگ‌ها',backlog_snapshot(request.user),'backlogs'),('periodic','بازدید دوره‌ای',backlog_snapshot(request.user,'periodic'),'planning-periodic')]:
        job=shared_queryset(SyncJob.objects.all(),request.user).filter(scope=configuration().scope,config__module=module).order_by('-created_at').first()
        sources.append({'label':label,'snapshot':snap,'url':reverse(route),'job':job})
    return render(request,'planning/today.html',{'mode':'today','crm_mode':True,'snapshot':snapshot,'counts':counts,
        'action_count':action_count,'page':Paginator(entries,25 if full else 5).get_page(request.GET.get('page')),
        'full':full,'group':group,'queue_total':len(entries),'sources':sources,'status_chart':status_distribution(cases),'case_count':cases.count()})

