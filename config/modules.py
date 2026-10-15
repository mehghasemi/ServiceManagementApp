"""Subsystem registry. A module contributes routes, navigation and settings.

Registration does not grant access; each endpoint enforces its own permissions.
"""
MODULES = (
    {'key': 'planning', 'label': 'برنامه‌ریزی', 'description': 'بازخوانی کیس‌های CRM، بررسی موانع و تعریف اقدام بعدی.', 'icon': '▤', 'enabled': True, 'route': 'planning-dashboard', 'settings_route': 'planning-settings'},
    {'key': 'projects', 'label': 'مدیریت پروژه‌ها', 'description': 'فضای آینده برای مدیریت استقرار، مراحل اجرا و تحویل پروژه.', 'icon': '◈', 'enabled': False, 'route': None, 'settings_route': None},
    {'key': 'tickets', 'label': 'مدیریت تیکت‌ها', 'description': 'فضای آینده برای بررسی جریان پشتیبانی و کیفیت رسیدگی به تیکت‌ها.', 'icon': '▧', 'enabled': False, 'route': None, 'settings_route': None},
)
