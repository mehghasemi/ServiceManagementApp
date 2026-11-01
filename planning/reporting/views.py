import json
import uuid
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie
from config.access import member
from planning.models import PersonalDashboard
from planning.dashboard_views import validate_widgets
from .sources import Sources, schema
from .configuration import validate_configuration, effective_filters
from .engine import execute, matches, validate_filter


def body(request):
    if len(request.body) > 200000: raise ValueError('درخواست بیش از حد بزرگ است.')
    value = json.loads(request.body)
    if not isinstance(value, dict): raise ValueError('درخواست معتبر نیست.')
    return value


@require_http_methods(['GET'])
def metadata(request):
    if not member(request.user): return JsonResponse({'error': 'دسترسی مجاز نیست.'}, status=403)
    sources = Sources(request.user); output = schema()
    for key, item in output.items():
        try:
            rows, meta = sources.load(key)
            item['coverage'] = meta
            for field, info in item['fields'].items():
                info['nonempty'] = sum(r.get(field) not in (None, '') for r in rows)
        except ValueError as error:
            item['coverage'] = {'available': False, 'error': str(error)}
    return JsonResponse({'sources': output})


@ensure_csrf_cookie
@require_http_methods(['POST'])
def preview(request):
    if not member(request.user): return JsonResponse({'error': 'دسترسی مجاز نیست.'}, status=403)
    try:
        data = body(request)
        widgets = validate_widgets(data.get('widgets', []), True)
        config = validate_configuration(data.get('configuration', {}), widgets)
        values = data.get('values', {})
        if not isinstance(values, dict): raise ValueError('مقادیر فیلتر معتبر نیستند.')
        sources = Sources(request.user); output = []; work = 0
        target = data.get('widget')
        for widget in widgets:
            if target and target != widget['id']: continue
            if widget['source'] != 'dynamic':
                from planning.dashboard_service import chart_data
                legacy = chart_data(request.user, [widget])[0]
                output.append({'id': widget['id'], 'legacy': True, 'rows': [{'label': r['label'], 'value': r['count']} for r in legacy['rows']]})
                continue
            rows, meta = sources.load(widget['query']['source'])
            work += len(rows) * max(1, len(json.dumps(widget['query'].get('filter'))) // 50)
            if work > 1000000:
                raise ValueError('حجم محاسبه این درخواست زیاد است؛ ابزارک‌ها یا View را محدود کنید.')
            result = execute(rows, widget['query'], effective_filters(config, widget, values), data.get('group'), data.get('page', 1))
            output.append({'id': widget['id'], 'coverage': meta, **result})
        return JsonResponse({'widgets': output})
    except (ValueError, TypeError, KeyError, UnicodeDecodeError) as error:
        return JsonResponse({'error': str(error) or 'درخواست گزارش معتبر نیست.'}, status=400)


@require_http_methods(['POST'])
def options(request):
    if not member(request.user): return JsonResponse({'error': 'دسترسی مجاز نیست.'}, status=403)
    try:
        data = body(request)
        fields = schema()[data['source']]['fields']
        if data['field'] not in fields: raise ValueError('فیلد معتبر نیست.')
        nodes = data.get('filters', [])
        if not isinstance(nodes, list) or len(nodes) > 12: raise ValueError('فیلتر بیش از حد است.')
        for node in nodes: validate_filter(node, fields)
        rows, _ = Sources(request.user).load(data['source'])
        values = sorted({str(row[data['field']]) for row in rows if row.get(data['field']) not in (None, '') and all(matches(row, node, fields) for node in nodes)})
        search = str(data.get('search', '')).casefold()[:100]
        values = [v for v in values if search in v.casefold()]
        return JsonResponse({'options': values[:1000], 'total': len(values), 'limited': len(values) > 1000})
    except (ValueError, TypeError, KeyError, UnicodeDecodeError) as error:
        return JsonResponse({'error': str(error) or 'فیلتر معتبر نیست.'}, status=400)


@require_http_methods(['POST'])
def manage(request, key):
    if not member(request.user): return JsonResponse({'error': 'دسترسی مجاز نیست.'}, status=403)
    row = get_object_or_404(PersonalDashboard, user=request.user, key=key, key__startswith='custom-')
    action = request.POST.get('action')
    if action == 'copy':
        if PersonalDashboard.objects.filter(user=request.user, key__startswith='custom-').count() >= 20:
            return JsonResponse({'error': 'حداکثر ۲۰ داشبورد مجاز است.'}, status=400)
        copy = PersonalDashboard.objects.create(user=request.user, key='custom-' + uuid.uuid4().hex,
            title=('کپی ' + row.title)[:100], widgets=row.widgets, configuration=row.configuration)
        return redirect('personal-dashboard', key=copy.key)
    if action == 'delete':
        # Keep the public publication independent; it can only be withdrawn by an admin.
        row.delete()
        return redirect('personal-dashboards')
    return JsonResponse({'error': 'عملیات معتبر نیست.'}, status=400)
