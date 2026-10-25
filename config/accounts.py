from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import render, redirect
from integrations.models import SettingsAudit


class NetworkUserForm(UserCreationForm):
    role = forms.ChoiceField(label='دسترسی', choices=[('reader', 'مشاهده گزارش‌ها'), ('operator', 'کارشناس: گزارش، بازخوانی و اقدام'), ('manager', 'مدیر: تنظیمات، معیارها و کاربران')])
    confirm = forms.BooleanField(label='ایجاد حساب و اعطای این دسترسی را تأیید می‌کنم.')

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ('username', 'first_name', 'last_name')


def network_login(request):
    # Separate from local-preview: there is no passwordless LAN path.
    form = AuthenticationForm(request, data=request.POST if request.method == 'POST' else None)
    key = 'network-login:' + request.META.get('REMOTE_ADDR', '')
    status = 200
    if request.method == 'POST':
        attempts = cache.get(key, 0)
        if attempts >= 10:
            form.add_error(None, 'تلاش‌های ناموفق زیاد است؛ پنج دقیقه بعد دوباره تلاش کنید.')
            status = 429
        elif form.is_valid():
            user = form.get_user()
            if user.username == 'local-preview' or not (user.is_staff or user.groups.filter(name='service-readers').exists()):
                form.add_error(None, 'این حساب مجوز ورود شبکه‌ای ندارد.')
            else:
                cache.delete(key)
                login(request, user)
                return redirect('home')
        else:
            cache.set(key, attempts+1, 300)
    return render(request, 'network-login.html', {'form': form, 'crm_mode': True}, status=status)


@login_required
def users(request):
    local_admin = not settings.SERVICE_LAN and request.user.is_staff and request.META.get('REMOTE_ADDR') in ('127.0.0.1', '::1')
    if not (local_admin or request.user.is_superuser):
        return HttpResponseForbidden('فقط مدیر می‌تواند حساب شبکه‌ای ایجاد کند.')
    form = NetworkUserForm(request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            role = form.cleaned_data['role']
            user.is_staff = role in ('operator', 'manager')
            user.is_superuser = role == 'manager'
            user.save()
            if role == 'reader':
                user.groups.add(Group.objects.get_or_create(name='service-readers')[0])
            SettingsAudit.objects.create(actor=request.user, area='network-user', before={}, after={'id': user.pk, 'username': user.username, 'role': role})
        messages.success(request, 'حساب ساخته شد. ورود از صفحه شبکه با همین نام کاربری و رمز انجام می‌شود.')
        return redirect('network-users')
    rows = get_user_model().objects.exclude(username='local-preview').order_by('username')
    return render(request, 'network-users.html', {'form': form, 'accounts': rows, 'crm_mode': True})


def can_manage(user, request):
    return user.is_superuser or (not settings.SERVICE_LAN and user.is_staff and request.META.get('REMOTE_ADDR') in ('127.0.0.1', '::1'))


class EditAccountForm(forms.ModelForm):
    role = forms.ChoiceField(label='دسترسی', choices=NetworkUserForm.base_fields['role'].choices)
    new_password = forms.CharField(label='رمز جدید؛ خالی یعنی بدون تغییر', required=False, widget=forms.PasswordInput)
    confirm_password = forms.CharField(label='تکرار رمز جدید', required=False, widget=forms.PasswordInput)
    class Meta:
        model = get_user_model()
        fields = ['username', 'first_name', 'last_name', 'is_active']
        labels = {'is_active': 'حساب فعال است'}
    def clean(self):
        data = super().clean()
        if data.get('new_password') != data.get('confirm_password'):
            self.add_error('confirm_password', 'تکرار رمز یکسان نیست.')
        return data


@login_required
def edit_user(request, pk):
    from django.shortcuts import get_object_or_404
    if not can_manage(request.user, request):
        return HttpResponseForbidden('فقط مدیر اجازه ویرایش کاربران را دارد.')
    target = get_object_or_404(get_user_model().objects.exclude(username='local-preview'), pk=pk)
    role = 'manager' if target.is_superuser else 'operator' if target.is_staff else 'reader'
    form = EditAccountForm(request.POST if request.method == 'POST' else None, instance=target, initial={'role':role})
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            # Lock administrator set before checking last-active-admin invariant.
            admins = list(get_user_model().objects.select_for_update().filter(is_superuser=True,is_active=True).values_list('pk',flat=True))
            data = form.cleaned_data
            removing = data['role'] != 'manager' or not data['is_active']
            if removing and (target.pk == request.user.pk or (target.pk in admins and len(admins) == 1)):
                form.add_error(None, 'دسترسی حساب خودتان یا آخرین مدیر فعال را نمی‌توانید حذف کنید.')
            else:
                obj = form.save(commit=False)
                obj.is_staff = data['role'] in ('manager','operator')
                obj.is_superuser = data['role'] == 'manager'
                if data['new_password']:
                    obj.set_password(data['new_password'])
                obj.save()
                readers = Group.objects.get_or_create(name='service-readers')[0]
                if data['role'] == 'reader': obj.groups.add(readers)
                else: obj.groups.remove(readers)
                SettingsAudit.objects.create(actor=request.user,area='network-user-edit',after={'id':obj.pk,'role':data['role'],'active':obj.is_active,'password_changed':bool(data['new_password'])})
                if obj.pk == request.user.pk and data['new_password']:
                    from django.contrib.auth import update_session_auth_hash
                    update_session_auth_hash(request,obj)
                messages.success(request,'تغییرات کاربر ذخیره شد.')
                return redirect('network-users')
    return render(request,'account-edit.html',{'form':form,'heading':'ویرایش کاربر','crm_mode':True})


@login_required
def change_password(request):
    from django.contrib.auth.forms import PasswordChangeForm
    from django.contrib.auth import update_session_auth_hash
    form = PasswordChangeForm(request.user, request.POST if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request,user)
        SettingsAudit.objects.create(actor=user,area='password-change',after={'id':user.pk})
        messages.success(request,'رمز شما تغییر کرد.')
        return redirect('home')
    return render(request,'account-edit.html',{'form':form,'heading':'تغییر رمز من','crm_mode':True})
