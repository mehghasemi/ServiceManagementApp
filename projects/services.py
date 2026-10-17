from collections import Counter
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime, parse_date
from integrations.analysis import guid, label
from integrations.client import CRMError, Cancelled
from integrations.models import ProjectSnapshot, SyncJob


def day(value):
    if not value:
        return None
    try:
        stamp = parse_datetime(str(value))
        return timezone.localtime(stamp).date() if stamp and timezone.is_aware(stamp) else stamp.date() if stamp else parse_date(str(value))
    except (ValueError, TypeError):
        return None


def normalize_projects(rows, notes):
    by_target = {}
    for note in notes or []:
        target = guid(note.get('_objectid_value') or note.get('objectid'))
        by_target.setdefault(target, {})[guid(note.get('annotationid'))] = {
            'title': note.get('subject') or '', 'text': note.get('notetext') or '',
            'date': note.get('modifiedon') or note.get('createdon') or '',
        }
    result = {}
    for row in rows:
        identifier = guid(row.get('brd_projectid'))
        if not identifier:
            raise CRMError('شناسه پروژه در View معتبر نیست؛ دریافت منتشر نشد.')
        result[identifier] = {
            'id': identifier, 'title': row.get('brd_name') or '', 'status': label(row, 'statuscode'),
            'state': row.get('statecode'), 'customer': label(row, '_brd_account_value') or label(row, '_brd_customer_value'),
            'manager': label(row, '_brd_projectmanager_value'), 'phase': label(row, 'brd_currentphase'),
            'planned_end': row.get('brd_plannedenddate'), 'actual_end': row.get('brd_realenddate'),
            'last_note_date': row.get('brd_lastnotedate'), 'last_action': row.get('brd_lastaction') or '',
            'notes': sorted(by_target.get(identifier, {}).values(), key=lambda n: n['date'], reverse=True),
        }
    return list(result.values())


def publish_snapshot(job, client, checkpoint):
    views = job.config['views']
    rows, _, name = client.fetch_view(views['case_view'])
    identifiers = sorted({guid(r.get('brd_projectid')) for r in rows})
    if '' in identifiers:
        raise CRMError('شناسه پروژه نامعتبر است.')
    notes = None
    if 'note_view' in views:
        notes = []
        for offset in range(0, len(identifiers), 100):
            notes.extend(client.fetch_view(views['note_view'], related_ids=identifiers[offset:offset+100])[0])
    records = normalize_projects(rows, notes)
    checkpoint('ذخیره دریافت کامل پروژه‌ها و یادداشت‌ها', len(records))
    with transaction.atomic():
        if SyncJob.objects.select_for_update().get(pk=job.pk).cancel_requested:
            raise Cancelled('دریافت لغو شد؛ داده قبلی حفظ شد.')
        ProjectSnapshot.objects.create(owner=job.owner, scope=job.scope, selection_key=job.config['selection_key'],
            job=job, source_name=name, records=records, coverage={'notes': notes is not None, 'note_view': views.get('note_view', {}).get('name'), 'mode': 'full'})
        SyncJob.objects.filter(pk=job.pk).update(status='success', progress=len(records), finished_at=timezone.now(), message=f'{len(records)} پروژه یکتا و یادداشت‌های مرتبط دریافت شد')



def dashboard_data(records, notes_loaded, options, today):
    from criteria.engine import ensure_rules, project_facts, evaluate_records
    rules = ensure_rules(options)
    rows = [dict(r) for r in records]
    evaluated, counts = evaluate_records([(r, project_facts(r, options, notes_loaded, today)) for r in rows], rules)
    by_id = {entry['item']['id']: entry['rules'] for entry in evaluated}
    for row in rows:
        row['attention_rules'] = by_id.get(row['id'], [])
        row['last_report'] = day(row['notes'][0]['date']) if row.get('notes') else None
    statuses = Counter(r['status'] or 'نامشخص' for r in rows)
    peak = max(statuses.values(), default=1)
    charts = [{'label': key, 'count': count, 'width': round(count*100/peak, 1)} for key, count in statuses.most_common()]
    return rows, charts, counts
