"""Independent View-based backlog snapshot; never overwrites ticket evidence."""
from django.conf import settings
from django.db import transaction
from django.forms.models import model_to_dict
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponseNotAllowed
from django.urls import reverse
from django.core.paginator import Paginator
from django.utils import timezone
from django.contrib import messages
from config.access import shared_queryset, member
from config.sorting import sort_rows
from integrations.models import BacklogSnapshot, ModuleSettings, CRMView, SyncJob, SettingsAudit
from integrations.jobs import configuration, module_settings, selection_key, start_job
from integrations.forms import ModuleForm
from integrations.views import operator_required, current_cases
from integrations.analysis import normalize
from integrations.client import CRMError, Cancelled

DEFAULT_VIEW = 'همه بکلاگ های پشتیبانی اتوماسیون عمومی'


def visit_data(records, rules, linked, include_all=False):
    from collections import Counter
    from criteria.engine import matches
    rows = []
    unknown = 0
    for source in records:
        evidence = source.get('evidence', {})
        state = evidence.get('state')
        facts = {**evidence, 'source_status': source.get('source_status') or None,
                 'active': state == 0 if state is not None else None}
        for field in ('case_service', 'sprint', 'release'):
            facts[field] = facts.get(field) or None
        outcomes = [matches(rule, facts) for rule in rules]
        if include_all or True in outcomes:
            rows.append({**source, 'ticket_count': linked.get(source['crm_id'], 0)})
        elif None in outcomes:
            unknown += 1
    def chart(field):
        counts = Counter((r.get(field) or 'نامشخص') if field == 'source_status' else (r['evidence'].get(field) or 'ثبت نشده') for r in rows)
        peak = max(counts.values(), default=1)
        return [{'label': key, 'count': n, 'width': round(n * 100 / peak, 1)} for key, n in counts.most_common()]
    return rows, unknown, chart('source_status'), chart('release')


@operator_required
def visits(request, kind):
    from collections import Counter
    from criteria.engine import ensure_rules
    all_rules = [r for r in ensure_rules(options()) if r.enabled and r.dashboard == kind]
    rules = [r for r in all_rules if r.purpose == 'attention']
    snapshot = snapshot_for(request.user, 'periodic')
    linked = Counter(str(parent) for parent in current_cases(request.user).values_list('parent_id', flat=True) if parent)
    records = list({r['crm_id']: r for r in (snapshot.records if snapshot else [])}.values())
    months = sorted({r['evidence'].get('release','') for r in records if r['evidence'].get('release')})
    month = request.GET.get('month','')[:200]
    city = request.GET.get('city','')[:200]
    query = request.GET.get('q', '').strip()[:100]
    if month: records = [r for r in records if r['evidence'].get('release') == month]
    if city: records = [r for r in records if (r['evidence'].get('city') or 'شهر دریافت نشده') == city]
    if query: records = [r for r in records if query.casefold() in ' '.join([r['title'], r['customer']]).casefold()]
    # The dedicated CRM View owns membership; Case Service is often absent.
    rows, unknown, status_chart, release_chart = visit_data(records, [], linked, include_all=True)
    from planning.visit_charts import visit_breakdown, city_columns
    center_chart, city_chart = visit_breakdown(rows, all_rules)
    unknown = sum(item["unknown"] for item in center_chart)
    columns = city_columns(city_chart)
    for item in columns['bars']:
        params = request.GET.copy()
        params.pop('page', None)
        params['city'] = item['label']
        item['url'] = '?' + params.urlencode() + '#visit-list'
    total = len(rows)
    customers = len({r['customer_id'] for r in rows if r.get('customer_id')})
    tickets = sum(r['ticket_count'] for r in rows)
    rows = sort_rows(request, rows, {'title': 'title', 'customer': 'customer', 'status': 'source_status', 'service': 'evidence.case_service', 'sprint': 'evidence.sprint', 'release': 'evidence.release', 'tickets': 'ticket_count'})
    return render(request, 'backlogs/visits.html', {'crm_mode': True, 'active_module': 'planning', 'mode': kind, 'kind': kind,
        'report_scope': options('periodic').report_scope, 'title': 'مراجعه حضوری' if kind == 'onsite' else 'بازدید دوره‌ای', 'rules': rules, 'snapshot': snapshot,
        'total': total, 'customers': customers, 'tickets': tickets, 'unknown': unknown, 'status_chart': status_chart,
        'release_chart': release_chart, 'center_chart': center_chart, 'city_chart': city_chart, 'city_columns': columns, 'city': city, 'months': months, 'month': month, 'query': query, 'page': Paginator(rows, 20).get_page(request.GET.get('page'))})


def options(module='backlogs'):
    obj=module_settings(module)
    # Only initialize a never-configured module, never overwrite user selection.
    if not obj.case_view_id and obj.revision == 1:
        choices=CRMView.objects.filter(scope=obj.scope,entity='incident',name=DEFAULT_VIEW if module == 'backlogs' else 'همه بکلاگ های بازدید دوره ای جاری خدمات عمومی')
        if choices.count() == 1:
            note_choices=CRMView.objects.filter(scope=obj.scope,entity='annotation',name='All Notes')
            note=note_choices.first() if note_choices.count()==1 else None
            ModuleSettings.objects.filter(pk=obj.pk,case_view__isnull=True,revision=1).update(case_view=choices.first(),note_view=note,revision=2)
            obj.refresh_from_db()
    return obj


def snapshot_for(user, module='backlogs'):
    opt=options(module)
    return shared_queryset(BacklogSnapshot.objects.all(),user).filter(scope=opt.scope,selection_key=selection_key(opt),job__config__module=module).order_by('-fetched_at','-pk').first()


def publish(job,client,checkpoint):
    views=job.config['views']
    rows,xml,name=client.fetch_view(views['case_view'])
    records=normalize(rows,xml)
    notes=None
    if 'note_view' in views:
        notes=[]
        ids=[r['crm_id'] for r in records]
        for offset in range(0,len(ids),100):
            checkpoint('دریافت یادداشت‌های بکلاگ‌ها',offset)
            notes.extend(client.fetch_view(views['note_view'],related_ids=ids[offset:offset+100])[0])
    records=normalize(rows,xml,notes)
    checkpoint('ذخیره فهرست مستقل بکلاگ‌ها',len(records))
    with transaction.atomic():
        locked=SyncJob.objects.select_for_update().get(pk=job.pk)
        if locked.cancel_requested: raise Cancelled('دریافت لغو شد؛ داده قبلی حفظ شد.')
        if not member(job.owner) or not job.owner.is_staff: raise CRMError('مجوز دریافت معتبر نیست.')
        opt=module_settings(job.config['module'])
        if configuration().scope != job.scope or selection_key(opt) != job.config['selection_key']:
            raise CRMError('منبع دریافت تغییر کرده؛ داده قبلی حفظ شد.')
        BacklogSnapshot.objects.create(owner=job.owner,scope=job.scope,selection_key=job.config['selection_key'],job=job,records=records,source_name=name,coverage={'notes':notes is not None})
        SyncJob.objects.filter(pk=job.pk).update(status='success',finished_at=timezone.now(),progress=len(records),message=f'{len(records)} بکلاگ دریافت شد؛ '+(f'{len(notes)} یادداشت مرتبط دریافت شد.' if notes is not None else 'View یادداشت انتخاب نشده است.'))


@operator_required
def dashboard(request):
    opt=options(); snapshot=snapshot_for(request.user)
    rows=snapshot.records if snapshot else []
    services=sorted({r['evidence'].get('case_service','') for r in rows if r['evidence'].get('case_service')})
    service=request.GET.get('service',''); query=request.GET.get('q','').strip()[:100]
    if service: rows=[r for r in rows if r['evidence'].get('case_service','') == service]
    if query: rows=[r for r in rows if query.casefold() in ' '.join([r['number'],r['title'],r['customer']]).casefold()]
    rows=sort_rows(request,rows,{'number':'number','title':'title','customer':'customer','status':'source_status','service':'evidence.case_service','sprint':'evidence.sprint','release':'evidence.release'})
    from collections import Counter
    status_chart=[{'label':key or 'نامشخص','count':count} for key,count in Counter(r.get('source_status','') for r in rows).most_common()]
    service_chart=[{'label':key or 'دسته نامشخص','count':count} for key,count in Counter(r['evidence'].get('case_service','') for r in rows).most_common()]
    return render(request,'backlogs/dashboard.html',{'crm_mode':True,'active_module':'planning','mode':'backlogs','status_chart':status_chart,'service_chart':service_chart,'total':len(rows),'options':opt,'snapshot':snapshot,'page':Paginator(rows,20).get_page(request.GET.get('page')),'services':services,'service':service,'query':query})


@operator_required
def detail(request,identifier,module='backlogs'):
    snapshot=snapshot_for(request.user,module)
    row=next((r for r in snapshot.records if r['crm_id']==str(identifier)),None) if snapshot else None
    if row is None:
        from django.http import Http404
        raise Http404
    linked=current_cases(request.user).filter(parent_id=str(identifier))
    return render(request,'backlogs/detail.html',{'crm_mode':True,'active_module':'planning','mode':'backlogs','row':row,'snapshot':snapshot,'linked':linked})


@operator_required
def settings_page(request, module='backlogs'):
    if settings.SERVICE_LAN and not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    opt=options(module)
    form=ModuleForm(request.POST if request.method=='POST' else None,instance=opt,scope=opt.scope)
    form.fields['case_view'].label='View بازدید دوره‌ای' if module == 'periodic' else 'View بکلاگ‌ها'
    if module == 'periodic':
        from django import forms
        form.fields['report_scope'] = forms.ChoiceField(label='دامنه گزارش', choices=ModuleSettings._meta.get_field('report_scope').choices, initial=opt.report_scope, help_text='عملکرد ماهانه فقط زمانی انتخاب شود که View شامل برنامه‌های پایان‌یافته نیز باشد؛ برنامه فیلترهای View را تغییر نمی‌دهد.')
    for field in ('activity_view','action_templates'): form.fields.pop(field,None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            locked=ModuleSettings.objects.select_for_update().get(pk=opt.pk)
            if locked.revision != form.cleaned_data['revision']:
                form.add_error(None,'تنظیمات تغییر کرده؛ صفحه را تازه کنید.')
            else:
                before=model_to_dict(locked)
                for key in ('case_view','note_view','page_size','auto_sync_enabled','auto_sync_minutes'):setattr(locked,key,form.cleaned_data[key])
                if module == 'periodic': locked.report_scope=form.cleaned_data['report_scope']
                locked.revision+=1;locked.save()
                SettingsAudit.objects.create(actor=request.user,area=module+':settings',before=before,after=model_to_dict(locked))
                messages.success(request,'تنظیمات بکلاگ ذخیره شد؛ برای دریافت، به‌روزرسانی را بزنید.')
                return redirect('planning-periodic' if module == 'periodic' else 'backlogs')
    return render(request,'backlogs/settings.html',{'source_module':module,'form':form,'crm_mode':True,'active_module':'planning','mode':'backlogs'})


@operator_required
def begin(request,kind,module='backlogs'):
    if request.method!='POST':return HttpResponseNotAllowed(['POST'])
    if kind not in ('sync','catalog'):return JsonResponse({'message':'عملیات معتبر نیست.'},status=400)
    options(module)
    try:
        job=start_job(request.user,kind,module=module)
        if request.headers.get('Accept')=='application/json':return JsonResponse({'url':reverse('crm-job',args=[job.pk])+'?format=json'},status=202)
        return redirect('crm-job',pk=job.pk)
    except CRMError as error:
        if request.headers.get('Accept')=='application/json':return JsonResponse({'message':str(error)},status=409)
        messages.error(request,str(error));return redirect('backlogs')
