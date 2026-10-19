from datetime import date, datetime
import jdatetime
from django import forms
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date


def persian_date(value):
    if not value: return 'ثبت نشده'
    try:
        if isinstance(value, str): value = parse_datetime(value) or parse_date(value)
        if isinstance(value, datetime):
            if timezone.is_aware(value): value = timezone.localtime(value)
            return jdatetime.datetime.fromgregorian(datetime=value.replace(tzinfo=None)).strftime('%Y/%m/%d %H:%M')
        return jdatetime.date.fromgregorian(date=value).strftime('%Y/%m/%d')
    except (TypeError, ValueError, AttributeError): return 'تاریخ نامعتبر'


class PersianDateField(forms.DateField):
    widget = forms.TextInput
    def __init__(self, *args, **kwargs):
        kwargs.setdefault('help_text', 'تاریخ شمسی؛ نمونه ۱۴۰۵/۰۷/۲۷')
        kwargs.setdefault('widget', forms.TextInput(attrs={'placeholder':'۱۴۰۵/۰۷/۲۷','dir':'ltr','inputmode':'numeric'}))
        super().__init__(*args, **kwargs)
    def prepare_value(self, value):
        return persian_date(value) if isinstance(value, date) else value
    def to_python(self, value):
        if value in self.empty_values: return None
        if isinstance(value, date): return value
        try:
            text=str(value).translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩','01234567890123456789')).replace('-','/')
            year,month,day=map(int,text.split('/'))
            if not 1200 <= year <= 1600: raise ValueError()
            return jdatetime.date(year,month,day).togregorian()
        except (ValueError, TypeError): raise forms.ValidationError('تاریخ شمسی معتبر مانند ۱۴۰۵/۰۷/۲۷ وارد کنید.')
