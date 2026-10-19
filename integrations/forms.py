from config.dates import PersianDateField
import uuid
from django import forms
from .models import SystemSettings, ModuleSettings, CRMView, CaseAction
from .client import validate_connection, CRMError

class ConfirmedForm(forms.ModelForm):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(label='ذخیره این تنظیمات را تأیید می‌کنم.', help_text='انتخاب گزینه‌ها به‌تنهایی اثری ندارد؛ تغییر پس از ذخیره اعمال می‌شود.')

class SystemForm(ConfirmedForm):
    class Meta:
        model = SystemSettings
        fields = ['base_url', 'organization', 'api_version', 'request_timeout', 'ai_provider', 'ai_model', 'ai_key_env']
        labels = {'base_url': 'آدرس پایه CRM', 'organization': 'نام سازمان', 'api_version': 'نسخه API', 'request_timeout': 'مهلت هر درخواست (ثانیه)', 'ai_provider': 'نام سرویس AI؛ برای مراحل بعد', 'ai_model': 'نام مدل AI؛ برای مراحل بعد', 'ai_key_env': 'نام متغیر محیطی کلید AI'}
        help_texts = {'base_url': 'اتصال مشترک همه ماژول‌ها؛ فقط میزبان مجاز سرور پذیرفته می‌شود.', 'organization': 'نام سازمان در مسیر CRM؛ نمونه: Main.', 'api_version': 'نسخه Web API؛ نمونه: v9.1.', 'request_timeout': 'بین ۱۰ تا ۱۲۰ ثانیه؛ کل دریافت حداکثر ۱۵ دقیقه است.', 'ai_provider': 'صرفاً ثبت ترجیح مشترک؛ هیچ درخواست AI در این نسخه ارسال نمی‌شود.', 'ai_model': 'تنظیم مشترک آینده؛ تحلیل فعلی قواعد قطعی و قابل توضیح دارد.', 'ai_key_env': 'فقط نام متغیر، نه مقدار کلید. هیچ secret در فرم یا دیتابیس ذخیره نمی‌شود.'}

    def clean(self):
        import re
        data = super().clean()
        try:
            validate_connection(data.get('base_url', ''), data.get('organization', ''), data.get('api_version', ''))
        except (CRMError, ValueError) as error:
            self.add_error('base_url', str(error))
        if not 10 <= data.get('request_timeout', 0) <= 120:
            self.add_error('request_timeout', 'عدد بین ۱۰ تا ۱۲۰ وارد کنید.')
        if not re.fullmatch(r'[A-Z][A-Z0-9_]{2,99}', data.get('ai_key_env', '')):
            self.add_error('ai_key_env', 'نام متغیر محیطی با حروف بزرگ لاتین وارد کنید؛ مقدار کلید را وارد نکنید.')
        return data

class ModuleForm(ConfirmedForm):
    action_templates = forms.CharField(label='اقدام‌های آماده', required=False, max_length=10000, widget=forms.Textarea(attrs={'rows': 5}), help_text='هر اقدام در یک خط؛ ترتیب خطوط ترتیب نمایش است. حذف یک خط آن گزینه را حذف می‌کند؛ اقدام‌های ثبت‌شده قبلی تغییر نمی‌کنند. حداکثر ۳۰ گزینه، هر گزینه ۵۰۰ نویسه.')

    def clean_action_templates(self):
        rows = list(dict.fromkeys(line.strip() for line in self.cleaned_data['action_templates'].splitlines() if line.strip()))
        if len(rows) > 30 or any(len(line) > 500 for line in rows):
            raise forms.ValidationError('حداکثر ۳۰ اقدام، هر اقدام حداکثر ۵۰۰ نویسه وارد کنید.')
        return '\n'.join(rows)

    class Meta:
        model = ModuleSettings
        fields = ['case_view', 'note_view', 'activity_view', 'page_size', 'action_templates']
        labels = {'case_view': 'View اصلی کیس‌های برنامه‌ریزی', 'note_view': 'View شواهد یادداشت؛ اختیاری', 'activity_view': 'View فعالیت‌ها؛ اختیاری', 'stale_days': 'آستانه قدمت یادداشت (روز)', 'parent_review_statuses': 'وضعیت‌های برنامه مرتبط برای بازبینی', 'page_size': 'تعداد ردیف در صفحه'}
        help_texts = {'case_view': 'فقط Viewهای موجودیت Case؛ فیلترهای خود View حفظ می‌شوند. تا تغییر صریح، انتخاب ثابت است.', 'note_view': 'فقط یادداشت‌های این View و مرتبط با کیس‌ها یا برنامه مادر تحلیل می‌شوند؛ پوشش کامل تضمین نمی‌شود.', 'activity_view': 'فعالیت‌های همین View برای شواهد موعد و اقدام استفاده می‌شوند؛ چیزی خارج از View خوانده نمی‌شود.', 'stale_days': 'قدمت یادداشت صرفاً علامت بازبینی است، نه نبود کار. بین ۱ تا ۳۶۵ روز.', 'parent_review_statuses': 'برچسب دقیق وضعیت‌ها با ویرگول جدا شود. تطبیق فقط با داده برنامه مرتبط موجود در View انجام می‌شود.', 'page_size': 'بین ۱۰ تا ۱۰۰؛ روی دریافت CRM اثری ندارد.'}

    def __init__(self, *args, scope, **kwargs):
        super().__init__(*args, **kwargs)
        catalog = CRMView.objects.filter(scope=scope).order_by('name', 'kind')
        self.fields['case_view'].queryset = catalog.filter(entity='incident')
        self.fields['case_view'].required = True
        self.fields['note_view'].queryset = catalog.filter(entity='annotation')
        self.fields['activity_view'].queryset = catalog.filter(entity__in=['task', 'activitypointer'])

    def clean(self):
        data = super().clean()
        for key, lower, upper in [('stale_days', 1, 365), ('page_size', 10, 100)]:
            if key in self.fields and not lower <= data.get(key, 0) <= upper:
                self.add_error(key, f'عدد بین {lower} تا {upper} وارد کنید.')
        return data

class ActionForm(forms.ModelForm):
    selected_preset = forms.ChoiceField(label='اقدام آماده', required=False)
    due_date = PersianDateField(label='موعد پیگیری (شمسی)', required=False)

    def __init__(self, *args, presets=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['selected_preset'].choices = [('', 'اقدام دلخواه')] + [(p,p) for p in presets]
        for name in ('title','responsible'):
            self.fields[name].required = False
        self.order_fields(['selected_preset','title','responsible','due_date','blocker','request_key','confirm'])

    def clean(self):
        data = super().clean()
        if data.get('selected_preset'):
            data['title'] = data.get('title') or data['selected_preset']
        else:
            for name in ('title','responsible','due_date'):
                if not data.get(name): self.add_error(name, 'برای اقدام دلخواه این فیلد لازم است؛ یا اقدام آماده انتخاب کنید.')
        return data

    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    confirm = forms.BooleanField(label='ثبت اقدام محلی را تأیید می‌کنم.', help_text='فقط در این برنامه ذخیره می‌شود؛ هیچ رکورد CRM تغییر نمی‌کند.')
    class Meta:
        model = CaseAction
        fields = ['title', 'responsible', 'due_date', 'blocker', 'selected_preset']
        labels = {'title': 'اقدام بعدی', 'responsible': 'مسئول پیگیری', 'due_date': 'موعد پیگیری', 'blocker': 'مانع یا پیش‌نیاز'}
        help_texts = {'title': 'اقدام روشن بر اساس شواهد کیس؛ مثلاً هماهنگی زمان نصب.', 'responsible': 'مسئول داخلی پیگیری؛ فعلاً متن آزاد است و تخصیص حساب کاربری نیست.', 'due_date': 'ورود و نمایش شمسی؛ موعد پیگیری است نه وعده رفع کیس.', 'blocker': 'مانع تأییدشده یا نیازمند بررسی را با توضیح مشخص کنید؛ از حدس قطعی پرهیز کنید.'}
        widgets = {'blocker': forms.Textarea(attrs={'rows': 3})}

class CompleteForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    result = forms.CharField(label='نتیجه اقدام', max_length=3000, widget=forms.Textarea(attrs={'rows': 4}), help_text='چه نتیجه‌ای حاصل شد؟ پایان پیگیری به معنی رفع کیس نزد مشتری نیست.')
    confirm = forms.BooleanField(label='اتمام این اقدام را تأیید می‌کنم.', help_text='فقط وضعیت اقدام محلی تغییر می‌کند؛ کیس CRM باز یا بسته نمی‌شود.')
