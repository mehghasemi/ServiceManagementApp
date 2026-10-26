from config.sorting import sort_rows
from config.pagination import display_page_size
from django.core.paginator import Paginator
from config.access import shared_queryset
from django.http import Http404
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from django.views.decorators.http import require_POST
from integrations.views import operator_required
from integrations.jobs import configuration, module_settings, selection_key, start_job
from integrations.models import ProjectSnapshot, SyncJob
from integrations.client import CRMError
from .services import dashboard_data


def snapshot_for(user):
    options = module_settings('projects')
    return shared_queryset(ProjectSnapshot.objects.all(), user).filter(scope=configuration().scope, selection_key=selection_key(options)).order_by('-fetched_at').first()


@operator_required
def dashboard(request):
    options = module_settings('projects')
    snapshot = snapshot_for(request.user)
    rows, charts, rule_counts = dashboard_data(snapshot.records if snapshot else [], bool(snapshot and snapshot.coverage.get('notes')), options, timezone.localdate())
    query = request.GET.get('q', '').strip()[:100]
    bucket = request.GET.get('bucket', '')
    if query:
        rows = [r for r in rows if query.casefold() in ' '.join([r['title'], r['customer'], r['manager']]).casefold()]
    if bucket:
        rows = [r for r in rows if any(str(rule.pk) == bucket for rule in r['attention_rules'])]
    rows, charts, rule_counts = dashboard_data(rows, bool(snapshot and snapshot.coverage.get('notes')), options, timezone.localdate())
    from collections import Counter
    phases = Counter(r.get('phase') or 'نامشخص' for r in rows)
    peak = max(phases.values(), default=1)
    phase_chart = [{'label': label, 'count': count, 'width': round(count*100/peak, 1)} for label, count in phases.most_common()]
    total = len(rows)
    attention_count = sum(bool(r['attention_rules']) for r in rows)
    suggestions = [entry for entry in rule_counts if entry['count']]
    rows = sort_rows(request, rows, {'title':'title','customer':'customer','manager':'manager','status':'status','phase':'phase','end':'planned_end','note':'last_report'})
    last_job = shared_queryset(SyncJob.objects.all(), request.user).filter(scope=configuration().scope, config__module='projects').order_by('-created_at').first()
    return render(request, 'projects/dashboard.html', {'crm_mode': True, 'mode': 'projects', 'options': options, 'snapshot': snapshot, 'last_job': last_job, 'total': total, 'attention_count': attention_count, 'rule_counts': rule_counts, 'chart_rows': charts, 'phase_chart': phase_chart, 'suggestions': suggestions, 'query': query, 'bucket': bucket, 'page': Paginator(rows, display_page_size(request, options.page_size)).get_page(request.GET.get('page'))})


@operator_required
def detail(request, identifier):
    snapshot = snapshot_for(request.user)
    project = next((row for row in snapshot.records if row['id'] == str(identifier)), None) if snapshot else None
    if project is None:
        raise Http404
    from criteria.engine import ensure_rules, project_facts, matches
    facts = project_facts(project, module_settings('projects'), bool(snapshot.coverage.get('notes')), timezone.localdate())
    attention_rules = [r for r in ensure_rules(module_settings('projects')) if r.purpose == 'attention' and matches(r, facts) is True]
    return render(request, 'projects/detail.html', {'crm_mode': True, 'project': project, 'snapshot': snapshot, 'attention_rules': attention_rules})


@operator_required
@require_POST
def begin_job(request, kind):
    try:
        job = start_job(request.user, kind, module='projects')
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
        return redirect('projects-dashboard')
