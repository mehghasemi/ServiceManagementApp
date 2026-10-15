"""Explainable suggestions, limited to the active View and current actor."""
from django.db.models import Prefetch
from integrations.models import CaseAction


def recommendations(cases, user, review_statuses, today):
    actions = CaseAction.objects.filter(actor=user, status='open').order_by('due_date', 'pk')
    result = []
    for case in cases.prefetch_related(Prefetch('local_actions', queryset=actions, to_attr='suggestion_actions')):
        opened = case.suggestion_actions
        overdue = [action for action in opened if action.due_date < today]
        blocked = [action for action in opened if action.blocker.strip()]
        if overdue:
            priority, title = 1, 'بازبینی تعهد عقب‌افتاده و تعیین موعد معتبر'
            reason = f'{len(overdue)} اقدام محلی باز از موعد گذشته است؛ بیشترین تأخیر {(today - overdue[0].due_date).days} روز.'
            impact = 'شفاف‌شدن تعهد بعدی و کاهش احتمال ادامه تأخیر'
        elif blocked:
            priority, title = 2, 'بررسی مانع و تعیین مسئول رفع آن'
            reason = f'{len(blocked)} اقدام باز با مانع ثبت‌شده وجود دارد.'
            impact = 'کمک به بازشدن مسیر ادامه کار'
        elif case.parent_status and case.parent_status in review_statuses:
            priority, title = 3, 'تطبیق وضعیت کیس با برنامه مرتبط'
            reason = f'وضعیت برنامه «{case.parent_status}» در فهرست بازبینی تنظیمات است.'
            impact = 'کاهش تصمیم‌گیری بر پایه وضعیت‌های ناسازگار؛ پس از بررسی شواهد'
        elif not case.parent_id:
            priority, title = 4, 'بررسی ارتباط کیس با برنامه در CRM'
            reason = 'شناسه برنامه مرتبط در داده دریافتی موجود نیست.'
            impact = 'بهبود قابلیت ردیابی و گروه‌بندی کیس‌ها'
        elif not opened:
            priority, title = 5, 'بررسی نیاز به ثبت قدم بعدی'
            reason = 'برای شما اقدام محلی بازی ثبت نشده است؛ فعالیت CRM ممکن است وجود داشته باشد.'
            impact = 'روشن‌شدن مسئول، موعد و نتیجه مورد انتظار در صورت نیاز به پیگیری'
        else:
            continue
        result.append({'case': case, 'priority': priority, 'title': title, 'reason': reason, 'impact': impact,
                       'sort_date': overdue[0].due_date if overdue else today})
    return sorted(result, key=lambda item: (item['priority'], item['sort_date'], item['case'].number, item['case'].pk))
