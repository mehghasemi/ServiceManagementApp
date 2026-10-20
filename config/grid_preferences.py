"""Personal presentation settings, independent of CRM data and operation rights."""
import json
import re
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from config.access import member
from planning.models import GridPreference

KEYS = {'visits-onsite', 'visits-periodic', 'cases', 'projects', 'backlogs', 'upgrades', 'planning-attention',
        'projects-attention', 'demo-board', 'demo-cases'}


@ensure_csrf_cookie
@require_http_methods(['GET', 'POST'])
def preferences(request, key):
    if not member(request.user):
        return JsonResponse({'error': 'دسترسی مجاز نیست.'}, status=403)
    if key not in KEYS:
        return JsonResponse({'error': 'گرید ناشناخته است.'}, status=404)
    if request.method == 'GET':
        row = GridPreference.objects.filter(user=request.user, key=key).first()
        return JsonResponse({'columns': row.columns if row else []})
    try:
        if len(request.body) > 12000:
            raise ValueError()
        data = json.loads(request.body)
        columns = data['columns']
        if not isinstance(columns, list) or len(columns) > 40:
            raise ValueError()
        seen = set()
        for column in columns:
            if not isinstance(column, dict) or set(column) != {'id', 'width', 'visible'}:
                raise ValueError()
            cid = column['id']
            if not isinstance(cid, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,59}', cid) or cid in seen:
                raise ValueError()
            seen.add(cid)
            if type(column['width']) is not int or not 80 <= column['width'] <= 600 or type(column['visible']) is not bool:
                raise ValueError()
        if columns and not any(c['visible'] for c in columns):
            raise ValueError()
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return JsonResponse({'error': 'تنظیم ستون‌ها معتبر نیست؛ حداقل یک ستون را نمایش دهید.'}, status=400)
    GridPreference.objects.update_or_create(user=request.user, key=key, defaults={'columns': columns})
    return JsonResponse({'columns': columns})
