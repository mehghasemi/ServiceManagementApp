from django.test import SimpleTestCase
from django import forms
from integrations.forms import ModuleForm

class ActionTemplateTests(SimpleTestCase):
    def test_dedup_and_limits(self):
        form=object.__new__(ModuleForm)
        form.cleaned_data={'action_templates':'  پیگیری ارتقا  \nپیگیری ارتقا\nتأیید مشتری'}
        self.assertEqual(form.clean_action_templates(),'پیگیری ارتقا\nتأیید مشتری')
        form.cleaned_data={'action_templates':'x'*501}
        with self.assertRaises(forms.ValidationError):form.clean_action_templates()
    def test_empty_list_is_allowed(self):
        form=object.__new__(ModuleForm);form.cleaned_data={'action_templates':''}
        self.assertEqual(form.clean_action_templates(),'')
