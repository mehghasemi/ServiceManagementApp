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


def options():
    obj=module_settings('backlogs')
    # Only initialize a never-configured module, never overwrite user selection.
    if not obj.case_view_id and obj.revision == 1:
        choices=CRMView.objects.filter(scope=obj.scope,entity='incident',name=DEFAULT_VIEW)
        if choices.count() == 1:
            note_choices=CRMView.objects.filter(scope=obj.scope,entity='annotation',name='All Notes')
            note=note_choices.first() if note_choices.count()==1 else None
            ModuleSettings.objects.filter(pk=obj.pk,case_view__isnull=True,revision=1).update(case_view=choices.first(),note_view=note,revision=2)
            obj.refresh_from_db()
    return obj


def snapshot_for(user):
    opt=options()
    return shared_queryset(BacklogSnapshot.objects.all(),user).filter(scope=opt.scope,selection_key=selection_key(opt)).order_by('-fetched_at','-pk').first()


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
        opt=module_settings('backlogs')
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
    rows=sort_rows(request,rows,{'number':'number','title':'title','customer':'customer','status':'source_status','service':'evidence.case_service'})
    return render(request,'backlogs/dashboard.html',{'crm_mode':True,'active_module':'planning','mode':'backlogs','options':opt,'snapshot':snapshot,'page':Paginator(rows,20).get_page(request.GET.get('page')),'services':services,'service':service,'query':query})


@operator_required
def detail(request,identifier):
    snapshot=snapshot_for(request.user)
    row=next((r for r in snapshot.records if r['crm_id']==str(identifier)),None) if snapshot else None
    if row is None:
        from django.http import Http404
        raise Http404
    linked=current_cases(request.user).filter(parent_id=str(identifier))
    return render(request,'backlogs/detail.html',{'crm_mode':True,'active_module':'planning','mode':'backlogs','row':row,'snapshot':snapshot,'linked':linked})


@operator_required
def settings_page(request):
    if settings.SERVICE_LAN and not request.user.is_superuser:
        from django.core.exceptions import PermissionDenied
        raise PermissionDenied
    opt=options()
    form=ModuleForm(request.POST if request.method=='POST' else None,instance=opt,scope=opt.scope)
    form.fields['case_view'].label='View بکلاگ‌ها'
    for field in ('activity_view','action_templates'): form.fields.pop(field,None)
    if request.method=='POST' and form.is_valid():
        with transaction.atomic():
            locked=ModuleSettings.objects.select_for_update().get(pk=opt.pk)
            if locked.revision != form.cleaned_data['revision']:
                form.add_error(None,'تنظیمات تغییر کرده؛ صفحه را تازه کنید.')
            else:
                before=model_to_dict(locked)
                for key in ('case_view','note_view','page_size'):setattr(locked,key,form.cleaned_data[key])
                locked.revision+=1;locked.save()
                SettingsAudit.objects.create(actor=request.user,area='backlogs:settings',before=before,after=model_to_dict(locked))
                messages.success(request,'تنظیمات بکلاگ ذخیره شد؛ برای دریافت، به‌روزرسانی را بزنید.')
                return redirect('backlogs')
    return render(request,'backlogs/settings.html',{'form':form,'crm_mode':True,'active_module':'planning','mode':'backlogs'})


@operator_required
def begin(request,kind):
    if request.method!='POST':return HttpResponseNotAllowed(['POST'])
    if kind not in ('sync','catalog'):return JsonResponse({'message':'عملیات معتبر نیست.'},status=400)
    options()
    try:
        job=start_job(request.user,kind,module='backlogs')
        if request.headers.get('Accept')=='application/json':return JsonResponse({'url':reverse('crm-job',args=[job.pk])+'?format=json'},status=202)
        return redirect('crm-job',pk=job.pk)
    except CRMError as error:
        if request.headers.get('Accept')=='application/json':return JsonResponse({'message':str(error)},status=409)
        messages.error(request,str(error));return redirect('backlogs')
