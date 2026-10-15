import hashlib
import json
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from .models import Program, FollowUp, AuditEvent, Mutation

FIELDS = ('customer', 'title', 'owner', 'status', 'next_step', 'due_date', 'blocker', 'notes')
class Conflict(Exception):
    pass

def snapshot(program):
    return {key: str(getattr(program, key) or '') for key in (*FIELDS, 'baseline_due', 'revision')}

def fingerprint(kind, pk, data):
    return hashlib.sha256(json.dumps([kind, pk, data], sort_keys=True, default=str).encode()).hexdigest()

def replay(actor, key, digest):
    prior = Mutation.objects.filter(key=key).first()
    if prior:
        if prior.actor_id != actor.pk or prior.fingerprint != digest:
            raise Conflict('شناسه این درخواست قبلاً با اطلاعات متفاوت ثبت شده است. صفحه را دوباره باز کنید.')
        return prior.program

def allowed(actor):
    return Program.objects.filter(created_by=actor)

@transaction.atomic
def save_program(actor, data, pk=None):
    digest = fingerprint('program', pk, data)
    prior = replay(actor, data['request_id'], digest)
    if prior:
        return prior
    values = {key: data[key] for key in FIELDS}
    before = {}
    if pk:
        program = allowed(actor).get(pk=pk)
        before = snapshot(program)
        baseline = program.baseline_due or values['due_date']
        updated = allowed(actor).filter(pk=pk, revision=data['revision']).update(**values, baseline_due=baseline, revision=F('revision') + 1, updated_at=timezone.now())
        if not updated:
            raise Conflict('این برنامه در پنجره دیگری تغییر کرده است. اطلاعات شما حفظ شده؛ نسخه جدید را در پنجره‌ای دیگر بررسی کنید و فرم تازه‌ای باز کنید.')
        program.refresh_from_db()
    else:
        program = Program.objects.create(**values, baseline_due=values['due_date'], created_by=actor)
    AuditEvent.objects.create(program=program, actor=actor, action='ویرایش برنامه' if pk else 'ایجاد برنامه', before=before, after=snapshot(program))
    Mutation.objects.create(key=data['request_id'], actor=actor, fingerprint=digest, program=program)
    return program

@transaction.atomic
def record_followup(actor, pk, data):
    digest = fingerprint('followup', pk, data)
    prior = replay(actor, data['request_id'], digest)
    if prior:
        return prior
    program = allowed(actor).get(pk=pk)
    before = snapshot(program)
    updated = allowed(actor).filter(pk=pk, revision=data['revision']).update(next_step=data['next_step'], due_date=data['due_date'], baseline_due=program.baseline_due or data['due_date'], revision=F('revision') + 1, updated_at=timezone.now())
    if not updated:
        raise Conflict('اطلاعات برنامه تغییر کرده است؛ متن شما حفظ شده. نسخه جدید را بررسی و فرم تازه‌ای باز کنید.')
    FollowUp.objects.create(program=program, actor=actor, result=data['result'], request_id=data['request_id'])
    program.refresh_from_db()
    AuditEvent.objects.create(program=program, actor=actor, action='ثبت پیگیری', before=before, after=snapshot(program))
    Mutation.objects.create(key=data['request_id'], actor=actor, fingerprint=digest, program=program)
    return program
