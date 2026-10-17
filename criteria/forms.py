import uuid
from django import forms
from integrations.models import EvaluationRule
from .engine import METRICS, OPERATORS, ALLOWED


class SelectionForm(forms.Form):
    enabled = forms.MultipleChoiceField(label='معیارهای فعال', required=False, widget=forms.CheckboxSelectMultiple)
    revision = forms.IntegerField(widget=forms.HiddenInput)
    confirm = forms.BooleanField(label='اعمال معیارهای انتخاب‌شده را تأیید می‌کنم.')

    def __init__(self, *args, rules, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['enabled'].choices = [(str(r.pk), r.label) for r in rules]


class RuleForm(forms.ModelForm):
    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    revision = forms.IntegerField(widget=forms.HiddenInput, initial=0)
    target_value = forms.CharField(label='مقدار / آستانه / فهرست عبارت‌ها', max_length=1500,
        help_text='عدد برای شاخص عددی؛ بله یا خیر برای شاخص منطقی؛ هر وضعیت یا عبارت متنی در یک خط. مقادیر متنی تطبیق دقیق دارند مگر عملگر «شامل» انتخاب شود.', widget=forms.Textarea(attrs={'rows': 3}))
    confirm = forms.BooleanField(label='ذخیره این معیار را تأیید می‌کنم.')

    class Meta:
        model = EvaluationRule
        fields = ['label', 'enabled', 'purpose', 'metric', 'operator', 'priority', 'active_only', 'closure_candidate', 'grouping', 'min_count', 'action_title', 'impact']
        labels = {'label': 'نام معیار', 'enabled': 'معیار فعال باشد', 'purpose': 'کاربرد', 'metric': 'شاخص مبنا', 'operator': 'شرط مقایسه', 'priority': 'سطح اهمیت (۱ مهم‌ترین)', 'active_only': 'فقط رکوردهای جاری', 'closure_candidate': 'تطبیق این معیار، نامزد بررسی تأیید رفع باشد', 'grouping': 'مبنای تجمیع اقدام مشترک', 'min_count': 'حداقل رکورد برای پیشنهاد مشترک', 'action_title': 'عنوان اقدام پیشنهادی', 'impact': 'اثر مورد انتظار اقدام'}
        help_texts = {'priority': 'از ۱ تا ۹؛ رتبه نمایش جداگانه و از ۱ شروع می‌شود.', 'active_only': 'پروژه جاری طبق وضعیت‌های خاتمه‌یافته تنظیمات؛ کیس جاری طبق statecode CRM. نبود داده وضعیت، نامشخص محسوب می‌شود.', 'closure_candidate': 'فقط قرینه‌ای برای بررسی انسانی است؛ هرگز مجوز بستن خودکار نیست.', 'min_count': 'حداقل تعداد کیس منطبق با همین معیار در یک گروه، از ۲ تا ۱۰۰۰۰.', 'grouping': 'شناسه دقیق مشتری لازم است؛ در حالت مشتری و برنامه، شناسه هر دو لازم است.'}
        widgets = {'impact': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, module, **kwargs):
        self.module = module
        super().__init__(*args, **kwargs)
        self.fields['purpose'].widget = forms.Select(choices=[('attention', 'نیازمند رسیدگی')] + ([('opportunity', 'فرصت اقدام مشترک')] if module == 'planning' else []))
        self.fields['metric'].widget = forms.Select(choices=[(k, v[0]) for k, v in METRICS[module].items()])
        self.fields['operator'].widget = forms.Select(choices=list(OPERATORS.items()))
        self.fields['grouping'].widget = forms.Select(choices=[('customer_program', 'مشتری و برنامه مشترک'), ('customer', 'مشتری / مرکز مشترک')])
        if self.instance.pk:
            value = self.instance.value
            self.initial['target_value'] = '\n'.join(str(v) for v in value) if isinstance(value, list) else ('بله' if value else 'خیر') if isinstance(value, bool) else str(value)
            self.initial['revision'] = self.instance.revision

    def clean(self):
        data = super().clean()
        metric = data.get('metric')
        kind = METRICS[self.module].get(metric, ('', None))[1]
        if not kind:
            self.add_error('metric', 'شاخص برای این زیرسیستم معتبر نیست.')
            return data
        if data.get('operator') not in ALLOWED[kind]:
            self.add_error('operator', 'عملگر با نوع شاخص سازگار نیست.')
        raw = data.get('target_value', '').strip()
        try:
            if kind == 'number':
                value = int(raw)
                if not -100000 <= value <= 100000:
                    raise ValueError
            elif kind == 'bool':
                if raw not in ('بله', 'خیر', 'true', 'false'):
                    raise ValueError
                value = raw in ('بله', 'true')
            else:
                value = [s.strip() for s in raw.replace('،', '\n').replace(',', '\n').splitlines() if s.strip()]
                if not value or len(value) > 50:
                    raise ValueError
            self.instance.value = value
        except ValueError:
            self.add_error('target_value', 'مقدار با نوع شاخص سازگار نیست یا از محدوده مجاز خارج است.')
        if not 1 <= data.get('priority', 0) <= 9:
            self.add_error('priority', 'عدد بین ۱ تا ۹ وارد کنید.')
        if not 2 <= data.get('min_count', 0) <= 10000:
            self.add_error('min_count', 'عدد بین ۲ تا ۱۰۰۰۰ وارد کنید.')
        if data.get('purpose') not in (['attention', 'opportunity'] if self.module == 'planning' else ['attention']):
            self.add_error('purpose', 'کاربرد معیار معتبر نیست.')
        if data.get('grouping') not in ('customer', 'customer_program'):
            self.add_error('grouping', 'مبنای گروه‌بندی معتبر نیست.')
        if data.get('purpose') == 'opportunity' and not data.get('action_title'):
            self.add_error('action_title', 'برای فرصت اقدام مشترک، عنوان اقدام لازم است.')
        if data.get('closure_candidate') and (self.module != 'planning' or data.get('purpose') != 'attention'):
            self.add_error('closure_candidate', 'این گزینه فقط برای معیار رسیدگی کیس است.')
        return data

    def save(self, commit=True):
        if not self.instance.code:
            self.instance.code = self.cleaned_data['request_key'].hex
        return super().save(commit=commit)
