/* Personal layouts; no record data is sent or stored in layout preferences. */
(async () => {
  const routes={'/':'home','/planning/':'planning','/planning/today/':'today','/projects/':'projects','/planning/backlogs/':'backlogs','/planning/visits/periodic/':'periodic','/planning/visits/onsite/':'onsite','/planning/upgrades/':'upgrades','/planning/suggestions/':'suggestions','/planning/actions/':'actions','/planning/attention/':'planning-attention','/projects/attention/':'projects-attention'};
  const host=document.getElementById('dashboard-builder'),custom=!!host;
  const key=custom?host.dataset.dashboardKey:routes[location.pathname];
  if(!key || !document.getElementById('main'))return;
  const endpoint='/preferences/dashboards/'+key+'/', elements=new Map();
  let specs=[],revision=0,editing=false,dirty=false,dragged=null;
  const make=(tag,text,cls)=>{const e=document.createElement(tag);if(text)e.textContent=text;if(cls)e.className=cls;return e;};
  const button=(text,action)=>{const b=make('button',text,'small-button');b.type='button';b.addEventListener('click',action);return b;};
  let saved;
  try {const response=await fetch(endpoint);if(!response.ok)return;saved=await response.json();revision=saved.revision;}catch{return;}
  let grid;
  if(custom){grid=host.querySelector('.personal-dashboard-grid');specs=saved.widgets;grid.querySelectorAll('[data-widget-id]').forEach(e=>elements.set(e.dataset.widgetId,e));}
  else {
    const candidates=Array.from(document.querySelectorAll('#main .stats > .stat, #main .charts-grid > .panel, #main .visual-main > .panel, #main .visual-secondary > .panel, #main > .visual-panel'));
    if(!candidates.length)return;
    grid=make('div',null,'personal-dashboard-grid');
    const first=candidates[0];let anchor=first;while(anchor.parentElement && anchor.parentElement.id!=='main')anchor=anchor.parentElement;
    anchor.before(grid);
    const parents=new Set();
    candidates.forEach((panel,index)=>{
      const title=(panel.querySelector('h2')||panel.firstElementChild)?.textContent.trim() || 'ابزارک';
      let hash=2166136261;for(const c of title)hash=Math.imul(hash^c.charCodeAt(0),16777619);
      let id='w-'+(hash>>>0).toString(16);if(elements.has(id))id+='-'+index;
      const tile=make('article',null,'dashboard-tile');tile.dataset.widgetId=id;
      parents.add(panel.parentElement);tile.append(panel);grid.append(tile);elements.set(id,tile);
      specs.push({id,width:panel.classList.contains('stat')?4:6,height:'normal',hidden:false});
    });
    parents.forEach(p=>{if(!p.children.length)p.hidden=true;});
    const defaults=new Map(specs.map(s=>[s.id,s]));
    specs=[...saved.widgets.filter(s=>defaults.has(s.id)),...specs.filter(s=>!saved.widgets.some(x=>x.id===s.id))];
  }
  const toolbar=make('div',null,'builder-toolbar');grid.before(toolbar);
  const status=make('span');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const mark=()=>{dirty=true;status.textContent='تغییرات ذخیره نشده است.';};
  function apply(){specs.forEach((s,index)=>{const tile=elements.get(s.id);if(!tile)return;tile.className='dashboard-tile tile-width-'+s.width+' tile-height-'+s.height;tile.hidden=s.hidden;if(grid.children[index]!==tile)grid.insertBefore(tile,grid.children[index]||null);});}
  const move=(id,step)=>{const i=specs.findIndex(s=>s.id===id),j=i+step;if(j<0||j>=specs.length)return;[specs[i],specs[j]]=[specs[j],specs[i]];apply();mark();elements.get(id).querySelector('.widget-drag')?.focus();};
  function controls(spec){
    const tile=elements.get(spec.id);if(!tile||tile.querySelector('.widget-controls'))return;
    const bar=make('div',null,'widget-controls');
    const drag=button('⠿',()=>{});drag.classList.add('widget-drag');drag.draggable=false;drag.setAttribute('aria-label','جابه‌جایی ابزارک؛ از کلیدهای بالا و پایین استفاده کنید');
    drag.addEventListener('keydown',e=>{if(e.key==='ArrowUp'||e.key==='ArrowDown'){e.preventDefault();move(spec.id,e.key==='ArrowUp'?-1:1);}});
    drag.addEventListener('pointerdown',e=>{
      if(e.button!==0)return;
      const startX=e.clientX,startY=e.clientY;
      drag.setPointerCapture(e.pointerId);
      let target=null;
      const track=event=>{
        if(Math.abs(event.clientX-startX)+Math.abs(event.clientY-startY)<8)return;
        tile.classList.add('dragging');
        const hit=document.elementFromPoint(event.clientX,event.clientY)?.closest('.dashboard-tile');
        grid.querySelectorAll('.drop-target').forEach(x=>x.classList.remove('drop-target'));
        target=hit&&hit!==tile&&grid.contains(hit)?hit:null;
        target?.classList.add('drop-target');
      };
      const finish=event=>{
        drag.removeEventListener('pointermove',track);drag.removeEventListener('pointerup',finish);drag.removeEventListener('pointercancel',finish);
        tile.classList.remove('dragging');grid.querySelectorAll('.drop-target').forEach(x=>x.classList.remove('drop-target'));
        if(event.type==='pointerup'&&target){const from=specs.findIndex(s=>s.id===spec.id),to=specs.findIndex(s=>s.id===target.dataset.widgetId);const [item]=specs.splice(from,1);specs.splice(to,0,item);apply();mark();}
      };
      drag.addEventListener('pointermove',track);drag.addEventListener('pointerup',finish);drag.addEventListener('pointercancel',finish);
    });
    drag.addEventListener('dragstart',e=>{dragged=spec.id;e.dataTransfer.setData('text/plain',spec.id);tile.classList.add('dragging');});
    drag.addEventListener('dragend',()=>{dragged=null;tile.classList.remove('dragging');grid.querySelectorAll('.drop-target').forEach(x=>x.classList.remove('drop-target'));});
    tile.addEventListener('dragover',e=>{if(editing&&dragged&&dragged!==spec.id){e.preventDefault();tile.classList.add('drop-target');}});
    tile.addEventListener('dragleave',()=>tile.classList.remove('drop-target'));
    tile.addEventListener('drop',e=>{if(!editing||!dragged||dragged===spec.id)return;e.preventDefault();const from=specs.findIndex(s=>s.id===dragged),to=specs.findIndex(s=>s.id===spec.id);const [item]=specs.splice(from,1);specs.splice(to,0,item);tile.classList.remove('drop-target');apply();mark();});
    bar.append(drag,button('↑',()=>move(spec.id,-1)),button('↓',()=>move(spec.id,1)));
    function select(label,field,options){const wrap=make('label',label),sel=make('select');sel.setAttribute('aria-label',label);options.forEach(([value,text])=>{const o=make('option',text);o.value=value;sel.append(o);});sel.value=spec[field];sel.addEventListener('change',()=>{spec[field]=field==='width'?Number(sel.value):sel.value;apply();mark();});wrap.append(sel);bar.append(wrap);return sel;}
    const width=select('عرض','width',[[4,'یک‌سوم'],[6,'نصف'],[8,'دوسوم'],[12,'کامل']]);
    const height=select('ارتفاع','height',[['compact','کوتاه'],['normal','معمولی'],['tall','بلند']]);
    bar.append(button('پنهان',()=>{spec.hidden=true;apply();refreshHidden();mark();}));if(custom)bar.append(button('حذف ابزارک',()=>{specs=specs.filter(s=>s.id!==spec.id);elements.delete(spec.id);tile.remove();refreshHidden();mark();}));tile.prepend(bar);
    const resize=button('◲',()=>{const sizes=[4,6,8,12];spec.width=sizes[(sizes.indexOf(spec.width)+1)%4];width.value=spec.width;apply();mark();});resize.className='widget-resize';resize.setAttribute('aria-label','تغییر اندازه؛ کلیک برای عرض بعدی یا کشیدن گوشه');
    resize.addEventListener('pointerdown',e=>{if(e.button!==0)return;const x=e.clientX,y=e.clientY,initialWidth=tile.getBoundingClientRect().width,initialHeight=tile.getBoundingClientRect().height;let moved=false;resize.setPointerCapture(e.pointerId);
      const onMove=event=>{if(Math.abs(event.clientX-x)+Math.abs(event.clientY-y)<8)return;moved=true;const unit=grid.getBoundingClientRect().width/12,target=(initialWidth+x-event.clientX)/unit;spec.width=[4,6,8,12].reduce((a,b)=>Math.abs(b-target)<Math.abs(a-target)?b:a);spec.height=initialHeight+event.clientY-y<330?'compact':initialHeight+event.clientY-y>510?'tall':'normal';width.value=spec.width;height.value=spec.height;apply();mark();};
      const end=()=>{resize.removeEventListener('pointermove',onMove);resize.removeEventListener('pointerup',end);resize.removeEventListener('pointercancel',end);if(moved)resize.addEventListener('click',event=>{event.stopImmediatePropagation();event.preventDefault();},{once:true,capture:true});};
      resize.addEventListener('pointermove',onMove);resize.addEventListener('pointerup',end);resize.addEventListener('pointercancel',end);
    });tile.append(resize);
  }
  const hiddenSelect=make('select');hiddenSelect.setAttribute('aria-label','ابزارک‌های پنهان');
  function refreshHidden(){hiddenSelect.replaceChildren();const first=make('option','نمایش دوباره ابزارک پنهان…');first.value='';hiddenSelect.append(first);specs.filter(s=>s.hidden).forEach(s=>{const o=make('option',elements.get(s.id)?.querySelector('h2')?.textContent||'کارت '+s.id);o.value=s.id;hiddenSelect.append(o);});hiddenSelect.hidden=!editing||!specs.some(s=>s.hidden);}
  hiddenSelect.addEventListener('change',()=>{const spec=specs.find(s=>s.id===hiddenSelect.value);if(spec){spec.hidden=false;apply();refreshHidden();mark();}});
  const edit=button('ویرایش چیدمان',()=>{editing=!editing;grid.classList.toggle('layout-editing',editing);edit.textContent=editing?'پایان ویرایش':'ویرایش چیدمان';edit.setAttribute('aria-pressed',editing);save.hidden=!editing;reset.hidden=!editing;refreshHidden();if(custom)host.querySelector('.builder-catalog').hidden=!editing;});edit.setAttribute('aria-pressed','false');
  async function persist(resetAll=false){
    save.disabled=true;status.textContent='در حال ذخیره…';
    try{const csrf=document.querySelector('[name=csrfmiddlewaretoken]')?.value || decodeURIComponent(document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.split('=').slice(1).join('=')||'');
      const response=await fetch(endpoint,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({widgets:resetAll?[]:specs,revision,title:custom?document.getElementById('personal-title').value:undefined})});if(!(response.headers.get('Content-Type')||'').includes('application/json'))throw new Error('نشست ورود یا مجوز ذخیره معتبر نیست؛ صفحه را تازه کنید و دوباره وارد شوید.');const result=await response.json();if(!response.ok)throw new Error(result.error||'ذخیره انجام نشد.');revision=result.revision;dirty=false;status.textContent='چیدمان در حساب شما ذخیره شد.';if(custom||resetAll)location.reload();
    }catch(error){status.textContent=error.message||'ارتباط برقرار نشد؛ تغییرات شما هنوز ذخیره نشده است.';}finally{save.disabled=false;}
  }
  const save=button('ذخیره چیدمان',()=>persist()),reset=button(custom?'خالی‌کردن داشبورد':'بازگشت به چیدمان پیش‌فرض',()=>{if(confirm('چیدمان این صفحه بازنشانی شود؟ داده‌های CRM تغییری نمی‌کنند.'))persist(true);});save.hidden=true;reset.hidden=true;
  toolbar.append(edit,save,reset,hiddenSelect,status);specs.forEach(controls);refreshHidden();apply();
  if(custom){
    document.getElementById('personal-title').addEventListener('input',mark);
    document.getElementById('widget-source').addEventListener('change',e=>{const kinds=document.getElementById('widget-kind');kinds.value=e.target.value==='case-created'?'line':'ring';Array.from(kinds.options).forEach(o=>o.disabled=e.target.value==='case-created'?o.value!=='line':o.value==='line');});
    document.getElementById('widget-source').dispatchEvent(new Event('change'));
    document.getElementById('add-widget').addEventListener('click',()=>{if(specs.length>=30){status.textContent='حداکثر ۳۰ ابزارک در هر داشبورد.';return;}const source=document.getElementById('widget-source'),kind=document.getElementById('widget-kind').value;const spec={id:'w-'+crypto.randomUUID(),source:source.value,kind,width:6,height:'normal',hidden:false};const tile=make('article',null,'dashboard-tile'),panel=make('section',null,'panel padded');tile.dataset.widgetId=spec.id;panel.append(make('h2',source.selectedOptions[0].textContent),make('p','پس از ذخیره چیدمان، اطلاعات همین منبع نمایش داده می‌شود.'));tile.append(panel);elements.set(spec.id,tile);specs.push(spec);controls(spec);apply();mark();});
  }
  window.addEventListener('beforeunload',e=>{if(dirty){e.preventDefault();e.returnValue='';}});
})();
