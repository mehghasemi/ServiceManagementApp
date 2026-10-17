import json
import uuid
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout, get_user_model
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import DatabaseError
from django.db.models import Q
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from .forms import ProgramForm, FollowUpForm
from .models import Program
from .services import allowed, save_program, record_followup, Conflict

def welcome(request):
    if settings.SERVICE_LAN:
        from config.accounts import network_login
        return network_login(request)
    if request.method == 'POST':
        user = get_object_or_404(get_user_model(), username='local-preview', is_active=True)
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('home')
    return render(request, 'welcome.html', {'crm_mode': True})

def sign_out(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])
    logout(request)
    return redirect('welcome')

@login_required
def board(request, mode='today'):
    today = timezone.localdate()
    base = allowed(request.user)
    attention = Q(status='draft') | Q(owner='') | Q(next_step='') | Q(due_date__isnull=True) | Q(due_date__lt=today)
    stats = {'total': base.count(), 'due': base.filter(due_date__lte=today).count(), 'attention': base.filter(attention).count(), 'verify': base.filter(status='verify').count()}
    rows = base
    if mode == 'today':
        rows = rows.filter(due_date__lte=today)
    elif mode == 'decisions':
        rows = rows.filter(attention)
    query = request.GET.get('q', '').strip()[:100]
    status = request.GET.get('status', '')
    if query:
        rows = rows.filter(Q(title__icontains=query) | Q(customer__icontains=query) | Q(owner__icontains=query))
    if status in Program.Status.values:
        rows = rows.filter(status=status)
    sorting = request.GET.get('sort', 'due')
    order = {'due': 'due_date', 'recent': '-updated_at', 'customer': 'customer'}.get(sorting, 'due_date')
    rows = rows.order_by(order, 'pk')
    page = Paginator(rows, 8).get_page(request.GET.get('page'))
    titles = {'today': ('کارهای امروز', 'هر پیگیری، یک قدم به نتیجه نزدیک‌تر.'), 'programs': ('برنامه‌های مشتریان', 'یک مشتری، یک اقدام مشترک؛ نتیجه مستقل برای هر کیس.'), 'decisions': ('نیازمند تصمیم', 'ابهام‌ها را به اقدام مشخص تبدیل کنیم.')}
    return render(request, 'board.html', {'mode': mode, 'title': titles[mode][0], 'subtitle': titles[mode][1], 'stats': stats, 'page': page, 'query': query, 'status_filter': status, 'sort': sorting, 'statuses': Program.Status.choices})

@login_required
def detail(request, pk):
    program = get_object_or_404(allowed(request.user), pk=pk)
    return render(request, 'detail.html', {'program': program, 'mode': 'programs'})

@login_required
def edit(request, pk=None):
    program = get_object_or_404(allowed(request.user), pk=pk) if pk else None
    form = ProgramForm(request.POST or None, instance=program, initial={'revision': program.revision if program else 0})
    response_status = 200
    if request.method == 'POST' and form.is_valid():
        try:
            saved = save_program(request.user, form.cleaned_data, pk)
            messages.success(request, 'برنامه ذخیره شد. اطلاعات CRM تغییری نکرده است.')
            return redirect('detail', pk=saved.pk)
        except Conflict as error:
            form.add_error(None, str(error))
            response_status = 409
        except DatabaseError:
            form.add_error(None, 'ذخیره‌سازی انجام نشد. ورودی شما حفظ شده؛ دوباره تلاش کنید. شناسه پیگیری: ' + uuid.uuid4().hex[:10])
            response_status = 503
    return render(request, 'form.html', {'form': form, 'program': program, 'mode': 'programs', 'title': 'ویرایش برنامه' if pk else 'برنامه جدید', 'back': program.pk if program else None}, status=response_status)

@login_required
def followup(request, pk):
    program = get_object_or_404(allowed(request.user), pk=pk)
    form = FollowUpForm(request.POST or None, initial={'revision': program.revision, 'next_step': program.next_step, 'due_date': program.due_date})
    response_status = 200
    if request.method == 'POST' and form.is_valid():
        try:
            record_followup(request.user, pk, form.cleaned_data)
            messages.success(request, 'پیگیری ثبت شد و اقدام بعدی به‌روز شد؛ نتیجه کیس‌ها تغییر نکرد.')
            return redirect('detail', pk=pk)
        except Conflict as error:
            form.add_error(None, str(error))
            response_status = 409
        except DatabaseError:
            form.add_error(None, 'ذخیره پیگیری انجام نشد؛ متن حفظ شده است. دوباره تلاش کنید. شناسه پیگیری: ' + uuid.uuid4().hex[:10])
            response_status = 503
    return render(request, 'form.html', {'form': form, 'program': program, 'mode': 'programs', 'title': 'ثبت پیگیری', 'back': pk}, status=response_status)

@login_required
def versions(request):
    data = json.loads((settings.BASE_DIR / 'CHANGELOG.json').read_text(encoding='utf-8-sig'))
    return render(request, 'versions.html', {'history': data})

def bad_request(request, exception=None):
    return render(request, 'error.html', {'title': 'درخواست معتبر نیست', 'explanation': 'صفحه را دوباره باز کنید و اطلاعات فرم را بررسی کنید.'}, status=400)

def forbidden(request, exception=None):
    return render(request, 'error.html', {'title': 'دسترسی امکان‌پذیر نیست', 'explanation': 'مجوز یا اعتبار فرم کافی نیست. صفحه را تازه کنید و دوباره وارد محیط نمونه شوید.'}, status=403)

def not_found(request, exception=None):
    return render(request, 'error.html', {'title': 'این مورد در دسترس نیست', 'explanation': 'به فهرست برنامه‌های مجاز برگردید و مورد را دوباره انتخاب کنید.'}, status=404)

def server_error(request):
    return render(request, 'error.html', {'title': 'عملیات انجام نشد', 'explanation': 'کمی بعد دوباره تلاش کنید. شناسه پیگیری: ' + uuid.uuid4().hex[:10]}, status=500)
