from django.urls import reverse


# Public normalized fields, not arbitrary ORM introspection: credentials and local
# permission/audit tables must never become selectable reporting entities.
FIELDS = {
    'id': ('شناسه رکورد', 'text'), 'number': ('شماره', 'text'), 'title': ('عنوان', 'text'),
    'customer_id': ('شناسه مشتری', 'text'), 'customer': ('مشتری / مرکز', 'text'),
    'status': ('وضعیت', 'text'), 'city': ('شهر', 'text'), 'version': ('نگارش فعلی', 'text'),
    'owner': ('مسئول ثبت‌شده', 'text'), 'created': ('تاریخ ایجاد', 'date'), 'modified': ('تاریخ ویرایش', 'date'),
    'release': ('ریلیز / ماه برنامه', 'text'), 'sprint': ('اسپرینت / هفته برنامه', 'text'),
    'service': ('دسته خدمت', 'text'), 'type': ('نوع رکورد', 'text'), 'category': ('نوع درخواست', 'text'),
    'parent_id': ('شناسه بکلاگ مرتبط', 'text'), 'notes_count': ('تعداد یادداشت دریافت‌شده', 'number'),
    'activities_count': ('تعداد فعالیت دریافت‌شده', 'number'), 'phase': ('مرحله پروژه', 'text'),
    'manager': ('مدیر پروژه', 'text'), 'planned_end': ('موعد برنامه', 'date'),
    'due': ('موعد فعالیت', 'date'), 'case_count': ('تعداد کیس در منبع جاری', 'number'),
}
SOURCE_LABELS = {'cases': 'کیس‌های View برنامه‌ریزی', 'backlogs': 'بکلاگ‌های View عمومی',
                 'periodic': 'بکلاگ‌های View بازدید دوره‌ای', 'projects': 'پروژه‌های View',
                 'customers': 'مشتریان موجود در کیس‌های دریافت‌شده', 'activities': 'فعالیت‌های دریافت‌شده کیس‌ها'}
BASE = ('id', 'number', 'title', 'customer_id', 'customer', 'status', 'city', 'version', 'owner', 'created', 'modified',
        'release', 'sprint', 'service', 'type', 'category', 'parent_id', 'notes_count', 'activities_count')
CONTRACTS = {'cases': BASE, 'backlogs': BASE, 'periodic': BASE,
    'projects': ('id', 'title', 'customer', 'customer_id', 'status', 'phase', 'manager', 'planned_end', 'notes_count'),
    'customers': ('id', 'customer', 'city', 'version', 'case_count'),
    'activities': ('id', 'title', 'status', 'due', 'customer', 'customer_id', 'parent_id')}


def schema():
    result = {}
    for source, keys in CONTRACTS.items():
        fields = {key: {'label': FIELDS[key][0], 'type': FIELDS[key][1]} for key in keys}
        relations = []
        if source == 'cases':
            for key in BASE:
                fields['backlog.' + key] = {'label': 'بکلاگ مرتبط ← ' + FIELDS[key][0], 'type': FIELDS[key][1], 'relation': 'backlog'}
            relations.append({'key': 'backlog', 'label': 'کیس ← بکلاگ مرتبط (parent_id)', 'cardinality': 'many-to-one'})
        result[source] = {'label': SOURCE_LABELS[source], 'fields': fields, 'relations': relations}
    return result


def normalized(record, snapshot, url=''):
    ev = record.get('evidence') or {}
    coverage = snapshot.coverage if snapshot else {}
    return dict(id=str(record.get('crm_id') or record.get('id') or ''), number=record.get('number'), title=record.get('title'),
        customer_id=record.get('customer_id'), customer=record.get('customer'), status=record.get('source_status', record.get('status')),
        city=ev.get('city'), version=ev.get('automation_version'), owner=ev.get('owner'), created=ev.get('created_on'),
        modified=ev.get('modified_on'), release=ev.get('release'), sprint=ev.get('sprint'), service=ev.get('case_service'),
        type=ev.get('incident_type'), category=ev.get('case_category'), parent_id=record.get('parent_id'),
        notes_count=len(ev.get('notes') or record.get('notes') or []) if coverage.get('notes') else None,
        activities_count=len(ev.get('activities') or []) if coverage.get('activities') else None,
        phase=record.get('phase'), manager=record.get('manager'), planned_end=record.get('planned_end'), _url=url)


class Sources:
    LIMIT = 50000

    def __init__(self, user):
        self.user, self.cache = user, {}

    def load(self, source):
        if source not in CONTRACTS:
            raise ValueError('منبع داده مجاز نیست.')
        if source in self.cache:
            return self.cache[source]
        from integrations.views import current_cases, active_snapshot
        from planning.backlogs import snapshot_for
        from projects.views import snapshot_for as project_snapshot
        if source in ('cases', 'activities', 'customers'):
            snapshot = active_snapshot(self.user)
            raw = list(current_cases(self.user)[:self.LIMIT + 1])
            if len(raw) > self.LIMIT:
                raise ValueError('حجم منبع بیش از حد مجاز است؛ View محدودتری انتخاب کنید.')
            if source == 'cases':
                parents, _ = self.load('backlogs')
                parents = {r['id'].lower(): r for r in parents}
                rows = []
                for case in raw:
                    values = {k: getattr(case, k) for k in ('crm_id', 'number', 'title', 'customer_id', 'customer', 'source_status', 'parent_id', 'evidence')}
                    row = normalized(values, snapshot, reverse('crm-case', args=[case.pk]))
                    parent = parents.get(str(case.parent_id or '').lower(), {})
                    row.update({'backlog.' + key: parent.get(key) for key in BASE})
                    rows.append(row)
            elif source == 'customers':
                groups = {}
                for case in raw:
                    if not case.customer_id:
                        continue
                    key = str(case.customer_id).lower()
                    row = groups.setdefault(key, {'id': key, 'customer': case.customer, 'case_count': 0,
                        'cities': set(), 'versions': set(), '_url': reverse('planning-dashboard') + '?customer=' + key})
                    row['case_count'] += 1
                    row['cities'].add(case.evidence.get('city') or None)
                    row['versions'].add(case.evidence.get('automation_version') or None)
                rows = []
                for row in groups.values():
                    row['city'] = next(iter(row['cities'])) if len(row['cities']) == 1 else None
                    row['version'] = next(iter(row['versions'])) if len(row['versions']) == 1 else None
                    row.pop('cities'); row.pop('versions'); rows.append(row)
            else:
                rows = []
                for case in raw:
                    for item in case.evidence.get('activities') or []:
                        if item.get('id'):
                            rows.append({'id': str(item['id']), 'title': item.get('title'), 'status': item.get('state_label'),
                                'due': item.get('due'), 'customer': case.customer, 'customer_id': case.customer_id,
                                'parent_id': str(case.crm_id), '_url': reverse('crm-case', args=[case.pk])})
        else:
            snapshot = project_snapshot(self.user) if source == 'projects' else snapshot_for(self.user, source)
            raw = snapshot.records if snapshot else []
            route = {'projects': 'project-detail', 'periodic': 'periodic-detail', 'backlogs': 'backlog-detail'}[source]
            rows = [normalized(r, snapshot, reverse(route, args=[r.get('id') if source == 'projects' else r['crm_id']])) for r in raw]
        if len(rows) > self.LIMIT:
            raise ValueError('حجم منبع بیش از حد مجاز است؛ View محدودتری انتخاب کنید.')
        rows = list({r['id']: r for r in rows if r['id']}.values())
        meta = {'available': snapshot is not None, 'source_name': snapshot.source_name if snapshot else '',
                'received': snapshot.fetched_at.isoformat() if snapshot else None,
                'coverage': snapshot.coverage if snapshot else {}, 'count': len(rows),
                'limitations': 'فقط داده View فعلی؛ تاریخ ایجاد، تاریخچه کامل حجم کار یا تاریخ واقعی رفع نیست. مشتری از کیس‌ها استخراج می‌شود؛ استان و زمان واقعی رفع در قرارداد فعلی وجود ندارند.'}
        if source == 'activities' and not meta['coverage'].get('activities'):
            meta['available'] = False
        self.cache[source] = rows, meta
        return rows, meta
