from collections import defaultdict
from django.db.models import Prefetch
from integrations.models import CaseAction


def grouped_recommendations(cases, user, today, review_statuses):
    groups = defaultdict(list)
    actions = CaseAction.objects.filter(actor=user, status='open')
    for case in cases.prefetch_related(Prefetch('local_actions', queryset=actions, to_attr='group_actions')):
        # Unknown customers/programs must never become an invented shared project.
        if case.customer_id and case.parent_id:
            groups[(case.customer_id, case.parent_id)].append(case)
    result = []
    for (customer_id, parent_id), members in groups.items():
        first = members[0]
        overdue = sum(any(a.due_date < today for a in c.group_actions) for c in members)
        blocked = sum(any(a.blocker.strip() for a in c.group_actions) for c in members)
        review = sum(c.parent_status in review_statuses for c in members)
        candidate = sum(c.source_status.casefold() == 'done' and c.evidence.get('state') == 0 for c in members)
        upgrade = any(word in first.parent_title for word in ('ارتقا', 'ارتقاء', 'بروزرسانی', 'به‌روزرسانی'))
        if overdue:
            priority, title = 1, 'بازبینی تعهدهای مشترک و هماهنگی یک برنامه جبرانی'
            reason = f'{overdue} کیس دارای اقدام محلی با موعد گذشته در همین مشتری و برنامه است.'
        elif blocked:
            priority, title = 2, 'بررسی موانع مشترک در جلسه هماهنگی مشتری'
            reason = f'برای {blocked} کیس مانع ثبت شده؛ مشترک‌بودن علت باید در جلسه بررسی شود.'
        elif review:
            priority, title = 3, 'تطبیق جمعی وضعیت برنامه و کیس‌های مرتبط'
            reason = f'{review} کیس به برنامه‌ای با وضعیت نیازمند بازبینی متصل است.'
        elif len(members) > 1:
            priority = 4
            title = 'بررسی امکان ارتقای هماهنگ مرکز' if upgrade else 'تدوین برنامه اقدام مشترک برای این مرکز'
            reason = f'{len(members)} کیس به یک مشتری و یک برنامه CRM مشترک متصل‌اند.'
        else:
            continue
        result.append({'priority': priority, 'title': title, 'reason': reason,
            'customer': first.customer or 'عنوان مشتری موجود نیست', 'program': first.parent_title,
            'customer_id': customer_id, 'parent_id': parent_id, 'count': len(members), 'candidate': candidate,
            'impact': f'امکان هماهنگ‌کردن پیگیری {len(members)} کیس در یک برنامه اجرایی؛ کاهش پیگیری‌های پراکنده.',
            'condition': 'بسته‌شدن کیس‌ها وابسته به رفع در نسخه هدف، اجرای موفق و تأیید نتیجه مشتری است. تعداد قابل بستن از داده فعلی قابل تعیین نیست.'})
    return sorted(result, key=lambda r: (r['priority'], -r['count'], r['customer_id'], r['parent_id']))
