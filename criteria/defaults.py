"""One-time editable starting values; never override a user's saved rules."""
def definitions(options):
    def rule(code, label, metric, operator, value, priority=3, **extra):
        if options.module == 'planning' and extra.get('purpose', 'attention') == 'attention':
            extra.setdefault('attention_group', {'missing_parent':'information','parent_review':'clarification','resolution_review':'clarification','stale':'information','overdue':'decision','blocked':'decision'}.get(code, ''))
        return dict(code=code, label=label, metric=metric, operator=operator, value=value, priority=priority, **extra)
    if options.module == 'projects':
        return [
            rule('overdue', 'عبور از موعد برنامه پروژه', 'overdue_days', 'gt', 0, 1, action_title='بازبینی تعهد و موانع پروژه', impact='تعیین موعد معتبر و مسئول رفع مانع'),
            rule('no_manager', 'مدیر پروژه نامشخص', 'manager_missing', 'eq', True, 2, action_title='تعیین مدیر و مسیر پیگیری', impact='روشن‌شدن مسئولیت و پاسخ‌گویی'),
            rule('stale', 'گزارش پروژه قدیمی است', 'note_age', 'gt', options.stale_days, 3, action_title='درخواست گزارش تازه', impact='بهبود مبنای تصمیم‌گیری؛ قدمت گزارش به معنی نبود کار نیست'),
            rule('no_note', 'یادداشت در View موجود نیست', 'no_note', 'eq', True, 3, action_title='بررسی پوشش گزارش پروژه', impact='تفکیک نقص ثبت از محدودیت View'),
            rule('no_due', 'موعد پایان پروژه ثبت نشده', 'planned_end_missing', 'eq', True, 2, action_title='توافق بر موعد برنامه', impact='امکان پیگیری تعهد و سنجش پیشرفت'),
        ]
    return [
        rule('missing_parent', 'رابطه برنامه مشخص نیست', 'has_parent', 'eq', False, 3, active_only=False),
        rule('parent_review', 'وضعیت برنامه نیازمند تطبیق است', 'parent_status', 'in', [s.strip() for s in options.parent_review_statuses.split(',') if s.strip()], 3),
        rule('resolution_review', 'رفع در نسخه و تأیید مشتری نیازمند بررسی است', 'source_status', 'in', ['Done'], 2, closure_candidate=True),
        rule('stale', 'یادداشت کیس قدیمی است', 'note_age', 'gt', options.stale_days, 3),
        rule('overdue', 'موعد اقدام محلی گذشته است', 'overdue_days', 'gt', 0, 1),
        rule('blocked', 'اقدام محلی مانع ثبت‌شده دارد', 'blocker_count', 'gte', 1, 2),
        rule('without_action', 'اقدام محلی باز وجود ندارد', 'open_count', 'eq', 0, 4, enabled=False),
        rule('upgrade', 'ارتقای هماهنگ مرکز', 'parent_title', 'contains_any', ['ارتقا', 'ارتقاء', 'بروزرسانی', 'به‌روزرسانی'], 1, purpose='opportunity', grouping='customer_program', min_count=2, action_title='هماهنگی ارتقای مرکز و بررسی جمعی رفع کیس‌ها', impact='یک برنامه ارتقا برای چند کیس مرتبط، سپس بررسی نتیجه هر کیس با مشتری'),
        rule('onsite', 'مراجعه حضوری مشترک به مرکز', 'source_status', 'in', ['Checking in Presence Services'], 1, purpose='opportunity', grouping='customer', min_count=2, action_title='برنامه‌ریزی یک مراجعه حضوری برای چند کیس مرکز', impact='تجمیع بررسی و اقدام حضوری در یک مراجعه؛ دامنه کار هر کیس پیش از اعزام تأیید شود'),
        rule('shared', 'پیگیری مشترک برنامه مشتری', 'has_parent', 'eq', True, 3, purpose='opportunity', grouping='customer_program', min_count=3, action_title='هماهنگی یک برنامه اجرایی مشترک', impact='کاهش پیگیری‌های پراکنده و تعیین مسئول و موعد مشترک'),
    ]
