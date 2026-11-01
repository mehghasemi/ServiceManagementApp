"""Editable initial assumptions requested by the service manager."""
READY = dict(code='upgrade-ready', label='قابل رفع با ارتقا؛ فرض مدیریتی Done',
    dashboard='upgrade', purpose='upgrade_ready', metric='source_status', operator='in',
    value=['Done'], active_only=True, priority=1,
    impact='فرض مدیریتی: کیس منطبق با اجرای ارتقا قابل رفع است؛ انجام ارتقا و بسته‌شدن واقعی جداگانه پیگیری می‌شود.')
PROGRAM = dict(code='upgrade-program', label='برنامه نصب نگارش جدید',
    dashboard='upgrade', purpose='upgrade_program', metric='case_service', operator='in',
    value=['برنامه ریزی - نصب نگارش جدید'], active_only=False, priority=1)
