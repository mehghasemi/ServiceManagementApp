(()=>{
'use strict';
const host=document.getElementById('criterion-tree'), hidden=document.getElementById('id_expression_data'), metric=document.getElementById('id_metric');
if(!host||!hidden||!metric)return;
const catalog=JSON.parse(document.getElementById('criterion-catalogue').textContent), byKey=Object.fromEntries(catalog.map(x=>[x.key,x]));
const section=document.getElementById('criterion-builder'), feedback=document.getElementById('criterion-feedback');
const timeDefault=()=>({version:1,days:30,calendar:'calendar',statuses:[],weekends:[4],holidays:[],responses:['staff_note']});
const firstField=byKey.source_status||byKey.status||catalog[0];
const leaf=()=>({metric:firstField.key,operator:firstField.operators[0].key,value:defaultValue(firstField)});
function defaultValue(field){return field.temporal?timeDefault():field.kind==='number'?30:field.kind==='bool'?true:[];}
let tree;
try{tree=JSON.parse(hidden.value).root;}catch{tree={join:'all',children:[leaf()]};}
function el(tag,text){const n=document.createElement(tag);if(text)n.textContent=text;return n;}
function button(text,action){const n=el('button',text);n.type='button';n.addEventListener('click',action);return n;}
function label(text,input){const n=el('label',text);n.append(input);return n;}
function select(options,value,onChange){const n=el('select');for(const [key,text] of options){const o=el('option',text);o.value=key;n.append(o);}n.value=value;n.addEventListener('change',()=>{onChange(n.value);sync();});return n;}
function input(value,onInput,multi=false){const n=el(multi?'textarea':'input');if(multi)n.rows=2;n.value=value;n.addEventListener('input',()=>{onInput(n.value);sync();});return n;}
const lines=v=>v.split(/[\n،,]/).map(s=>s.trim()).filter(Boolean);
function sync(){hidden.value=JSON.stringify({version:1,root:tree});}
function total(n){return 1+(n.children||[]).reduce((s,c)=>s+total(c),0);}
function render(){host.replaceChildren(draw(tree,null,0,1));sync();}
function remove(parent,index){parent.children.splice(index,1);render();host.querySelector('button')?.focus();}
function draw(node,parent,index,depth){
 if(node.join){
  const box=el('fieldset');box.className='criterion-group';box.append(el('legend',depth===1?'ترکیب اصلی':'گروه شرط'));
  const bar=el('div');bar.className='criterion-controls';
  bar.append(label('رابطه شرط‌ها',select([['all','همه شرط‌ها برقرار باشند (و)'],['any','حداقل یک شرط برقرار باشد (یا)']],node.join,v=>node.join=v)));
  function add(group){if(total(tree)>=40||node.children.length>=20||depth>=4||(group&&depth>=3)){feedback.textContent='حداکثر ۴ سطح، ۴۰ جزء و ۲۰ شرط در هر گروه مجاز است.';return;}node.children.push(group?{join:'all',children:[leaf()]}:leaf());render();}
  bar.append(button('افزودن شرط',()=>add(false)),button('افزودن گروه',()=>add(true)));
  if(parent)bar.append(button('حذف گروه',()=>remove(parent,index)));
  box.append(bar);node.children.forEach((child,i)=>box.append(draw(child,node,i,depth+1)));return box;
 }
 const row=el('div');row.className='criterion-leaf';const field=byKey[node.metric];
 if(!field){row.append(el('p','فیلد این شرط دیگر در دسترس نیست؛ شرط را حذف و دوباره تعریف کنید.'));if(parent)row.append(button('حذف شرط',()=>remove(parent,index)));return row;}
 row.append(label('فیلد',select(catalog.map(f=>[f.key,f.label]),node.metric,v=>{node.metric=v;node.operator=byKey[v].operators[0].key;node.value=defaultValue(byKey[v]);render();})));
 row.append(label('شرط',select(field.operators.map(o=>[o.key,o.label]),node.operator,v=>node.operator=v)));
 if(field.temporal){
  const value=node.value, days=input(value.days,v=>value.days=number(v));days.inputMode='numeric';row.append(label('تعداد روز',days));
  const details=el('details');details.append(el('summary','تقویم و شواهد زمانی'));
  const options=el('div');options.className='criterion-time-options';
  options.append(label('تقویم',select([['calendar','روز تقویمی'],['working','روز کاری']],value.calendar,v=>value.calendar=v)));
  options.append(label('وضعیت‌ها؛ هر مقدار یک خط (خالی: همه)',input(value.statuses.join('\n'),v=>value.statuses=lines(v),true)));
  function checks(title,choices,key){const fieldset=el('fieldset');fieldset.append(el('legend',title));const group=el('div');group.className='criterion-checks';for(const [k,text] of choices){const check=el('input');check.type='checkbox';check.checked=value[key].includes(k);check.addEventListener('change',()=>{value[key]=check.checked?[...value[key],k]:value[key].filter(x=>x!==k);sync();});group.append(label(text,check));}fieldset.append(group);return fieldset;}
  options.append(checks('تعطیلات هفتگی؛ برای روز کاری',[[5,'شنبه'],[6,'یکشنبه'],[0,'دوشنبه'],[1,'سه‌شنبه'],[2,'چهارشنبه'],[3,'پنجشنبه'],[4,'جمعه']],'weekends'));
  options.append(label('تعطیلات موردی شمسی؛ هر تاریخ یک خط',input(value.holidays.map(jalali).join('\n'),v=>value.holidays=lines(v),true)));
  if(node.metric==='customer_wait')options.append(checks('پیگیری معتبر',[['staff_note','پاسخ کارشناس'],['phone_call','تماس مرتبط'],['local_action','پیگیری محلی انجام‌شده'],['status_change','تغییر وضعیت']],'responses'));
  details.append(options,el('small','تاریخ ورود به وضعیت و تشخیص پیام مشتری نیازمند اتصال شواهد CRM هستند؛ نبود پوشش کامل نتیجه نامشخص دارد. روزها تقویمی‌اند، نه ساعت دقیق SLA.'));row.append(details);
 }else if(field.kind==='bool')row.append(label('مقدار',select([['true','بله'],['false','خیر']],String(node.value),v=>node.value=v==='true')));
 else if(field.kind==='number'){const n=input(node.value,v=>node.value=number(v));n.inputMode='numeric';row.append(label('مقدار',n));}
 else row.append(label('مقادیر؛ هر مقدار در یک خط',input(node.value.join('\n'),v=>node.value=lines(v),true)));
 if(parent)row.append(button('حذف شرط',()=>remove(parent,index)));return row;
}
function number(v){v=v.replace(/[۰-۹]/g,c=>String('۰۱۲۳۴۵۶۷۸۹'.indexOf(c))).replace(/[٠-٩]/g,c=>String('٠١٢٣٤٥٦٧٨٩'.indexOf(c)));return /^-?\d+$/.test(v.trim())?Number(v):null;}
function jalali(v){if(!/^\d{4}-\d{2}-\d{2}$/.test(v))return v;return new Intl.DateTimeFormat('fa-IR-u-nu-latn',{year:'numeric',month:'2-digit',day:'2-digit',timeZone:'UTC'}).format(new Date(v+'T12:00:00Z'));}
function mode(){const composite=metric.value==='expression';section.hidden=!composite;for(const id of ['id_operator','id_target_value']){const n=document.getElementById(id);n.closest('.field').hidden=composite;n.required=!composite;}if(composite)document.getElementById('id_operator').value='eq';}
hidden.form.addEventListener('submit',event=>{hidden.form.querySelector('[data-save-status]').textContent=event.submitter?.value==='preview'?'در حال بررسی داده‌ها؛ لطفاً منتظر بمانید…':'در حال ذخیره معیار…';});
metric.addEventListener('change',mode);hidden.form.addEventListener('submit',sync);render();mode();
})();
