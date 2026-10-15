from functools import wraps
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
from .analysis import reasons

def operator_required(view):
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_staff:
            return render(request, 'error.html', {'title': 'دسترسی مجاز نیست', 'explanation': 'دسترسی اپراتور محلی برای این بخش لازم است.'}, status=403)
        return view(request, *args, **kwargs)
    return wrapper

def active_snapshot(user):
    config = configuration()
    options = module_settings()
    snapshot = PlanningSnapshot.objects.filter(owner=user, scope=config.scope, selection_key=selection_key(options)).order_by('-fetched_at').first()
    # Case identity is stable across Views, but a historical View must never show
    # newer evidence silently written through a different selection.
    if snapshot and snapshot.cases.filter(fetched_at__gt=snapshot.fetched_at).exists():
        return None
    return snapshot

def current_cases(user):
    snapshot = active_snapshot(user)
    return snapshot.cases.all() if snapshot else CRMCase.objects.none()

@operator_required
def dashboard(request):
    config, options = configuration(), module_settings()
    snapshot = active_snapshot(request.user)
    last_job = SyncJob.objects.filter(owner=request.user, scope=config.scope).filter(Q(config__module='planning') | ~Q(config__has_key='module')).order_by('-created_at').first()
    rows = current_cases(request.user).annotate(open_actions=Count('local_actions', filter=Q(local_actions__actor=request.user, local_actions__status='open')))
    total = rows.count()
    without_action = rows.filter(open_actions=0).count()
    missing_parent = rows.filter(parent_id='').count()
    review_statuses = [v.strip() for v in options.parent_review_statuses.split(',') if v.strip()]
    parent_review = rows.filter(parent_status__in=review_statuses).count()
    from planning.charts import status_distribution
    chart_rows = status_distribution(current_cases(request.user))
    action_coverage = round((total - without_action) * 100 / total, 1) if total else None
    query = request.GET.get('q', '').strip()[:100]
    bucket = request.GET.get('bucket', '')
    if query:
        rows = rows.filter(Q(title__icontains=query) | Q(number__icontains=query) | Q(customer__icontains=query))
    if bucket == 'without_action':
        rows = rows.filter(open_actions=0)
    elif bucket == 'missing_parent':
        rows = rows.filter(parent_id='')
    elif bucket == 'review':
        rows = rows.filter(parent_status__in=review_statuses)
    customer_filter, parent_filter = request.GET.get('customer', '')[:50], request.GET.get('parent', '')[:50]
    if customer_filter and parent_filter:
        rows = rows.filter(customer_id=customer_filter, parent_id=parent_filter)
    page = Paginator(rows.order_by('customer', 'parent_id', 'number'), options.page_size).get_page(request.GET.get('page'))
    for case in page:
        case.review_reasons = reasons(case, options, bool(snapshot and snapshot.coverage.get('notes')), timezone.localdate())
    groups = current_cases(request.user).exclude(parent_id='').values('customer_id', 'customer', 'parent_id', 'parent_title', 'parent_status').annotate(count=Count('id')).order_by('-count')[:8]
    return render(request, 'crm/dashboard.html', {'mode': 'crm-planning', 'snapshot': snapshot, 'last_job': last_job, 'options': options, 'page': page, 'total': total, 'without_action': without_action, 'missing_parent': missing_parent, 'parent_review': parent_review, 'query': query, 'bucket': bucket, 'groups': groups, 'customer_filter': customer_filter, 'parent_filter': parent_filter, 'crm_mode': True, 'chart_rows': chart_rows, 'action_coverage': action_coverage, 'with_action': total - without_action})

@operator_required
def settings_page(request, module=False):
    module_key = 'projects' if module == 'projects' else 'planning'
    from projects.forms import ProjectForm
    obj = module_settings(module_key) if module else configuration()
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
        return redirect('crm-job', pk=job.pk)
    except CRMError as error:
        messages.error(request, str(error))
        return redirect('planning-dashboard')

@operator_required
def job_status(request, pk):
    job = get_object_or_404(SyncJob, pk=pk, owner=request.user)
    if request.GET.get('format') == 'json':
        return JsonResponse({'status': job.status, 'message': job.message, 'progress': job.progress})
    return render(request, 'crm/job.html', {'job': job, 'crm_mode': True, 'mode': 'crm-planning', 'job_module': job.config.get('module', 'planning'), 'active_module': job.config.get('module', 'planning')})

@operator_required
def cancel_job(request, pk):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    get_object_or_404(SyncJob, pk=pk, owner=request.user)
    SyncJob.objects.filter(pk=pk, owner=request.user, status__in=['queued', 'running']).update(cancel_requested=True)
    return redirect('crm-job', pk=pk)

@operator_required
def case_detail(request, pk):
    case = get_object_or_404(current_cases(request.user), pk=pk)
    snapshot = active_snapshot(request.user)
    actions = case.local_actions.filter(actor=request.user).order_by('-created_at')
    return render(request, 'crm/case.html', {'case': case, 'actions': actions, 'snapshot': snapshot, 'reasons': reasons(case, module_settings(), snapshot.coverage.get('notes'), timezone.localdate()), 'crm_mode': True, 'mode': 'crm-planning'})

@operator_required
def create_action(request, pk):
    case = get_object_or_404(current_cases(request.user), pk=pk)
    form = ActionForm(request.POST if request.method == 'POST' else None)
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
    return render(request, 'crm/action.html', {'form': form, 'case': case, 'title': 'تعریف اقدام برای کیس', 'crm_mode': True, 'mode': 'crm-planning'}, status=status)

@operator_required
def complete_action(request, pk):
    action = get_object_or_404(CaseAction, pk=pk, actor=request.user, case__in=current_cases(request.user))
    form = CompleteForm(request.POST if request.method == 'POST' else None, initial={'revision': action.revision})
    status = 200
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            updated = CaseAction.objects.filter(pk=pk, actor=request.user, status='open', revision=form.cleaned_data['revision']).update(status='done', result=form.cleaned_data['result'], revision=F('revision')+1, completed_at=timezone.now())
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
    actions = CaseAction.objects.filter(actor=request.user, case__scope=scope).select_related('case').order_by('status', 'due_date')
    page = Paginator(actions, 30).get_page(request.GET.get('page'))
    for action in page:
        action.in_current_view = action.case_id in active_ids
    return render(request, 'crm/actions.html', {'page': page, 'crm_mode': True, 'mode': 'crm-actions'})


@operator_required
def suggestions_page(request):
    from planning.group_recommendations import grouped_recommendations
    options = module_settings()
    statuses = [s.strip() for s in options.parent_review_statuses.split(',') if s.strip()]
    rows = grouped_recommendations(current_cases(request.user), request.user, timezone.localdate(), statuses)
    return render(request, 'crm/group_recommendations.html', {'crm_mode': True, 'mode': 'planning-suggestions', 'page': Paginator(rows, 15).get_page(request.GET.get('page'))})
