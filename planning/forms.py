from config.dates import PersianDateField
import uuid
from django import forms
from .models import Program

class ProgramForm(forms.ModelForm):
    due_date = PersianDateField(label='موعد (شمسی)', required=False)
    revision = forms.IntegerField(widget=forms.HiddenInput, initial=0)
    request_id = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    confirm = forms.BooleanField(label='ثبت این اطلاعات و تغییر وضعیت برنامه را تأیید می‌کنم.', help_text='با زدن دکمه ذخیره، اطلاعات و تغییر وضعیت در تاریخچه ثبت می‌شود.')

    class Meta:
        model = Program
        fields = ['customer', 'title', 'owner', 'status', 'next_step', 'due_date', 'blocker', 'notes']
        widgets = {'blocker': forms.Textarea(attrs={'rows': 3}), 'notes': forms.Textarea(attrs={'rows': 3})}
        help_texts = {
            'customer': 'نام ساختگی مشتری؛ هر برنامه به یک مشتری تعلق دارد.',
            'title': 'کار اجرایی مشترک را بنویسید؛ مانند نصب نسخه برای مشتری.',
            'owner': 'فردی که پیگیری قدم بعدی را بر عهده دارد؛ فعلاً متن آزاد است و حساب کاربری نیست.',
            'status': 'وضعیت محلی برنامه است؛ انتخاب آن تا ذخیره فرم اثری ندارد و CRM را تغییر نمی‌دهد.',
            'next_step': 'یک اقدام مشخص و قابل انجام؛ عبارت کلی «در حال پیگیری» کافی نیست.',
            'due_date': 'موعد روزانه به وقت تهران؛ ورود و نمایش تاریخ شمسی است.',
            'blocker': 'مانع و پیش‌نیاز را شرح دهید؛ مسئول و موعد بالا برای پیگیری همین مانع استفاده می‌شوند.',
            'notes': 'توضیح تکمیلی ساختگی؛ اطلاعات واقعی مشتری را در نمونه وارد نکنید.',
        }

    def clean(self):
        data = super().clean()
        if data.get('status') != Program.Status.DRAFT:
            for name in ('owner', 'next_step', 'due_date'):
                if not data.get(name):
                    self.add_error(name, 'برای این وضعیت، این بخش را تکمیل کنید.')
        if data.get('status') == Program.Status.BLOCKED and not data.get('blocker'):
            self.add_error('blocker', 'مانع یا پیش‌نیاز را توضیح دهید.')
        return data

class FollowUpForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    request_id = forms.UUIDField(widget=forms.HiddenInput, initial=uuid.uuid4)
    result = forms.CharField(label='نتیجه پیگیری', max_length=3000, widget=forms.Textarea(attrs={'rows': 4}), help_text='چه کاری انجام شد و چه چیزی روشن شد؟ ثبت این متن به معنی رفع کیس یا اتمام برنامه نیست.')
    next_step = forms.CharField(label='اقدام بعدی', max_length=500, help_text='قدم بعدی را مشخص کنید؛ اقدام قبلی در تاریخچه حفظ می‌شود.')
    due_date = PersianDateField(label='موعد پیگیری بعدی (شمسی)')
    confirm = forms.BooleanField(label='ثبت نتیجه و اقدام بعدی را تأیید می‌کنم.', help_text='ثبت یک‌باره است؛ ارسال دوباره همان فرم پیگیری تکراری نمی‌سازد.')
