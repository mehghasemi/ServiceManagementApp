from integrations.forms import ModuleForm
from integrations.models import CRMView


class ProjectForm(ModuleForm):
    class Meta(ModuleForm.Meta):
        fields = ['auto_sync_enabled', 'auto_sync_minutes', 'case_view', 'note_view', 'parent_review_statuses', 'page_size']
        labels = {**ModuleForm.Meta.labels, 'case_view': 'View پیش‌فرض پروژه‌ها', 'note_view': 'View یادداشت‌های پروژه', 'stale_days': 'آستانه قدمت گزارش (روز)', 'parent_review_statuses': 'وضعیت‌های خاتمه‌یافته پروژه'}
        help_texts = {**ModuleForm.Meta.help_texts, 'parent_review_statuses': 'برچسب دقیق وضعیت‌های خاتمه یا لغو با ویرگول؛ از هشدار موعد و تازگی گزارش کنار گذاشته می‌شوند. مستقل از تنظیمات برنامه‌ریزی.', 'case_view': 'View موجودیت پروژه؛ انتخاب تا ذخیره صریح بعدی ثابت می‌ماند.', 'note_view': 'فیلترهای View حفظ و دریافت فقط به شناسه پروژه‌های همین View محدود می‌شود. نبود یادداشت به معنی نبود فعالیت نیست.'}

    def __init__(self, *args, scope, **kwargs):
        # ModuleForm assumes activity_view; project settings intentionally omit it.
        from integrations.forms import ConfirmedForm
        ConfirmedForm.__init__(self, *args, **kwargs)
        catalog = CRMView.objects.filter(scope=scope).order_by('name', 'kind')
        self.fields['case_view'].queryset = catalog.filter(entity='brd_project')
        self.fields['case_view'].required = True
        self.fields['note_view'].queryset = catalog.filter(entity='annotation')
