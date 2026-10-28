/* Safe client presentation of already-visible, scoped distribution values. */
(()=>{
 const cache=new WeakMap(),NS='http://www.w3.org/2000/svg';
 const el=(tag,text,cls)=>{const e=document.createElement(tag);if(text!==undefined)e.textContent=text;if(cls)e.className=cls;return e;};
 const svg=(tag,attrs)=>{const e=document.createElementNS(NS,tag);Object.entries(attrs).forEach(([k,v])=>e.setAttribute(k,v));return e;};
 window.renderDashboardChart=(tile,kind)=>{
  let data=cache.get(tile);const panel=tile.querySelector('.visual-panel');if(!panel)return;
  if(!data){const items=panel.querySelectorAll('.visual-legend>div,.visual-column');if(!items.length)return;data={rows:Array.from(items).map(e=>({label:e.querySelector('a,span')?.textContent||'',url:e.querySelector('a')?.getAttribute('href'),count:Number(e.querySelector('b')?.textContent)||0})),kind:null};cache.set(tile,data);}
  if(data.kind===kind)return;data.kind=kind;
  panel.querySelectorAll('.visual-ring-layout,.visual-columns,.horizontal-chart,.custom-chart-render').forEach(e=>e.remove());
  const wrap=el('div',undefined,'custom-chart-render'),total=data.rows.reduce((a,b)=>a+b.count,0),peak=Math.max(1,...data.rows.map(r=>r.count));
  if(['pie','ring'].includes(kind)){
   const chart=svg('svg',{viewBox:'0 0 120 120',class:'editable-round-chart','aria-hidden':'true'});let offset=0;
   data.rows.forEach((r,i)=>{const share=total?r.count/total:0,attrs={class:'visual-fill tone-'+i%6};if(kind==='ring')chart.append(svg('circle',{cx:60,cy:60,r:46,fill:'none','stroke-width':13,pathLength:100,'stroke-dasharray':(share*100)+' 100','stroke-dashoffset':-offset*100,transform:'rotate(-90 60 60)',class:'visual-stroke tone-'+i%6}));else if(share===1)chart.append(svg('circle',{...attrs,cx:60,cy:60,r:46}));else if(share){const a=offset*Math.PI*2-Math.PI/2,b=(offset+share)*Math.PI*2-Math.PI/2;chart.append(svg('path',{...attrs,d:`M60 60 L${60+46*Math.cos(a)} ${60+46*Math.sin(a)} A46 46 0 ${share>.5?1:0} 1 ${60+46*Math.cos(b)} ${60+46*Math.sin(b)} Z`}));}offset+=share;});wrap.append(chart);
  }
  const list=el('div',undefined,kind==='columns'?'visual-columns':'horizontal-chart');
  data.rows.forEach((r,i)=>{const item=el('div',undefined,(kind==='columns'?'visual-column ':'')+'tone-'+i%6);const label=el(r.url?'a':'span',r.label);if(r.url)label.setAttribute('href',r.url);item.append(label,el('b',r.count));if(kind==='columns'||kind==='bars'){const chart=svg('svg',{viewBox:kind==='columns'?'0 0 70 150':'0 0 100 8','aria-hidden':'true',class:kind==='columns'?'visual-column-track':'bar-track'});chart.append(svg('rect',{class:'visual-fill',x:kind==='columns'?15:0,y:kind==='columns'?150-r.count/peak*150:0,width:kind==='columns'?40:r.count/peak*100,height:kind==='columns'?r.count/peak*150:8}));item.append(chart);}list.append(item);});wrap.append(list);panel.append(wrap);
 };
})();
