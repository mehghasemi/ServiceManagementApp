"""Dashboard catalog and scoped data adapters; no evaluation rules live here."""
from collections import Counter
from django.urls import reverse
from django.utils import timezone
from planning.charts import status_distribution, creation_chart

BUILTINS = {'home','planning','today','projects','backlogs','periodic','onsite','upgrades','suggestions','actions','planning-attention','projects-attention'}
CATALOG = {
 'case-status': ('وضعیت کیس‌ها','planning','ring'),
 'case-created': ('ماه ایجاد کیس‌های موجود','planning','line'),
 'project-status': ('وضعیت پروژه‌ها','projects','ring'),
 'project-phase': ('مرحله پروژه‌ها','projects','columns'),
 'backlog-status': ('وضعیت بکلاگ‌ها','backlogs','ring'),
 'backlog-service': ('دسته خدمت بکلاگ‌ها','backlogs','columns'),
 'periodic-city': ('بازدید دوره‌ای به تفکیک شهر','periodic','columns'),
 'periodic-release': ('بازدید دوره‌ای به تفکیک ریلیز','periodic','columns'),
}

def chart_data(user, specs):
    from integrations.views import active_snapshot, current_cases
    from projects.views import snapshot_for as projects_snapshot
    from planning.backlogs import snapshot_for as backlogs_snapshot
    snapshots={}; cache={}; output=[]
    for spec in specs:
        title,module,default_kind=CATALOG[spec['source']]
        if module not in snapshots:
            snapshots[module]=(active_snapshot(user) if module=='planning' else projects_snapshot(user) if module=='projects' else backlogs_snapshot(user,module))
        snapshot=snapshots[module]
        source=spec['source']
        if source not in cache:
            rows=[]; creation=None
            if module=='planning':
                cases=current_cases(user)
                if source=='case-status': rows=status_distribution(cases)
                else: creation=creation_chart(cases,timezone.localdate())
            elif snapshot:
                records=snapshot.records
                if source=='project-status': values=[r.get('status') for r in records]
                elif source=='project-phase': values=[r.get('phase') for r in records]
                elif source=='backlog-status': values=[r.get('source_status') for r in records]
                else:
                    field={'backlog-service':'case_service','periodic-city':'city','periodic-release':'release'}[source]
                    values=[r.get('evidence',{}).get(field) for r in records]
                rows=[{'label':str(label or 'نامشخص'),'count':count} for label,count in Counter(values).most_common()]
            cache[source]=(rows,creation)
        rows,creation=cache[source]
        route={'planning':'planning-dashboard','projects':'projects-dashboard','backlogs':'backlogs','periodic':'planning-periodic'}[module]
        output.append({**spec,'title':title,'rows':rows,'creation':creation,'snapshot':snapshot,'url':reverse(route)})
    return output
