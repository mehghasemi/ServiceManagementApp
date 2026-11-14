import uuid
import json
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
    expression_data = forms.CharField(required=False, max_length=30000, widget=forms.HiddenInput)
    time_statuses = forms.CharField(label='وضعیت‌های معیار زمانی؛ هر مقدار در یک خط', required=False, widget=forms.Textarea(attrs={'rows': 2}), help_text='خالی یعنی همه وضعیت‌ها. ماندگاری وضعیت نیازمند تاریخ ورود معتبر است؛ پیام مشتری نیازمند تشخیص نویسنده و دریافت کامل پیگیری‌هاست. نبود این داده‌ها نتیجه نامشخص می‌دهد.')
    time_calendar = forms.ChoiceField(label='مبنای روزهای معیار زمانی', required=False, initial='calendar', choices=[('calendar','روز تقویمی'),('working','روز کاری')])
    time_weekends = forms.MultipleChoiceField(label='روزهای تعطیل هفتگی', required=False, initial=['4'], choices=[('5','شنبه'),('6','یکشنبه'),('0','دوشنبه'),('1','سه‌شنبه'),('2','چهارشنبه'),('3','پنجشنبه'),('4','جمعه')], widget=forms.CheckboxSelectMultiple)
    time_holidays = forms.CharField(label='تعطیلات موردی شمسی؛ هر تاریخ در یک خط', required=False, widget=forms.Textarea(attrs={'rows': 2}), help_text='مثلاً ۱۴۰۵/۰۱/۰۱؛ تعطیلات رسمی خودکار اضافه نمی‌شوند.')
    time_responses = forms.MultipleChoiceField(label='چه چیزی پیگیری معتبر پیام مشتری است؟', required=False, initial=['staff_note'], choices=[('staff_note','پاسخ کارشناس'),('phone_call','تماس مرتبط'),('local_action','پیگیری محلی انجام‌شده'),('status_change','تغییر وضعیت')], widget=forms.CheckboxSelectMultiple)

    request_key = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    revision = forms.IntegerField(widget=forms.HiddenInput, initial=0)
    target_value = forms.CharField(label='مقدار / آستانه / فهرست عبارت‌ها', max_length=1500,
        help_text='عدد برای شاخص عددی؛ بله یا خیر برای شاخص منطقی؛ هر وضعیت یا عبارت متنی در یک خط. مقادیر متنی تطبیق دقیق دارند مگر عملگر «شامل» انتخاب شود.', widget=forms.Textarea(attrs={'rows': 3}))
    confirm = forms.BooleanField(label='ذخیره این معیار را تأیید می‌کنم.')

    class Meta:
        model = EvaluationRule
        fields = ['label', 'enabled', 'dashboard', 'purpose', 'attention_group', 'metric', 'operator', 'priority', 'active_only', 'closure_candidate', 'grouping', 'min_count', 'action_title', 'impact']
        labels = {'dashboard': 'داشبورد مرتبط', 'label': 'نام معیار', 'enabled': 'معیار فعال باشد', 'purpose': 'کاربرد', 'attention_group': 'گروه رسیدگی', 'metric': 'شاخص مبنا', 'operator': 'شرط مقایسه', 'priority': 'سطح اهمیت (۱ مهم‌ترین)', 'active_only': 'فقط رکوردهای جاری', 'closure_candidate': 'تطبیق این معیار، نامزد بررسی تأیید رفع باشد', 'grouping': 'مبنای تجمیع اقدام مشترک', 'min_count': 'حداقل رکورد برای پیشنهاد مشترک', 'action_title': 'عنوان اقدام پیشنهادی', 'impact': 'اثر مورد انتظار اقدام'}
        help_texts = {'attention_group': 'دلیل رسیدگی را در کدام گروه مدیریتی نمایش دهیم؟ این انتخاب شرط، اهمیت یا نتیجه معیار را تغییر نمی‌دهد؛ برای فرصت اقدام مشترک کاربرد ندارد.', 'priority': 'از ۱ تا ۹؛ رتبه نمایش جداگانه و از ۱ شروع می‌شود.', 'active_only': 'پروژه جاری طبق وضعیت‌های خاتمه‌یافته تنظیمات؛ کیس جاری طبق statecode CRM. نبود داده وضعیت، نامشخص محسوب می‌شود.', 'closure_candidate': 'فقط قرینه‌ای برای بررسی انسانی است؛ هرگز مجوز بستن خودکار نیست.', 'min_count': 'حداقل تعداد کیس منطبق با همین معیار در یک گروه، از ۲ تا ۱۰۰۰۰.', 'grouping': 'شناسه دقیق مشتری لازم است؛ در حالت مشتری و برنامه، شناسه هر دو لازم است.'}
        widgets = {'impact': forms.Textarea(attrs={'rows': 3})}

    def __init__(self, *args, module, **kwargs):
        self.module = module
        super().__init__(*args, **kwargs)
        self.fields['purpose'].widget = forms.Select(choices=[('attention', 'نیازمند رسیدگی')] + ([('opportunity', 'فرصت اقدام مشترک'), ('upgrade_ready', 'قابل رفع با ارتقا؛ فرض مدیریتی')] if module == 'planning' else [('completed', 'بازدید انجام‌شده'), ('pending', 'بازدید باقی‌مانده'), ('upgrade_program', 'شناسایی برنامه ارتقا')] if module == 'backlogs' else []))
        self.fields['metric'].widget = forms.Select(choices=[('expression', 'معیار ترکیبی؛ ساخت شرط‌های دلخواه')] + [(k, v[0]) for k, v in METRICS[module].items()])
        self.fields['operator'].widget = forms.Select(choices=list(OPERATORS.items()))
        self.fields['grouping'].widget = forms.Select(choices=[('customer_program', 'مشتری و برنامه مشترک'), ('customer', 'مشتری / مرکز مشترک')])
        if module == 'projects':
            self.fields['dashboard'].widget = forms.HiddenInput()
        elif module == 'backlogs':
            self.fields['dashboard'].choices = [('', 'عمومی'), ('upgrade', 'ارتقا'), ('onsite', 'مراجعه حضوری'), ('periodic', 'بازدید دوره‌ای')]
        compound = (self.data.get('metric') if self.is_bound else self.instance.metric) == 'expression'
        if compound:
            self.fields['target_value'].required = False
        if self.is_bound and self.data.get('intent') == 'preview':
            self.fields['confirm'].required = False
        if not self.is_bound and not self.instance.pk:
            self.initial['metric'] = 'expression'
            self.initial['operator'] = 'eq'
        if self.instance.metric == 'expression':
            self.initial['expression_data'] = json.dumps(self.instance.value, ensure_ascii=False)
        if self.instance.pk:
            value = self.instance.value
            self.initial['target_value'] = '\n'.join(str(v) for v in value) if isinstance(value, list) else ('بله' if value else 'خیر') if isinstance(value, bool) else str(value)
            self.initial['revision'] = self.instance.revision
            from .temporal import METRICS as temporal_metrics
            if self.instance.metric in temporal_metrics and isinstance(value, dict):
                self.initial.update(target_value=value.get('days', 30), time_statuses='\n'.join(value.get('statuses', [])), time_calendar=value.get('calendar','calendar'), time_weekends=[str(n) for n in value.get('weekends',[4])], time_responses=value.get('responses',[]))
                import jdatetime
                from datetime import date
                self.initial['time_holidays']='\n'.join(jdatetime.date.fromgregorian(date=date.fromisoformat(v)).strftime('%Y/%m/%d') for v in value.get('holidays',[]))


    @property
    def ui_groups(self):
        groups=[('هدف معیار',('label','enabled','dashboard','purpose','attention_group')),('شرط بررسی',('metric','operator','target_value','priority','active_only','closure_candidate')),('تنظیم معیار زمانی؛ فقط برای شاخص‌های زمانی',('time_statuses','time_calendar','time_weekends','time_holidays','time_responses')),('اقدام پیشنهادی',('grouping','min_count','action_title','impact')),('تأیید',('confirm',))]
        return [(title,[self[name] for name in names if not self[name].is_hidden]) for title,names in groups]

    def clean(self):
        data = super().clean()
        metric = data.get('metric')
        allowed_dashboards = {'planning': ('', 'upgrade', 'onsite'), 'backlogs': ('', 'upgrade', 'onsite', 'periodic'), 'projects': ('',)}
        if data.get('dashboard', '') not in allowed_dashboards[self.module]:
            self.add_error('dashboard', 'داشبورد برای این ماژول معتبر نیست.')
        kind = 'expression' if metric == 'expression' else METRICS[self.module].get(metric, ('', None))[1]
        if not kind:
            self.add_error('metric', 'شاخص برای این زیرسیستم معتبر نیست.')
            return data
        if kind != 'expression' and data.get('operator') not in ALLOWED[kind]:
            self.add_error('operator', 'عملگر با نوع شاخص سازگار نیست.')
        raw = data.get('target_value', '').strip()
        try:
            if kind == 'expression':
                from .expressions import validate
                try:
                    value = json.loads(data.get('expression_data') or '{}')
                    value = validate(value, self.module)
                except (ValueError, TypeError, KeyError, RecursionError) as error:
                    self.add_error('expression_data', 'شرط‌های ترکیبی را کامل کنید؛ فیلد، نوع مقدار و محدودیت ۴ سطح و ۴۰ جزء را بررسی کنید.')
                    value = {}
                if data.get('operator') != 'eq': self.add_error('operator', 'عملگر معیار ترکیبی معتبر نیست.')
                if data.get('purpose') != 'attention': self.add_error('purpose', 'معیار ترکیبی فعلاً برای نیازمند رسیدگی است.')
            elif kind == 'number':
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
        if data.get('purpose') not in (['attention', 'opportunity', 'upgrade_ready'] if self.module == 'planning' else ['attention', 'completed', 'pending', 'upgrade_program'] if self.module == 'backlogs' else ['attention']):
            self.add_error('purpose', 'کاربرد معیار معتبر نیست.')
        if data.get('grouping') not in ('customer', 'customer_program'):
            self.add_error('grouping', 'مبنای گروه‌بندی معتبر نیست.')
        if data.get('purpose') == 'opportunity' and not data.get('action_title'):
            self.add_error('action_title', 'برای فرصت اقدام مشترک، عنوان اقدام لازم است.')
        if data.get('closure_candidate') and (self.module != 'planning' or data.get('purpose') != 'attention'):
            self.add_error('closure_candidate', 'این گزینه فقط برای معیار رسیدگی کیس است.')
        from .temporal import METRICS as temporal_metrics, validate
        if metric in temporal_metrics:
            if data.get('purpose') != 'attention': self.add_error('purpose','معیار زمانی فقط برای نیازمند رسیدگی است.')
            if data.get('operator') not in ('gt','gte'): self.add_error('operator','برای معیار زمانی «بیشتر از» یا «بیشتر یا مساوی» انتخاب کنید.')
            try:
                from planning.reporting.engine import day as parse_day
                holidays=[]
                for line in data.get('time_holidays','').splitlines():
                    if not line.strip(): continue
                    stamp=parse_day(line.strip())
                    if not stamp: raise ValueError('تاریخ تعطیل معتبر نیست.')
                    holidays.append(stamp.isoformat())
                config=dict(version=1, days=int(raw), calendar=data.get('time_calendar') or 'calendar', statuses=[v.strip() for v in data.get('time_statuses','').splitlines() if v.strip()], weekends=[int(v) for v in data.get('time_weekends',[])], holidays=holidays, responses=data.get('time_responses',[]))
                validate(config)
                if metric == 'customer_wait' and not config['responses']: raise ValueError('حداقل یک نوع پیگیری انتخاب کنید.')
                self.instance.value=config
            except (ValueError,TypeError) as error:
                self.add_error('target_value',str(error))
        return data

    def save(self, commit=True):
        if not self.instance.code:
            self.instance.code = self.cleaned_data['request_key'].hex
        return super().save(commit=commit)
