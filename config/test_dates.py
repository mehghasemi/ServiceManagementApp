from datetime import date
from django.test import SimpleTestCase
from django.core.exceptions import ValidationError
from config.dates import PersianDateField, persian_date
from integrations.forms import ActionForm
import uuid

class PersianTests(SimpleTestCase):
    def test_roundtrip_and_leap_validation(self):
        field=PersianDateField()
        self.assertEqual(field.clean('۱۴۰۳/۰۱/۰۱'),date(2024,3,20))
        self.assertEqual(persian_date(date(2024,3,20)),'1403/01/01')
        with self.assertRaises(ValidationError):field.clean('۱۴۰۲/۱۲/۳۰')
        with self.assertRaises(ValidationError):field.clean('2026-10-19')
    def test_preset_optional_fields_and_validation(self):
        form=ActionForm(data={'selected_preset':'پیگیری ارتقا','request_key':str(uuid.uuid4()),'confirm':True},presets=['پیگیری ارتقا'])
        self.assertTrue(form.is_valid(),form.errors)
        self.assertEqual(form.cleaned_data['title'],'پیگیری ارتقا')
        self.assertIsNone(form.cleaned_data['due_date'])
        bad=ActionForm(data={'selected_preset':'حذف‌شده','confirm':True},presets=['پیگیری ارتقا'])
        self.assertFalse(bad.is_valid())
