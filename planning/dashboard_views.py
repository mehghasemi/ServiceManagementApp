import json
import re
import uuid
from django.contrib import messages
from django.db import transaction, IntegrityError
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from integrations.views import operator_required
from config.access import member
from config.accounts import can_manage
from .models import PersonalDashboard, DashboardPublication
from .dashboard_service import CATALOG, BUILTINS, chart_data


def validate_widgets(value, custom):
    if not isinstance(value,list) or len(value)>30: raise ValueError()
    ids=set()
    for widget in value:
        fields={'id','width','height','hidden'} | ({'source','kind'} if custom else set())
        if not isinstance(widget,dict) or set(widget)!=fields: raise ValueError()
        if not isinstance(widget['id'],str) or not re.fullmatch(r'w-[a-z0-9-]{1,60}',widget['id']) or widget['id'] in ids: raise ValueError()
        ids.add(widget['id'])
        if type(widget['width']) is not int or widget['width'] not in (4,6,8,12): raise ValueError()
        if widget['height'] not in ('compact','normal','tall') or type(widget['hidden']) is not bool: raise ValueError()
        if custom:
            if widget['source'] not in CATALOG: raise ValueError()
            allowed=('line',) if widget['source']=='case-created' else ('ring','columns')
            if widget['kind'] not in allowed: raise ValueError()
    return value


@operator_required
@require_http_methods(['GET','POST'])
def index(request):
    dashboards=PersonalDashboard.objects.filter(user=request.user,key__startswith='custom-').order_by('-updated_at')
    if request.method=='POST':
        title=request.POST.get('title','').strip()
        if not title or len(title)>100: messages.error(request,'نام داشبورد باید بین ۱ تا ۱۰۰ نویسه باشد.')
        elif dashboards.count()>=20: messages.error(request,'حداکثر ۲۰ داشبورد شخصی می‌توانید داشته باشید.')
        else:
            row=PersonalDashboard.objects.create(user=request.user,key='custom-'+uuid.uuid4().hex,title=title)
            return redirect('personal-dashboard',key=row.key)
    return render(request,'dashboards/index.html',{'dashboards':dashboards,'shared_dashboards':DashboardPublication.objects.filter(enabled=True,key__startswith='custom-').order_by('title'),'mode':'personal-dashboards'})


@operator_required
@ensure_csrf_cookie
def dashboard(request,key):
    row=get_object_or_404(PersonalDashboard,user=request.user,key=key,key__startswith='custom-')
    return render(request,'dashboards/detail.html',{'dashboard':row,'widgets':chart_data(request.user,row.widgets),'catalog':CATALOG,'mode':'personal-dashboards'})


@ensure_csrf_cookie
@require_http_methods(['GET','POST'])
def layout(request,key):
    if not member(request.user): return JsonResponse({'error':'دسترسی مجاز نیست.'},status=403)
    custom=key.startswith('custom-')
    if key not in BUILTINS and not custom: return JsonResponse({'error':'داشبورد ناشناخته است.'},status=404)
    row=PersonalDashboard.objects.filter(user=request.user,key=key).first()
    if custom and row is None: return JsonResponse({'error':'داشبورد یافت نشد.'},status=404)
    publication=DashboardPublication.objects.filter(key=key).first()
    if request.method=='GET':
        inherited=bool(not custom and not (row and row.widgets) and publication and publication.enabled)
        widgets=publication.widgets if inherited else row.widgets if row else []
        return JsonResponse({'widgets':widgets,'revision':row.revision if row else 0,'title':row.title if row else '',
                             'inherited':inherited,'publication_revision':publication.revision if publication else 0,
                             'published':bool(publication and publication.enabled),'can_publish':can_manage(request.user,request)})
    try:
        if len(request.body)>20000: raise ValueError()
        data=json.loads(request.body)
        widgets=validate_widgets(data['widgets'],custom)
        revision=data['revision']
        if type(revision) is not int or revision<0: raise ValueError()
        title=data.get('title',row.title if row else '')
        if not isinstance(title,str) or len(title)>100 or (custom and not title.strip()): raise ValueError()
    except (ValueError,KeyError,TypeError,UnicodeDecodeError):
        return JsonResponse({'error':'چیدمان معتبر نیست؛ اندازه و نوع نمودار را از گزینه‌های موجود انتخاب کنید.'},status=400)
    conflict={'error':'این داشبورد در پنجره دیگری تغییر کرده است. صفحه را تازه کنید؛ تغییرات ذخیره‌نشده شما ارسال نمی‌شوند.'}
    if row:
        changed=PersonalDashboard.objects.filter(pk=row.pk,user=request.user,revision=revision).update(widgets=widgets,title=title.strip(),revision=revision+1,updated_at=timezone.now())
        if not changed: return JsonResponse(conflict,status=409)
    else:
        if revision!=0: return JsonResponse(conflict,status=409)
        try:
            with transaction.atomic(): PersonalDashboard.objects.create(user=request.user,key=key,widgets=widgets,revision=1)
        except IntegrityError: return JsonResponse(conflict,status=409)
    return JsonResponse({'revision':revision+1,'widgets':widgets})


@operator_required
def shared_dashboard(request,key):
    row=get_object_or_404(DashboardPublication,key=key,key__startswith='custom-',enabled=True)
    return render(request,'dashboards/detail.html',{'dashboard':row,'widgets':chart_data(request.user,row.widgets),'shared':True,'mode':'personal-dashboards'})


@require_http_methods(['POST'])
def publish(request,key):
    if not member(request.user) or not can_manage(request.user,request):
        return JsonResponse({'error':'انتشار چیدمان مشترک فقط برای ادمین مجاز است.'},status=403)
    try:
        if len(request.body)>1000: raise ValueError()
        data=json.loads(request.body)
        expected=data['publication_revision']; revision=data['revision']; enabled=data.get('enabled',True)
        if type(expected) is not int or expected<0 or type(revision) is not int or type(enabled) is not bool: raise ValueError()
    except (ValueError,KeyError,TypeError,UnicodeDecodeError):
        return JsonResponse({'error':'درخواست انتشار معتبر نیست.'},status=400)
    draft=get_object_or_404(PersonalDashboard,user=request.user,key=key)
    if draft.revision!=revision:return JsonResponse({'error':'پیش‌نویس تغییر کرده است؛ صفحه را تازه کنید.'},status=409)
    current=DashboardPublication.objects.filter(key=key).first()
    values={'title':draft.title,'widgets':draft.widgets,'enabled':enabled,'publisher':request.user,'updated_at':timezone.now()}
    if current:
        changed=DashboardPublication.objects.filter(pk=current.pk,revision=expected).update(**values,revision=expected+1)
        if not changed:return JsonResponse({'error':'نسخه مشترک توسط ادمین دیگری تغییر کرده است؛ صفحه را تازه کنید.'},status=409)
    else:
        if expected!=0:return JsonResponse({'error':'نسخه انتشار تغییر کرده است.'},status=409)
        try:
            with transaction.atomic():DashboardPublication.objects.create(key=key,**values)
        except IntegrityError:return JsonResponse({'error':'انتشار هم‌زمان انجام شده است؛ صفحه را تازه کنید.'},status=409)
    return JsonResponse({'publication_revision':expected+1,'published':enabled})
