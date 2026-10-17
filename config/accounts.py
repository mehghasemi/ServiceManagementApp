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
