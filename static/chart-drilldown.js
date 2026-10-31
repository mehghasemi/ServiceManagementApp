/* Graphic marks and their textual labels share one scoped navigation target. */
(()=>{
 const NS='http://www.w3.org/2000/svg';
 function link(mark,url,label){
  if(!url||!mark||mark.closest('a'))return;
  const a=document.createElementNS(NS,'a');a.setAttribute('href',url);a.setAttribute('aria-label','نمایش رکوردها: '+label);a.setAttribute('tabindex','0');
  mark.closest('svg')?.removeAttribute('aria-hidden');mark.replaceWith(a);a.append(mark);
 }
 function wire(root){
  root.querySelectorAll('.visual-panel,.status-composition').forEach(panel=>{
   const labels=Array.from(panel.querySelectorAll('.visual-legend>div,.status-legend>a,.custom-chart-render .horizontal-chart>div'));
   const marks=panel.querySelectorAll('.visual-ring svg .visual-stroke,.visual-ring svg .visual-fill,.status-segment,.editable-round-chart .visual-stroke,.editable-round-chart .visual-fill');
   marks.forEach((mark,i)=>{const row=labels[i],a=row?.matches('a')?row:row?.querySelector('a');link(mark,a?.getAttribute('href'),a?.textContent||'');});
  });
  root.querySelectorAll('.horizontal-chart>div,.visual-column,.bar-row').forEach(row=>{
   const a=row.querySelector('a');row.querySelectorAll('svg rect:not(.bar-track)').forEach(mark=>link(mark,a?.getAttribute('href'),a?.textContent||''));
  });
  if(location.hash){const target=document.getElementById(location.hash.slice(1))||(location.hash==='#chart-records'?document.getElementById('case-list'):null);if(target){const details=target.closest('details');if(details)details.open=true;target.scrollIntoView({block:'start'});}}
 }
 window.wireChartLinks=wire;
 document.addEventListener('DOMContentLoaded',()=>wire(document));
})();
