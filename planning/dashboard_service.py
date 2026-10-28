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


CATALOG.update({
 'case-customer': ('کیس‌ها: مشتری','planning','columns'),
 'project-customer': ('پروژه‌ها: مشتری','projects','columns'),
 'backlog-customer': ('بکلاگ‌ها: مشتری','backlogs','columns'),
 'backlog-release': ('بکلاگ‌ها: ریلیز','backlogs','columns'),
 'periodic-customer': ('بازدید دوره‌ای: مشتری','periodic','columns'),
 'periodic-status': ('بازدید دوره‌ای: وضعیت','periodic','columns'),
})
FIELDS={'case-status':'source_status','case-customer':'customer','project-status':'status','project-phase':'phase','project-customer':'customer','backlog-status':'source_status','backlog-customer':'customer','backlog-service':'evidence.case_service','backlog-release':'evidence.release','periodic-city':'evidence.city','periodic-release':'evidence.release','periodic-customer':'customer','periodic-status':'source_status'}
KINDS=('ring','pie','columns','bars')

def dimension(record,source):
    value=record
    for field in FIELDS[source].split('.'):
        value=value.get(field) if isinstance(value,dict) else getattr(value,field,None)
    return str(value) if value not in (None,'') else 'نامشخص'

def aggregate(records,source,split='',contains=''):
    counts=Counter()
    for record in records:
        label=dimension(record,source)
        if contains and contains.casefold() not in label.casefold(): continue
        counts[(label,dimension(record,split) if split else '')]+=1
    pairs=sorted(counts,key=lambda pair:(-counts[pair],pair))
    rows=[{'label':a+(' · '+b if split else ''),'category':a,'series':b,'count':counts[(a,b)]} for a,b in pairs]
    return rows

def chart_data(user, specs):
    from integrations.views import active_snapshot, current_cases
    from projects.views import snapshot_for as projects_snapshot
    from planning.backlogs import snapshot_for as backlogs_snapshot
    snapshots={}; datasets={}; output=[]
    for spec in specs:
        title,module,default_kind=CATALOG[spec['source']]
        if module not in snapshots:
            snapshots[module]=(active_snapshot(user) if module=='planning' else projects_snapshot(user) if module=='projects' else backlogs_snapshot(user,module))
            datasets[module]=list(current_cases(user)) if module=='planning' else (snapshots[module].records if snapshots[module] else [])
        snapshot=snapshots[module];source=spec['source'];creation=None
        if source=='case-created':
            creation=creation_chart(datasets[module],timezone.localdate());rows=creation['rows']
        else:
            rows=aggregate(datasets[module],source,spec.get('split',''),spec.get('contains',''))
        route={'planning':'planning-dashboard','projects':'projects-dashboard','backlogs':'backlogs','periodic':'planning-periodic'}[module]
        output.append({**spec,'title':spec.get('title') or title,'rows':rows,'creation':creation,'snapshot':snapshot,'url':reverse(route)})
    return output
