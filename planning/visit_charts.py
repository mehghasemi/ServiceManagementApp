from collections import defaultdict
from criteria.engine import matches


def visit_breakdown(rows,rules):
    completed=[r for r in rules if r.purpose=='completed']
    pending=[r for r in rules if r.purpose=='pending']
    centers={}
    cities={}
    for row in rows:
        evidence=row['evidence']
        state=evidence.get('state')
        facts={**evidence,'source_status':row.get('source_status') or None,'active':state==0 if state is not None else None}
        done=any(matches(r,facts) is True for r in completed)
        todo=any(matches(r,facts) is True for r in pending)
        status='done' if done and not todo else 'pending' if todo and not done else 'unknown'
        # Unknown customer identities stay separate, never grouped by similar name.
        key=row.get('customer_id') or row['crm_id']
        for groups,key,label in [(centers,key,row.get('customer') or 'مرکز نامشخص'),(cities,evidence.get('city') or '',evidence.get('city') or 'شهر دریافت نشده')]:
            item=groups.setdefault(key,{'label':label,'total':0,'done':0,'pending':0,'unknown':0})
            item['total']+=1;item[status]+=1
    def chart(groups):
        peak=max((r['total'] for r in groups.values()),default=1)
        result=sorted(groups.values(),key=lambda r:(-r['total'],r['label']))
        for row in result:
            for field in ('done','pending','unknown'):row[field+'_width']=round(row[field]/peak*100,3)
        return result
    return chart(centers),chart(cities)


def city_columns(rows):
    """Linear zero-based axis with readable integer tick intervals."""
    import math
    peak=max((row['total'] for row in rows),default=0)
    rough=max(1,peak/5)
    magnitude=10**math.floor(math.log10(rough))
    step=next(n*magnitude for n in (1,2,5,10) if n*magnitude>=rough)
    ceiling=max(step,math.ceil(peak/step)*step)
    result=[]
    for index,row in enumerate(sorted(rows,key=lambda r:r['label'])):
        height=round(row['total']/ceiling*180,3)
        result.append({**row,'x':65+index*70,'y':210-height,'height':height,'label_y':235+(index%2)*20})
    return {'bars':result,'width':max(450,100+70*len(rows)),'ticks':[{'value':n,'y':210-n/ceiling*180} for n in range(0,ceiling+1,step)]}
