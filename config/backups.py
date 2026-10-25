"""Admin-only signed settings backup; business records are deliberately excluded."""
import json
import secrets
from pathlib import Path
from datetime import datetime
from django import forms
from django.conf import settings
from django.core import serializers, signing
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from integrations.models import SystemSettings, CRMView, ModuleSettings, EvaluationRule, SettingsAudit, SyncJob
from .accounts import can_manage

MODELS = (SystemSettings, CRMView, ModuleSettings, EvaluationRule)

def config_path():
    return Path(settings.DATABASES['default']['NAME']).parent / (Path(settings.DATABASES['default']['NAME']).stem + '-backup-config.json')

def load_config():
    p = config_path()
    if p.exists(): return json.loads(p.read_text(encoding='utf-8'))
    return {'directory':str(p.parent / 'settings-backups'), 'key':secrets.token_urlsafe(48)}

def export_settings(key):
    rows = [obj for model in MODELS for obj in model.objects.all().order_by('pk')]
    data = {'schema':1, 'records':json.loads(serializers.serialize('json',rows))}
    return signing.dumps(data,key=key,salt='service-settings-v1',compress=True)

def restore_settings(token,key,actor):
    data = signing.loads(token,key=key,salt='service-settings-v1')
    allowed = {model._meta.label_lower for model in MODELS}
    if data.get('schema') != 1 or not isinstance(data.get('records'),list) or len(data['records']) > 10000:
        raise ValueError('ساختار پشتیبان معتبر نیست.')
    if any(row.get('model') not in allowed for row in data['records']):
        raise ValueError('این فایل شامل داده غیرمجاز است.')
    with transaction.atomic():
        if SyncJob.objects.filter(status__in=['running','queued']).exists():
            raise ValueError('ابتدا منتظر پایان دریافت CRM بمانید.')
        for obj in serializers.deserialize('json',json.dumps(data['records'])):
            item=obj.object
            if isinstance(item,SystemSettings):
                from integrations.client import validate_connection
                validate_connection(item.base_url,item.organization,item.api_version)
            if hasattr(item,'revision'):
                old=type(item).objects.filter(pk=item.pk).first()
                item.revision=max(item.revision,old.revision if old else 0)+1
            item._state.adding = not type(item).objects.filter(pk=item.pk).exists()
            item.full_clean()
            item.save()
        SettingsAudit.objects.create(actor=actor,area='settings-restore',after={'records':len(data['records'])})

class BackupForm(forms.Form):
    directory=forms.CharField(label='مسیر پوشه پشتیبان روی سرور',max_length=1000,help_text='مسیر مطلق روی رایانه میزبان؛ حساب اجراکننده برنامه باید اجازه نوشتن داشته باشد.')
    def clean_directory(self):
        value=Path(self.cleaned_data['directory']).expanduser()
        if not value.is_absolute(): raise forms.ValidationError('مسیر کامل پوشه را وارد کنید.')
        root=Path(settings.BASE_DIR).resolve()
        if value.resolve().is_relative_to(root) and not value.resolve().is_relative_to(root/'private'):
            raise forms.ValidationError('پشتیبان نباید داخل کد عمومی پروژه ذخیره شود؛ پوشه private یا مسیری مستقل انتخاب کنید.')
        return str(value)

class RestoreForm(forms.Form):
    backup=forms.FileField(label='فایل پشتیبان تنظیمات')
    confirm=forms.BooleanField(label='جایگزینی تنظیمات موجود با مقادیر این پشتیبان را تأیید می‌کنم.')

@login_required
def backups(request):
    if not can_manage(request.user,request): return HttpResponseForbidden('فقط مدیر اجازه پشتیبان‌گیری و بازیابی دارد.')
    config=load_config()
    form=BackupForm(request.POST if request.method=='POST' and request.POST.get('operation')=='backup' else None,initial={'directory':config['directory']})
    restore=RestoreForm(request.POST if request.method=='POST' and request.POST.get('operation')=='restore' else None,request.FILES or None)
    try:
        if request.method=='POST' and request.POST.get('operation')=='backup' and form.is_valid():
            directory=Path(form.cleaned_data['directory']);directory.mkdir(parents=True,exist_ok=True)
            config['directory']=str(directory)
            config_path().write_text(json.dumps(config),encoding='utf-8')
            name='settings-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.smbak'
            (directory/name).write_text(export_settings(config['key']),encoding='utf-8')
            SettingsAudit.objects.create(actor=request.user,area='settings-backup',after={'file':name})
            messages.success(request,'پشتیبان تنظیمات ذخیره شد: '+str(directory/name));return redirect('settings-backups')
        if request.method=='POST' and request.POST.get('operation')=='restore' and restore.is_valid():
            file=restore.cleaned_data['backup']
            if file.size>5_000_000: raise ValueError('حداکثر حجم فایل ۵ مگابایت است.')
            # Before restoring, always retain a recoverable settings snapshot.
            directory=Path(config['directory']);directory.mkdir(parents=True,exist_ok=True)
            (directory/('before-restore-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.smbak')).write_text(export_settings(config['key']),encoding='utf-8')
            restore_settings(file.read().decode('utf-8'),config['key'],request.user)
            messages.success(request,'تنظیمات بازیابی شد؛ موارد جدیدی که در پشتیبان نبودند حفظ شدند.');return redirect('settings-backups')
    except Exception as error:
        from django.core.exceptions import ValidationError
        if isinstance(error,(ValueError,ValidationError)): messages.error(request,str(error))
        else: messages.error(request,'فایل معتبر نیست یا دسترسی پوشه کافی نیست؛ بازیابی اعمال نشد.')
    return render(request,'settings-backups.html',{'form':form,'restore':restore,'crm_mode':True})
