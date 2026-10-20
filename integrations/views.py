from config.sorting import sort_rows
from config.pagination import display_page_size
from functools import wraps
from django.conf import settings
from config.access import shared_queryset, open_actions_filter, member
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, F, Prefetch
from django.forms.models import model_to_dict
from django.http import JsonResponse, HttpResponseNotAllowed
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import SystemSettings, ModuleSettings, SettingsAudit, SyncJob, PlanningSnapshot, CRMCase, CaseAction, ActionAudit
from .forms import SystemForm, ModuleForm, ActionForm, CompleteForm
from .jobs import configuration, module_settings, start_job, selection_key
from .client import CRMError

def operator_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        route = request.resolver_match.url_name if request.resolver_match else ''
        configuration_route = route in ('system-settings', 'planning-settings', 'projects-settings') or 'criteria' in route or 'rule-' in route
        denied = not member(request.user) or (not request.user.is_staff and request.method not in ('GET', 'HEAD'))
        if settings.SERVICE_LAN and configuration_route and not request.user.is_superuser:
            denied = True
        if denied:
            return render(request, 'error.html', {'title': 'دسترسی مجاز نیست', 'explanation': 'نقش حساب شما اجازه انجام این عملیات را ندارد. برای تغییر دسترسی با مدیر هماهنگ کنید.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapper

def active_snapshot(user):
    config = configuration()
    options = module_settings()
    snapshot = shared_queryset(PlanningSnapshot.objects.all(), user).filter(scope=config.scope, selection_key=selection_key(options)).order_by('-fetched_at').first()
    # Case identity is stable across Views, but a historical View must never show
    # newer evidence silently written through a different selection.
    if snapshot and snapshot.cases.filter(fetched_at__gt=snapshot.fetched_at).filter(Q(evidence__refresh_selection_key__isnull=True) | ~Q(evidence__refresh_selection_key=snapshot.selection_key)).exists():
        return None
    return snapshot

def current_cases(user):
    snapshot = active_snapshot(user)
    return snapshot.cases.all() if snapshot else CRMCase.objects.none()

@operator_required
def dashboard(request):
    config, options = configuration(), module_settings()
    snapshot = active_snapshot(request.user)
    last_job = shared_queryset(SyncJob.objects.all(), request.user).filter(scope=config.scope).filter(Q(config__module='planning') | ~Q(config__has_key='module')).order_by('-created_at').first()
    rows = current_cases(request.user).annotate(open_actions=Count('local_actions', filter=open_actions_filter(request.user)))
    total = rows.count()
    type_counts = list(current_cases(request.user).values('evidence__incident_type').annotate(count=Count('pk')).order_by('-count'))
    type_filter = request.GET.get('record_type', '')[:100]
    linked_programs = current_cases(request.user).exclude(parent_id='').values('parent_id').distinct().count()
    unlinked_count = current_cases(request.user).filter(parent_id='').count()
    parent_link = request.GET.get('parent_link', '')
    status_filter = request.GET.get('status', '')[:100]
    source_statuses = list(current_cases(request.user).values_list('source_status', flat=True).distinct().order_by('source_status'))
    without_action = rows.filter(open_actions=0).count()
    from criteria.engine import ensure_rules, planning_facts, evaluate_records, matches
    rules = ensure_rules(options)
    facts_rows = planning_facts(current_cases(request.user), request.user, bool(snapshot and snapshot.coverage.get('notes')), timezone.localdate())
    attention_rows, rule_counts = evaluate_records(facts_rows, rules)
    hit_map = {entry['item'].pk: entry['rules'] for entry in attention_rows}
    from planning.charts import status_distribution
    chart_rows = status_distribution(current_cases(request.user))
    action_coverage = round((total - without_action) * 100 / total, 1) if total else None
    query = request.GET.get('q', '').strip()[:100]
    bucket = request.GET.get('bucket', '')
    if parent_link == 'missing':
        rows = rows.filter(parent_id='')
    if status_filter:
        rows = rows.filter(source_status=status_filter)
    if type_filter:
        rows = rows.filter(evidence__incident_type=type_filter)
    if query:
        rows = rows.filter(Q(title__icontains=query) | Q(number__icontains=query) | Q(customer__icontains=query))
    if bucket == 'without_action':
        rows = rows.filter(open_actions=0)
    elif bucket:
        ids = [entry['item'].pk for entry in attention_rows if any(str(r.pk) == bucket for r in entry['rules'])]
        rows = rows.filter(pk__in=ids)
    customer_filter, parent_filter = request.GET.get('customer', '')[:50], request.GET.get('parent', '')[:50]
    customer_label = ''
    if customer_filter:
        customer_label = current_cases(request.user).filter(customer_id=customer_filter).values_list('customer', flat=True).first() or 'مشتری انتخاب‌شده'
        rows = rows.filter(customer_id=customer_filter)
    if parent_filter:
        rows = rows.filter(parent_id=parent_filter)
    opportunity = request.GET.get('opportunity', '')[:20]
    if opportunity:
        selected_rule = next((r for r in rules if str(r.pk) == opportunity and r.enabled and r.purpose == 'opportunity'), None)
        ids = [case.pk for case, facts in facts_rows if selected_rule and matches(selected_rule, facts) is True]
        rows = rows.filter(pk__in=ids)
    rows = sort_rows(request, rows.order_by('customer', 'parent_id', 'number', 'pk'), {'case':'number','title':'title','type':'evidence.incident_type','category':'evidence.case_category','customer':'customer','status':'source_status','parent':'parent_title','created':'evidence.created_on','actions':'open_actions'})
    page = Paginator(rows, display_page_size(request, options.page_size)).get_page(request.GET.get('page'))
    for case in page:
        case.review_reasons = hit_map.get(case.pk, [])
    groups = current_cases(request.user).exclude(parent_id='').values('customer_id', 'customer', 'parent_id', 'parent_title', 'parent_status').annotate(count=Count('id')).order_by('-count')[:8]
    return render(request, 'crm/dashboard.html', {'mode': 'crm-planning', 'snapshot': snapshot, 'last_job': last_job, 'options': options, 'page': page, 'total': total, 'without_action': without_action,  'query': query, 'bucket': bucket, 'groups': groups, 'customer_filter': customer_filter, 'customer_label': customer_label, 'parent_filter': parent_filter, 'opportunity': opportunity, 'unlinked_count': unlinked_count, 'parent_link': parent_link, 'status_filter': status_filter, 'source_statuses': source_statuses, 'type_counts': type_counts, 'type_filter': type_filter, 'linked_programs': linked_programs, 'attention_count': len(attention_rows), 'rule_counts': rule_counts, 'crm_mode': True, 'chart_rows': chart_rows, 'action_coverage': action_coverage, 'with_action': total - without_action})

@operator_required
def settings_page(request, module=False):
    module_key = 'projects' if module == 'projects' else 'planning'
    from projects.forms import ProjectForm
    obj = module_settings(module_key) if module else configuration()
    if module:
        from criteria.engine import ensure_rules
        ensure_rules(obj)
    form_class = ProjectForm if module == 'projects' else ModuleForm if module else SystemForm
    kwargs = {'scope': obj.scope} if module else {}
    before = model_to_dict(obj)
    form = form_class(request.POST if request.method == 'POST' else None, instance=obj, initial={'revision': obj.revision}, **kwargs)
    status = 200
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            SystemSettings.objects.select_for_update().get(pk=configuration().pk)
            if SyncJob.objects.filter(status__in=['queued', 'running']).exists():
                form.add_error(None, 'تا پایان یا لغو دریافت جاری، تنظیمات را تغییر ندهید.')
                status = 409
            else:
                fields = {name: form.cleaned_data[name] for name in form.Meta.fields}
                updated = type(obj).objects.filter(pk=obj.pk, revision=form.cleaned_data['revision']).update(**fields, revision=F('revision') + 1)
                if not updated:
                    form.add_error(None, 'تنظیمات تغییر کرده‌اند؛ صفحه را دوباره باز کنید و تغییر را بازبینی کنید.')
                    status = 409
                else:
                    obj.refresh_from_db()
                    SettingsAudit.objects.create(actor=request.user, area=module_key if module else 'system', before=before, after=model_to_dict(obj))
                    messages.success(request, 'تنظیمات ذخیره شد. برای دریافت داده، دکمه دریافت را بزنید.')
                    return redirect('projects-settings' if module == 'projects' else 'planning-settings' if module else 'system-settings')
    return render(request, 'crm/settings.html', {'form': form, 'module_settings_page': module, 'project_settings': module == 'projects', 'mode': 'settings', 'crm_mode': True}, status=status)

@operator_required
def begin_job(request, kind):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    try:
        job = start_job(request.user, kind)
        if request.headers.get('Accept') == 'application/json':
            from django.http import JsonResponse
            from django.urls import reverse
            return JsonResponse({'url': reverse('crm-job', args=[job.pk]) + '?format=json'}, status=202)
        return redirect('crm-job', pk=job.pk)
    except CRMError as error:
        if request.headers.get('Accept') == 'application/json':
            from django.http import JsonResponse
            return JsonResponse({'message': str(error)}, status=409)
        messages.error(request, str(error))
        return redirect('planning-dashboard')

@operator_required
def job_status(request, pk):
    job = get_object_or_404(shared_queryset(SyncJob.objects.filter(scope=configuration().scope), request.user), pk=pk)
    if request.GET.get('format') == 'json':
        return JsonResponse({'status': job.status, 'message': job.message, 'progress': job.progress})
    return render(request, 'crm/job.html', {'job': job, 'crm_mode': True, 'mode': 'crm-planning', 'job_module': job.config.get('module', 'planning'), 'active_module': job.config.get('module', 'planning')})

@operator_required
def cancel_job(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    get_object_or_404(shared_queryset(SyncJob.objects.filter(scope=configuration().scope), request.user), pk=pk)
    shared_queryset(SyncJob.objects.filter(scope=configuration().scope), request.user).filter(pk=pk, status__in=['queued', 'running']).update(cancel_requested=True)
    return redirect('crm-job', pk=pk)

@operator_required
def case_detail(request, pk):
    case = get_object_or_404(current_cases(request.user), pk=pk)
    snapshot = active_snapshot(request.user)
    from criteria.engine import ensure_rules, planning_facts, matches
    rules = ensure_rules(module_settings())
    facts = planning_facts(current_cases(request.user).filter(pk=case.pk), request.user, bool(snapshot.coverage.get('notes')), timezone.localdate())[0][1]
    case_reasons = [r for r in rules if r.purpose == 'attention' and matches(r, facts) is True]
    actions = shared_queryset(case.local_actions.all(), request.user, 'actor').order_by('-created_at')
    return render(request, 'crm/case.html', {'case': case, 'actions': actions, 'last_followup': actions.first(), 'last_completed': actions.filter(completed_at__isnull=False).order_by('-completed_at').first(), 'snapshot': snapshot, 'reasons': case_reasons, 'crm_mode': True, 'mode': 'crm-planning'})

@operator_required
def create_action(request, pk):
    case = get_object_or_404(current_cases(request.user), pk=pk)
    form = ActionForm(request.POST if request.method == 'POST' else None, presets=[p.strip() for p in module_settings().action_templates.splitlines() if p.strip()])
    status = 200
    if request.method == 'POST' and form.is_valid():
        data = {key: form.cleaned_data[key] for key in form.Meta.fields}
        with transaction.atomic():
            action, created = CaseAction.objects.get_or_create(request_key=form.cleaned_data['request_key'], defaults={**data, 'case': case, 'actor': request.user})
            if action.case_id != case.pk or action.actor_id != request.user.pk or any(getattr(action, k) != v for k, v in data.items()):
                form.add_error(None, 'این درخواست با اطلاعات متفاوت ثبت شده؛ فرم تازه‌ای باز کنید.')
                status = 409
            else:
                if created:
                    ActionAudit.objects.create(action=action, actor=request.user, event='ایجاد اقدام محلی', data={k: str(v) for k, v in data.items()})
                messages.success(request, 'اقدام به کیس CRM متصل و محلی ذخیره شد؛ CRM تغییر نکرد.')
                return redirect('crm-case', pk=pk)
    return render(request, 'crm/action.html', {'form': form, 'case': case, 'action_templates': [line.strip() for line in module_settings().action_templates.splitlines() if line.strip()], 'title': 'تعریف اقدام برای کیس', 'crm_mode': True, 'mode': 'crm-planning'}, status=status)

@operator_required
def complete_action(request, pk):
    action = get_object_or_404(shared_queryset(CaseAction.objects.all(), request.user, 'actor'), pk=pk, case__in=current_cases(request.user))
    form = CompleteForm(request.POST if request.method == 'POST' else None, initial={'revision': action.revision})
    status = 200
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            updated = shared_queryset(CaseAction.objects.all(), request.user, 'actor').filter(pk=pk, status='open', revision=form.cleaned_data['revision']).update(status='done', result=form.cleaned_data['result'], revision=F('revision')+1, completed_at=timezone.now())
            if updated:
                ActionAudit.objects.create(action=action, actor=request.user, event='اتمام اقدام محلی', data={'result': form.cleaned_data['result']})
                messages.success(request, 'نتیجه اقدام ثبت شد؛ این ثبت به معنی رفع کیس نزد مشتری نیست.')
                return redirect('crm-case', pk=action.case_id)
            action.refresh_from_db()
            if action.status == 'done' and action.result == form.cleaned_data['result']:
                return redirect('crm-case', pk=action.case_id)
            form.add_error(None, 'اقدام تغییر کرده یا قبلاً انجام شده؛ صفحه را بازبینی کنید.')
            status = 409
    return render(request, 'crm/action.html', {'form': form, 'case': action.case, 'title': 'ثبت نتیجه اقدام', 'crm_mode': True, 'mode': 'crm-planning'}, status=status)

@operator_required
def actions_page(request):
    # Keep actions whose cases left the View visible to their owner, with scope labels.
    scope = configuration().scope
    active_ids = set(current_cases(request.user).values_list('id', flat=True))
    actions = shared_queryset(CaseAction.objects.all(), request.user, 'actor').filter(case__scope=scope).select_related('case').order_by('status', 'due_date')
    page = Paginator(actions, 30).get_page(request.GET.get('page'))
    for action in page:
        action.in_current_view = action.case_id in active_ids
    return render(request, 'crm/actions.html', {'page': page, 'crm_mode': True, 'mode': 'crm-actions'})


@operator_required
def suggestions_page(request):
    from planning.group_recommendations import grouped_recommendations
    options = module_settings()
    from criteria.engine import ensure_rules
    snapshot = active_snapshot(request.user)
    rows = grouped_recommendations(current_cases(request.user), request.user, timezone.localdate(), ensure_rules(options), bool(snapshot and snapshot.coverage.get('notes')))
    return render(request, 'crm/group_recommendations.html', {'crm_mode': True, 'mode': 'planning-suggestions', 'page': Paginator(rows, 10).get_page(request.GET.get('page'))})


@operator_required
def refresh_record(request, module, identifier):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    try:
        job = start_job(request.user, 'row', module=module, target=identifier)
        if request.headers.get('Accept') == 'application/json':
            from django.urls import reverse
            return JsonResponse({'url': reverse('crm-job', args=[job.pk]) + '?format=json'}, status=202)
        return redirect('crm-job', pk=job.pk)
    except CRMError as error:
        if request.headers.get('Accept') == 'application/json':
            return JsonResponse({'message': str(error)}, status=409)
        messages.error(request, str(error))
        return redirect('projects-dashboard' if module == 'projects' else 'planning-dashboard')
