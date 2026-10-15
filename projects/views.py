from django.core.paginator import Paginator
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
    return ProjectSnapshot.objects.filter(owner=user, scope=configuration().scope, selection_key=selection_key(options)).order_by('-fetched_at').first()


@operator_required
def dashboard(request):
    options = module_settings('projects')
    snapshot = snapshot_for(request.user)
    rows, charts, suggestions = dashboard_data(snapshot.records if snapshot else [], bool(snapshot and snapshot.coverage.get('notes')), options.stale_days, timezone.localdate(), options.parent_review_statuses.split(','))
    total = len(rows)
    overdue = sum(r['overdue'] for r in rows)
    no_manager = sum(r['no_manager'] for r in rows)
    stale = sum(r['stale'] for r in rows)
    query = request.GET.get('q', '').strip()[:100]
    bucket = request.GET.get('bucket', '')
    if query:
        rows = [r for r in rows if query.casefold() in ' '.join([r['title'], r['customer'], r['manager']]).casefold()]
    if bucket in ('overdue', 'no_manager', 'stale', 'no_note'):
        rows = [r for r in rows if r[bucket]]
    last_job = SyncJob.objects.filter(owner=request.user, scope=configuration().scope, config__module='projects').order_by('-created_at').first()
    return render(request, 'projects/dashboard.html', {'crm_mode': True, 'mode': 'projects', 'options': options, 'snapshot': snapshot, 'last_job': last_job, 'total': total, 'overdue': overdue, 'no_manager': no_manager, 'stale': stale, 'chart_rows': charts, 'suggestions': suggestions, 'query': query, 'bucket': bucket, 'page': Paginator(rows, options.page_size).get_page(request.GET.get('page'))})


@operator_required
def detail(request, identifier):
    snapshot = snapshot_for(request.user)
    project = next((row for row in snapshot.records if row['id'] == str(identifier)), None) if snapshot else None
    if project is None:
        raise Http404
    return render(request, 'projects/detail.html', {'crm_mode': True, 'project': project, 'snapshot': snapshot})


@operator_required
@require_POST
def begin_job(request, kind):
    try:
        job = start_job(request.user, kind, module='projects')
        return redirect('crm-job', pk=job.pk)
    except CRMError as error:
        messages.error(request, str(error))
        return redirect('projects-dashboard')
