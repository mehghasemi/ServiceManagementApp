/* Shared Persian calendar selector. ISO is accepted on load; submissions use Jalali dates. */
(()=>{
 const fmt=new Intl.DateTimeFormat('en-US-u-ca-persian-nu-latn',{year:'numeric',month:'numeric',day:'numeric',timeZone:'UTC'});
 const parts=date=>{const p=Object.fromEntries(fmt.formatToParts(date).map(x=>[x.type,x.value]));return [Number(p.year),Number(p.month),Number(p.day)];};
 const digits=s=>String(s||'').replace(/[۰-۹]/g,c=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).replace(/[٠-٩]/g,c=>String('٠١٢٣٤٥٦٧٨٩'.indexOf(c))).replace(/[\u200e\u200f]/g,'');
 function parse(value){const s=digits(value).trim();if(!s)return [];if(/^\d{4}-\d{2}-\d{2}/.test(s)){const d=new Date(s.slice(0,10)+'T12:00:00Z');return Number.isNaN(d.getTime())?[]:parts(d);}const p=s.split('/').map(Number);return p.length===3&&p.every(Number.isFinite)?p:[];}
 const months=['فروردین','اردیبهشت','خرداد','تیر','مرداد','شهریور','مهر','آبان','آذر','دی','بهمن','اسفند'];
 function days(y,m){if(m<7)return 31;if(m<12)return 30;for(let d=18;d<=22;d++){const p=parts(new Date(Date.UTC(y+622,2,d)));if(p[0]===y&&p[1]===12&&p[2]===30)return 30;}return 29;}
 function attach(raw,range=false){if(raw._jalali)raw._jalali.remove();const group=document.createElement('span');group.className='jalali-picker';raw.type='hidden';raw.insertAdjacentElement('afterend',group);raw._jalali=group;const initial=raw.value.split('|').map(s=>s.trim()),controls=[];
  for(let i=0;i<(range?2:1);i++){
   const unit=document.createElement('span');unit.className='jalali-date';const caption=(raw.getAttribute('aria-label')||raw.name||'تاریخ')+(range?(i?' تا':' از'):'');
   const y=document.createElement('input');y.type='number';y.min='1';y.max='3177';y.placeholder='سال';y.setAttribute('aria-label',caption+'؛ سال');
   const m=document.createElement('select'),d=document.createElement('select');m.setAttribute('aria-label',caption+'؛ ماه');d.setAttribute('aria-label',caption+'؛ روز');m.add(new Option('ماه',''));months.forEach((v,j)=>m.add(new Option(v,String(j+1))));const p=parse(initial[i]);y.value=p[0]||'';m.value=p[1]||'';
   function redraw(selected){d.replaceChildren(new Option('روز',''));const count=days(Number(y.value)||parts(new Date())[0],Number(m.value)||1);for(let n=1;n<=count;n++)d.add(new Option(String(n),String(n)));d.value=selected&&Number(selected)<=count?String(selected):'';}
   redraw(p[2]);controls.push([y,m,d]);if(range){const label=document.createElement('small');label.textContent=i?'تا':'از';unit.append(label);}unit.append(y,m,d);group.append(unit);
   y.addEventListener('change',()=>{redraw(d.value);sync();});m.addEventListener('change',()=>{redraw(d.value);sync();});d.addEventListener('change',sync);
  }
  function sync(){let incomplete=false;const values=controls.map(([y,m,d])=>{const any=y.value||m.value||d.value,full=y.value&&m.value&&d.value;const invalid=any&&(!full||Number(y.value)<1||Number(y.value)>3177);y.setCustomValidity(invalid?'سال، ماه و روز را کامل انتخاب کنید.':'');incomplete=incomplete||!!invalid;return full?`${y.value.padStart(4,'0')}/${m.value.padStart(2,'0')}/${d.value.padStart(2,'0')}`:'';});if(range&&values.some(Boolean)&&!values.every(Boolean)){controls[0][0].setCustomValidity('هر دو تاریخ ابتدا و انتها را انتخاب کنید.');incomplete=true;}if(incomplete){raw.dataset.dateIncomplete='true';return;}delete raw.dataset.dateIncomplete;raw.value=values.every(v=>!v)?'':values.join(' | ');raw.dispatchEvent(new Event('input',{bubbles:true}));raw.dispatchEvent(new Event('change',{bubbles:true}));}
  const clear=document.createElement('button');clear.type='button';clear.className='small-button';clear.textContent='پاک‌کردن تاریخ';clear.addEventListener('click',()=>{controls.flat().forEach(c=>c.value='');sync();});group.append(clear);return group;
 }
 function detach(raw){raw._jalali?.remove();raw._jalali=null;delete raw.dataset.dateIncomplete;raw.type='text';}
 window.ServiceDatePicker={attach,detach,parse,days};
 const mount=()=>document.querySelectorAll('input[data-jalali]:not([type=hidden])').forEach(raw=>attach(raw,raw.dataset.jalali==='range'));
 document.addEventListener('DOMContentLoaded',mount);if(document.readyState!=='loading')mount();
})();
