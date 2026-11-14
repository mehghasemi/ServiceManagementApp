"""Managerial decisions over the current, authorized planning View."""
import hashlib
import json

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone

from config.access import shared_queryset
from config.dates import PersianDateField
from criteria.views import evaluations, rule_description
from integrations.models import CaseAction
from integrations.views import operator_required
from .models import InterventionEvent

QUEUES = {'decision': 'نیازمند تصمیم شما', 'staff': 'در انتظار اقدام مسئول', 'customer': 'در انتظار پاسخ مشتری'}
KINDS = {'decision': 'ثبت تصمیم و تعهد', 'followup': 'ثبت نتیجه پیگیری', 'warning': 'ثبت هشدار داخلی', 'closed': 'تعیین تکلیف شد'}


class EventForm(forms.Form):
    kind = forms.ChoiceField(label='نوع ثبت', choices=KINDS.items())
    description = forms.CharField(label='اقدام بعدی یا نتیجه', max_length=500)
    queue = forms.ChoiceField(label='پس از تصمیم در کدام صف باشد؟', choices=QUEUES.items())
    responsible = forms.CharField(label='مسئول اقدام یا مخاطب هشدار', required=False, max_length=120)
    decision_owner = forms.CharField(label='صاحب تصمیم', required=False, max_length=120)
    blocker = forms.CharField(label='مانع گزارش‌شده', required=False, max_length=500)
    due = PersianDateField(label='موعد پیگیری', required=False)
    revision = forms.IntegerField(widget=forms.HiddenInput, min_value=0)
    evidence_hash = forms.CharField(widget=forms.HiddenInput, max_length=64)

    def clean(self):
        data = super().clean()
        if data.get('kind') in ('warning','decision') and not data.get('responsible'):
            self.add_error('responsible','مسئول یا مخاطب را مشخص کنید.')
        if data.get('kind') == 'decision':
            if not data.get('decision_owner'):
                self.add_error('decision_owner','فرد یا نقش صاحب تصمیم را وارد کنید.')
            if data.get('queue') != 'decision' and not data.get('due'):
                self.add_error('due','برای تعهد، موعد پیگیری تعیین کنید.')
        return data


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()


def collect(user):
    hits, _, records, _ = evaluations(user, 'planning')
    matched = {row['item'].pk:row['rules'] for row in hits}
    completed = shared_queryset(CaseAction.objects.filter(case_id__in=[case.pk for case,_ in records], completed_at__isnull=False), user, 'actor')
    latest = {}
    for action in completed.order_by('-completed_at','-pk'):
        latest.setdefault(action.case_id, action)
    issues = {}
    for case, facts in records:
        group = bool(case.parent_id and case.customer_id)
        identity = ['backlog',case.customer_id,case.parent_id] if group else ['case',case.crm_id]
        key = digest([case.scope, 'shared' if settings.SERVICE_LAN else user.pk, identity])
        issue = issues.setdefault(key, dict(key=key, customer=case.customer, title=(case.parent_title or 'بکلاگ مشترک') if group else case.title,
            cases=[], rules={}, decision_hit=False, signals=[], actions=[], followup=None, last_result='', priority=10, history=[], warnings=[]))
        rules = matched.get(case.pk, [])
        issue['cases'].append((case,rules))
        issue['decision_hit'] |= any(rule.attention_group == 'decision' for rule in rules)
        issue['rules'].update({r.pk:r.label for r in rules})
        issue['priority'] = min([issue['priority'], *(r.priority for r in rules)])
        actions = case.rule_actions
        issue['actions'].extend(actions)
        issue['signals'].append([str(case.crm_id),case.source_status,case.parent_status,sorted((r.pk,r.revision) for r in rules),sorted((a.pk,a.revision) for a in actions)])
        followup = latest.get(case.pk)
        if followup and (not issue['followup'] or followup.completed_at > issue['followup']):
            issue.update(followup=followup.completed_at,last_result=followup.result)
    for event in shared_queryset(InterventionEvent.objects.all(),user,'actor').filter(issue__in=issues).select_related('actor').order_by('-revision'):
        issues[event.issue]['history'].append(event)
    result = {}
    today = timezone.localdate()
    for key,row in issues.items():
        history = row['history']
        if not row['rules'] and not history and not row['actions']:
            continue
        row['fingerprint'] = digest(sorted(row['signals']))
        row['revision'] = history[0].revision if history else 0
        row['warnings'] = [e for e in history if e.kind == 'warning']
        row['last_warning'] = next(iter(row['warnings']),None)
        row['first_warning'] = row['warnings'][-1] if row['warnings'] else None
        state = next((e for e in history if e.kind in ('closed','decision')),None)
        follow = next((e for e in history if e.kind == 'followup'),None)
        if follow and (not row['followup'] or follow.created_at >= row['followup']):
            row.update(followup=follow.created_at,last_result=follow.description)
        actions = row['actions']
        row.update(queue='decision', next_step='', responsible='', owner='', due=None, blocker='، '.join(dict.fromkeys(a.blocker for a in actions if a.blocker)),reason='اقدام بعدی گروه تعیین شود')
        if state:
            row.update(queue=state.queue if state.kind=='decision' else 'closed',next_step=state.description,responsible=state.responsible,owner=state.decision_owner,due=state.due,reason='')
            if state.blocker:
                row['blocker']=state.blocker
            if state.evidence_hash != row['fingerprint']:
                row.update(queue='decision',reason='وضعیت کیس‌ها، معیار یا تعهد مرتبط تغییر کرده است')
            elif state.kind=='decision' and state.due and state.due < today:
                row.update(queue='decision',reason='موعد تعهد گذشته است')
        elif len(actions)==1 and len(row['cases'])==1:
            action=actions[0]
            row.update(next_step=action.title,responsible=action.responsible,due=action.due_date)
            if action.responsible and action.due_date and action.due_date >= today and not action.blocker:
                row.update(queue='staff',reason='')
        if not state and not row['decision_hit'] and not actions:
            row.update(queue='review',reason='علت یا اطلاعات مورد نیاز بررسی شود')
        result[key]=row
    return result


def checked_condition(rule):
    values = rule.value
    if rule.metric == 'note_age' and rule.operator == 'gt':
        return f'از آخرین یادداشت دریافت‌شده بیش از {values} روز گذشته است.'
    if rule.metric in ('source_status', 'parent_status') and rule.operator == 'in':
        field = 'وضعیت کیس' if rule.metric == 'source_status' else 'وضعیت بکلاگ مرتبط'
        return f'{field} در CRM یکی از این مقادیر است: ' + '، '.join(values)
    if rule.metric == 'has_parent' and rule.operator == 'eq' and values is False:
        return 'در داده دریافتی کیس، شناسه بکلاگ مرتبط موجود نیست.'
    return rule_description(rule, 'planning')


def queue_report(rows):
    summary = {}
    matched_total = 0
    related_total = 0
    for row in rows:
        reasons = {}
        related_total += len(row['cases'])
        for case, rules in row['cases']:
            if rules:
                matched_total += 1
            for rule in rules:
                if rule.pk not in summary:
                    summary[rule.pk] = dict(id=rule.pk, label=rule.label,
                        checked=checked_condition(rule), topics=0, cases=0)
                entry = summary[rule.pk]
                entry['cases'] += 1
                if rule.pk not in reasons:
                    entry['topics'] += 1
                    reasons[rule.pk] = entry
        row['matched_reasons'] = reasons.values()
        if row['queue'] == 'review' and reasons:
            row['entry_reason'] = '، '.join(entry['label'] for entry in reasons.values())
            row['entry_check'] = ' '.join(entry['checked'] for entry in reasons.values())
        else:
            row['entry_reason'] = row['reason'] or {**QUEUES, 'closed':'تعیین تکلیف‌شده'}.get(row['queue'], 'بررسی اولیه')
            row['entry_check'] = row['entry_reason']
            state = next((e for e in row['history'] if e.kind in ('closed','decision')), None)
            if state:
                row['entry_check'] = ('شواهد جاری با زمان ثبت تصمیم تفاوت دارد.' if state.evidence_hash != row['fingerprint']
                    else 'موعد تعهد ثبت‌شده قبل از امروز است.' if state.kind == 'decision' and state.due and state.due < timezone.localdate()
                    else 'آخرین تصمیم ثبت‌شده: ' + state.description)
            elif row['queue'] == 'staff':
                row['entry_check'] = 'یک کیس و یک اقدام باز با مسئول، موعد معتبر و بدون مانع ثبت‌شده.'
            elif reasons:
                row['entry_check'] = ' '.join(entry['checked'] for entry in reasons.values())
            elif row['actions']:
                row['entry_check'] = 'اقدام باز ثبت شده و برای موضوع تصمیم مشترک ثبت نشده است.'
    return dict(topics=len(rows), cases=related_total, matched=matched_total,
                reasons=sorted(summary.values(), key=lambda entry: (-entry['topics'], entry['id'])))


@operator_required
def board(request):
    rows=list(collect(request.user).values())
    total_topics = len(rows)
    total_cases = sum(len(row['cases']) for row in rows)
    selected=request.GET.get('queue','review')
    queues={'review':'نیازمند بررسی اولیه', **QUEUES, 'closed':'تعیین تکلیف‌شده'}
    if selected not in queues:
        raise Http404
    tabs=[(key,label,sum(row['queue']==key for row in rows)) for key,label in queues.items()]
    rows=sorted((row for row in rows if row['queue']==selected),key=lambda row:(row['priority'],-len(row['cases']),row['title'],row['key']))
    report = queue_report(rows)
    selected_rule = request.GET.get('rule', '')
    if selected_rule:
        rows = [row for row in rows if any(str(key) == selected_rule for key in row['rules'])]
    return render(request,'criteria/interventions.html',{'active_module':'planning','crm_mode':True,'mode':'attention','total_topics':total_topics,'total_cases':total_cases,'report':report,'selected_rule':selected_rule,'tabs':tabs,'selected':selected,'page':Paginator(rows,25).get_page(request.GET.get('page'))})


@operator_required
def detail(request,key):
    row=collect(request.user).get(key)
    if row is None:
        raise Http404
    initial={'revision':row['revision'],'evidence_hash':row['fingerprint'],'queue':row['queue'] if row['queue'] in QUEUES else 'decision','responsible':row['responsible'],'decision_owner':row['owner'],'due':row['due']}
    form=EventForm(request.POST if request.method=='POST' else None,initial=initial)
    status=200
    if request.method=='POST' and form.is_valid():
        values=form.cleaned_data.copy()
        revision=values.pop('revision')
        if revision != row['revision'] or values['evidence_hash'] != row['fingerprint']:
            form.add_error(None,'اطلاعات تغییر کرده است. صفحه را تازه کنید و دوباره بررسی کنید.')
            status=409
        else:
            try:
                with transaction.atomic():
                    InterventionEvent.objects.create(issue=key,revision=revision+1,actor=request.user,**values)
            except IntegrityError:
                form.add_error(None,'ثبت هم‌زمان انجام شده است. صفحه را تازه کنید.')
                status=409
            else:
                messages.success(request,'در سابقه رسیدگی ثبت شد.')
                return redirect('planning-intervention',key=key)
    for event in row['history']:
        event.label=KINDS.get(event.kind,event.kind)
    return render(request,'criteria/intervention.html',{'row':row,'form':form,'crm_mode':True,'mode':'attention','active_module':'planning'},status=status)
