from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F
from django.forms.models import model_to_dict
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from integrations.models import ModuleSettings, SettingsAudit, EvaluationRule
from integrations.jobs import module_settings
from integrations.views import operator_required, current_cases, active_snapshot
from .engine import ensure_rules, evaluate_records, planning_facts, project_facts, METRICS, OPERATORS
from .forms import SelectionForm, RuleForm


def context(module, mode):
    return {'crm_mode': True, 'active_module': module, 'mode': mode, 'module_key': module, 'module_label': 'برنامه‌ریزی' if module == 'planning' else 'مدیریت پروژه‌ها'}


def rule_description(rule, module):
    value = rule.value
    text = '، '.join(str(v) for v in value) if isinstance(value, list) else ('بله' if value else 'خیر') if isinstance(value, bool) else str(value)
    return f"{METRICS[module].get(rule.metric, (rule.metric,))[0]} · {OPERATORS.get(rule.operator, rule.operator)} · {text}"


@operator_required
def settings(request, module):
    options = module_settings(module)
    rules = ensure_rules(options)
    form = SelectionForm(request.POST or None, rules=rules, initial={'enabled': [str(r.pk) for r in rules if r.enabled], 'revision': options.revision})
    status = 200
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            locked = ModuleSettings.objects.select_for_update().get(pk=options.pk)
            if locked.revision != form.cleaned_data['revision']:
                form.add_error(None, 'معیارها یا تنظیمات تغییر کرده‌اند؛ صفحه را دوباره باز کنید.')
                status = 409
            else:
                selected = set(form.cleaned_data['enabled'])
                before = {str(r.pk): r.enabled for r in rules}
                for rule in rules:
                    enabled = str(rule.pk) in selected
                    if rule.enabled != enabled:
                        EvaluationRule.objects.filter(pk=rule.pk).update(enabled=enabled, revision=F('revision')+1)
                ModuleSettings.objects.filter(pk=locked.pk).update(revision=F('revision')+1)
                SettingsAudit.objects.create(actor=request.user, area=module+':rules', before=before, after={str(r.pk): str(r.pk) in selected for r in rules})
                messages.success(request, 'معیارهای انتخاب‌شده اعمال شد؛ بازخوانی CRM لازم نیست.')
                return redirect(module+'-criteria')
    selected = set(form['enabled'].value() or [])
    for rule in rules:
        rule.condition_text = rule_description(rule, module)
        rule.checked = str(rule.pk) in selected
    return render(request, 'criteria/settings.html', {**context(module, 'criteria'), 'rules': rules, 'form': form}, status=status)


@operator_required
def edit(request, module, pk=None):
    options = module_settings(module)
    ensure_rules(options)
    rule = get_object_or_404(EvaluationRule, pk=pk, settings=options) if pk else EvaluationRule(settings=options)
    before = model_to_dict(rule) if pk else {}
    form = RuleForm(request.POST or None, instance=rule, module=module)
    status = 200
    if request.method == 'POST' and form.is_valid():
        with transaction.atomic():
            ModuleSettings.objects.select_for_update().get(pk=options.pk)
            current = EvaluationRule.objects.select_for_update().get(pk=pk) if pk else None
            repeated = EvaluationRule.objects.filter(settings=options, code=form.cleaned_data['request_key'].hex).first() if not pk else None
            if repeated:
                fields = form.Meta.fields
                if all(getattr(repeated, name) == getattr(form.instance, name) for name in fields) and repeated.value == form.instance.value:
                    return redirect(module+'-criteria')
                form.add_error(None, 'این درخواست قبلاً با اطلاعات متفاوت ثبت شده است؛ فرم تازه‌ای باز کنید.')
                status = 409
            elif current and current.revision != form.cleaned_data['revision']:
                form.add_error(None, 'این معیار تغییر کرده است؛ فرم تازه‌ای باز کنید.')
                status = 409
            else:
                saved = form.save(commit=False)
                saved.revision = current.revision+1 if current else 1
                saved.save()
                ModuleSettings.objects.filter(pk=options.pk).update(revision=F('revision')+1)
                SettingsAudit.objects.create(actor=request.user, area=module+':rule', before=before, after=model_to_dict(saved))
                messages.success(request, 'معیار ذخیره شد و در تحلیل بعدی اعمال می‌شود.')
                return redirect(module+'-criteria')
    return render(request, 'criteria/edit.html', {**context(module, 'criteria'), 'form': form, 'is_new': pk is None}, status=status)


def evaluations(user, module):
    options = module_settings(module)
    rules = ensure_rules(options)
    today = timezone.localdate()
    if module == 'planning':
        snapshot = active_snapshot(user)
        records = planning_facts(current_cases(user), user, bool(snapshot and snapshot.coverage.get('notes')), today)
    else:
        from projects.views import snapshot_for
        snapshot = snapshot_for(user)
        records = [(r, project_facts(r, options, bool(snapshot.coverage.get('notes')), today)) for r in snapshot.records] if snapshot else []
    hits, counts = evaluate_records(records, rules)
    return hits, counts, records, rules


@operator_required
def attention(request, module):
    rows, counts, records, rules = evaluations(request.user, module)
    selected = request.GET.get('rule', '')
    total = len(rows)
    snapshot = active_snapshot(request.user) if module == 'planning' else None
    if selected:
        rows = [r for r in rows if any(str(rule.pk) == selected for rule in r['rules'])]
    for entry in rows:
        for rule in entry['rules']:
            rule.condition_text = rule_description(rule, module)
    return render(request, 'criteria/attention.html', {**context(module, 'attention'), 'page': Paginator(rows, 25).get_page(request.GET.get('page')), 'counts': counts, 'selected': selected, 'total': total, 'source_count': len(records), 'notes_loaded': bool(snapshot and snapshot.coverage.get('notes'))})
