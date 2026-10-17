"""Plain-language explanations generated from the same saved rule as evaluation."""
def explain_rule(rule):
    from .engine import METRICS, OPERATORS
    module = rule.settings.module
    metric = METRICS[module].get(rule.metric, (rule.metric,))[0]
    value = rule.value
    value = '، '.join(str(v) for v in value) if isinstance(value, list) else ('بله' if value else 'خیر') if isinstance(value, bool) else str(value)
    text = f'این معیار داده دریافت‌شده از فهرست انتخابی CRM را بررسی می‌کند. شرط فعلی: {metric} {OPERATORS.get(rule.operator, rule.operator)} «{value}».'
    if rule.active_only:
        text += ' فقط موارد جاری بررسی می‌شوند؛ وضعیت نامشخص نتیجه قطعی ندارد.'
    if rule.metric in ('note_age', 'no_note'):
        text += ' یادداشت‌های مرتبط دریافت‌شده مبنا هستند؛ تاریخ، آخرین ویرایش یادداشت است و لزوماً تاریخ نوشتن گزارش تازه نیست. نبود دریافت، نامشخص است؛ نبود یادداشت در این فهرست به معنی نبود آن در کل CRM نیست.'
    if rule.metric in ('overdue_days', 'open_count', 'blocker_count') and module == 'planning':
        text += ' فقط اقدام‌های باز ثبت‌شده در این برنامه مبنا هستند؛ فعالیت‌های خارج از برنامه در این شمارش نیستند.'
    if rule.purpose == 'opportunity':
        group = 'مرکز و برنامه مرتبط یکسان' if rule.grouping == 'customer_program' else 'مرکز یکسان، حتی در چند برنامه'
        text += f' کیس‌های منطبق با شناسه واقعی {group} گروه می‌شوند؛ حداقل {rule.min_count} کیس لازم است. پیشنهاد: {rule.action_title or rule.label}. تعداد نمایش‌داده‌شده ظرفیت پیگیری مشترک است، نه تعداد قطعی قابل بستن.'
    else:
        text += ' انطباق، مورد را برای بررسی مدیریتی مشخص می‌کند؛ به معنی خطا یا کم‌کاری کارشناس نیست.'
    text += f' اهمیت تنظیم‌شده {rule.priority} است؛ عدد کمتر زودتر نمایش داده می‌شود.'
    if rule.impact:
        text += f' اثر مورد انتظار: {rule.impact}'
    if rule.closure_candidate:
        text += ' این معیار فقط نامزد بررسی تأیید رفع را مشخص می‌کند؛ حل نزد مشتری باید جداگانه تأیید شود.'
    return text + ' داده ناقص نتیجه قطعی نمی‌دهد. این پیشنهاد چیزی را در CRM تغییر نمی‌دهد.'
