"""Self-contained HTML/JS viewer: single epoch, side-by-side, blink, swipe and difference modes,
with zoom/pan and click-for-details candidate markers."""
import json

_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Inter:wght@400;600;700&display=swap');
:root{--line:#29445e;--ink:#e6f1fc;--muted:#8fb0cf;--acc:#70c8ff}
*{box-sizing:border-box}
html,body{margin:0;background:transparent;color:var(--ink);font-family:Inter,'Segoe UI',sans-serif}
#banner{padding:8px 14px;border-radius:10px;font:600 12px 'DM Mono',monospace;letter-spacing:.06em;margin-bottom:10px;border:1px solid}
#banner.sim{background:#2c2108;border-color:#8a6a1c;color:#ffcc66}
#banner.real{background:#0b2a1c;border-color:#1f7a4d;color:#5be3a0}
.bar{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-bottom:10px}
.seg{display:flex;border:1px solid var(--line);border-radius:9px;overflow:hidden}
.seg button{background:#0d1c30;color:#a8c5df;border:0;border-right:1px solid var(--line);padding:7px 14px;font:500 12px 'DM Mono',monospace;cursor:pointer}
.seg button:last-child{border-right:0}
.seg button:hover{background:#14304f}
.seg button.on{background:#17406b;color:#fff}
label{font:12px 'DM Mono',monospace;color:var(--muted);display:inline-flex;align-items:center;gap:6px}
select{background:#0d1c30;border:1px solid var(--line);color:var(--ink);border-radius:7px;padding:4px 6px;font:12px 'DM Mono',monospace}
.rst{background:#0d1c30;color:#a8c5df;border:1px solid var(--line);border-radius:7px;padding:5px 10px;font:12px 'DM Mono',monospace;cursor:pointer}
#ro{margin-left:auto;font:12px 'DM Mono',monospace;color:var(--muted)}
#stage{display:grid;gap:12px}
#stage.two{grid-template-columns:1fr 1fr}
#stage.one{max-width:560px;margin:0 auto}
.pane{position:relative;aspect-ratio:1/1;background:#000;border:1px solid var(--line);border-radius:10px;overflow:hidden;cursor:crosshair}
.inner{position:absolute;inset:0;transform-origin:0 0;--s:1}
.inner img{position:absolute;inset:0;width:100%;height:100%;user-select:none;-webkit-user-drag:none}
.inner svg{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}
.pane.drag{cursor:grabbing}
.tag{position:absolute;left:8px;top:8px;font:500 11px 'DM Mono',monospace;background:rgba(5,9,18,.82);padding:3px 8px;border-radius:6px;border:1px solid var(--line)}
.handle{position:absolute;top:0;bottom:0;width:calc(2px / var(--s));background:#fff;box-shadow:0 0 6px #000;pointer-events:none}
#swipeCtl{max-width:560px;margin:10px auto 0}
#swipeCtl input{width:100%;accent-color:#70c8ff}
#info{display:none;margin:0 0 10px;padding:10px 14px;border:1px solid #365b82;border-radius:10px;background:#0d2238;font:12px/1.55 'DM Mono',monospace;color:#cfe3f7;position:relative}
#info b{color:#70c8ff}#info .x{position:absolute;right:10px;top:6px;cursor:pointer;color:#8fb0cf}
#info .warn{color:#ffcc66}
#legend{margin-top:10px;font:11px 'DM Mono',monospace;color:var(--muted);display:flex;flex-wrap:wrap;gap:6px 16px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px;border:2px solid}
</style></head><body>
<div id="banner"></div>
<div class="bar">
  <div class="seg" id="modes"></div>
  <span id="hzWrap" style="display:none"><label>Blink rate
    <select id="hz"><option value="0.5">0.5 Hz</option><option value="1" selected>1 Hz</option><option value="2">2 Hz</option><option value="4">4 Hz</option></select></label></span>
  <label><input type="checkbox" id="mk" checked> Candidate markers</label>
  <button class="rst" id="rst" title="Reset zoom and pan">Reset zoom</button>
  <span id="ro">Hover for coordinates · wheel to zoom · drag to pan</span>
</div>
<div id="info"></div>
<div id="stage"></div>
<div id="swipeCtl" style="display:none"><input type="range" id="sw" min="0" max="100" value="50"></div>
<div id="legend"></div>
<script>
const D=__DATA__;
const COL={moving:'#ffd166',brightening:'#ff7b7b',dimming:'#6bc5ff'};
const NAME={moving:'Moving source',brightening:'Brightening',dimming:'Dimming'};
const $=id=>document.getElementById(id);
const MODES={b:'Epoch B',a:'Epoch A',side:'Side by side',blink:'Blink',swipe:'Swipe',diff:'Difference'};
let mode=D.modes[0],timer=null,V={s:1,tx:0,ty:0};
function applyView(){MK.forEach((m,svg)=>{if(svg.isConnected)drawMk(svg);});document.querySelectorAll('.inner').forEach(e=>{e.style.transform='translate('+V.tx+'px,'+V.ty+'px) scale('+V.s+')';e.style.setProperty('--s',V.s);});}
function clampView(w,h){V.s=Math.min(10,Math.max(1,V.s));V.tx=Math.min(0,Math.max(w*(1-V.s),V.tx));V.ty=Math.min(0,Math.max(h*(1-V.s),V.ty));}
$('rst').onclick=()=>{V={s:1,tx:0,ty:0};applyView();};

$('banner').className=D.prov;
$('banner').textContent=D.prov==='sim'
  ?'SIMULATED DEMONSTRATION - these images are generated, not SPHEREx observations.'
  :'REAL SPHEREx OBSERVATIONS - as supplied in your files. Candidates are automatic, unverified detections.';

D.modes.forEach(k=>{const t=MODES[k];
  const b=document.createElement('button');b.textContent=t;b.dataset.k=k;
  b.onclick=()=>{mode=k;render();};$('modes').appendChild(b);
});
$('mk').onchange=render;$('hz').onchange=render;
$('legend').innerHTML=Object.keys(COL).map(k=>'<span><i class="dot" style="border-color:'+COL[k]+'"></i>'+NAME[k]+'</span>').join('')
  +'<span>Candidates are automatic detections in these two images - not confirmed discoveries.</span>';

function hover(e,p){
  const r=p.querySelector('.inner').getBoundingClientRect(),x=(e.clientX-r.left)/r.width*D.n,y=(e.clientY-r.top)/r.height*D.n;
  let t='x '+x.toFixed(1)+'  y '+y.toFixed(1)+' px';
  if(D.wcs){const c=(D.n-1)/2,dec=D.dec0-(y-c)*D.pix/3600,ra=D.ra0-(x-c)*D.pix/3600/Math.cos(D.dec0*Math.PI/180);
    t+='  |  RA '+ra.toFixed(4)+'°  Dec '+dec.toFixed(4)+'°';}
  if(V.s>1.01)t+='  |  zoom '+V.s.toFixed(1)+'\u00d7';
  $('ro').textContent=t;
}
function pane(src,tag){
  const p=document.createElement('div');p.className='pane';
  p.innerHTML='<div class="inner"><img src="'+src+'" draggable="false"><svg viewBox="0 0 '+D.n+' '+D.n+'" preserveAspectRatio="none"></svg></div><div class="tag">'+tag+'</div>';
  p.addEventListener('mousemove',e=>hover(e,p));
  p.addEventListener('wheel',e=>{e.preventDefault();const r=p.getBoundingClientRect(),px=e.clientX-r.left,py=e.clientY-r.top,k=Math.exp(-e.deltaY*0.0015),ns=Math.min(10,Math.max(1,V.s*k)),f=ns/V.s;
    V.tx=px-(px-V.tx)*f;V.ty=py-(py-V.ty)*f;V.s=ns;clampView(r.width,r.height);applyView();},{passive:false});
  let drag=null;
  p.addEventListener('mousedown',e=>{drag={x:e.clientX,y:e.clientY,tx:V.tx,ty:V.ty};p.classList.add('drag');});
  window.addEventListener('mouseup',()=>{drag=null;p.classList.remove('drag');});
  window.addEventListener('mousemove',e=>{if(!drag)return;const r=p.getBoundingClientRect();V.tx=drag.tx+e.clientX-drag.x;V.ty=drag.ty+e.clientY-drag.y;clampView(r.width,r.height);applyView();});
  return p;
}
function showInfo(id){
  const c=D.cands.find(x=>x.id===id);if(!c)return;
  let h='<span class="x" onclick="this.parentNode.style.display=\'none\'">\u2715</span><b>'+c.id+' \u00b7 '+NAME[c.kind]+'</b><br>';
  h+='Significance: '+c.snr+' \u03c3 \u00b7 expected false alarms: '+c.fa+' per image<br>';
  h+='Reliability: <b>'+c.reliability+'</b>'+(c.kind==='moving'?' (symmetry '+c.symmetry+')':'')+'<br>';
  if(c.kind==='moving')h+='Moved '+c.shift_arcsec+' arcsec ('+c.shift_px+' px) from A to B<br>';
  else h+=(c.kind==='brightening'?'Brighter':'Fainter')+' in B than in A<br>';
  if(c.frac!==undefined)h+='Change relative to source brightness: '+(c.frac>=99?'>99':Math.round(c.frac*100))+'%<br>';
  if(c.note)h+='<span class="warn">'+c.note+'</span><br>';
  h+='Status: unverified candidate - check SIMBAD, Gaia and WISE before drawing conclusions.';
  const el=$('info');el.innerHTML=h;el.style.display='block';
}
const MK=new Map();
function markers(svg,fr,trail){
  MK.set(svg,{fr:fr,trail:trail});drawMk(svg);
}
function drawMk(svg){
  const m=MK.get(svg),fr=m.fr,trail=m.trail,k=1/V.s;
  if(!$('mk').checked){svg.innerHTML='';return;}
  let s='';
  D.cands.forEach(c=>{
    const col=COL[c.kind];let x=c.x,y=c.y;
    if(c.kind==='moving'){
      if(fr==='A'){x=c.xa;y=c.ya;}else{x=c.xb;y=c.yb;}
      if(trail)s+='<line x1="'+c.xa+'" y1="'+c.ya+'" x2="'+c.xb+'" y2="'+c.yb+'" stroke="'+col+'" stroke-width="'+(1.2*k)+'" stroke-dasharray="'+(3*k)+' '+(2*k)+'" vector-effect="non-scaling-stroke"/>';
    }
    s+='<circle cx="'+x+'" cy="'+y+'" r="'+Math.max(4,D.n/32)*k+'" fill="none" stroke="'+col+'" stroke-width="'+(1.6*k)+'" vector-effect="non-scaling-stroke"/>';
    s+='<circle cx="'+x+'" cy="'+y+'" r="'+Math.max(7,D.n/18)*k+'" fill="transparent" style="pointer-events:all;cursor:pointer" onclick="showInfo(\''+c.id+'\')"><title>'+c.id+': click for details</title></circle>';
    s+='<text x="'+(x+D.n/28*k)+'" y="'+(y-D.n/28*k)+'" fill="'+col+'" font-size="'+(D.n/22*k)+'" font-family="DM Mono,monospace">'+c.id+'</text>';
  });
  svg.innerHTML=s;
}
function render(){
  if(timer){clearInterval(timer);timer=null;}
  MK.clear();
  const st=$('stage');st.innerHTML='';st.className=(mode==='side')?'two':'one';
  $('swipeCtl').style.display=(mode==='swipe')?'block':'none';
  $('hzWrap').style.display=(mode==='blink')?'inline':'none';
  document.querySelectorAll('#modes button').forEach(b=>b.classList.toggle('on',b.dataset.k===mode));
  const A='A · '+D.labelA,B='B · '+D.labelB;
  if(mode==='a'||mode==='b'){
    const p=pane(mode==='a'?D.a:D.b,mode==='a'?A:B);st.append(p);markers(p.querySelector('svg'),mode==='a'?'A':'B',false);
  }else if(mode==='side'){
    const a=pane(D.a,A),b=pane(D.b,B);st.append(a,b);
    markers(a.querySelector('svg'),'A',false);markers(b.querySelector('svg'),'B',true);
  }else if(mode==='diff'){
    const p=pane(D.d,'B − A  (red = brighter in B, blue = fainter)');st.append(p);markers(p.querySelector('svg'),'B',true);
  }else if(mode==='blink'){
    const p=pane(D.a,A);st.append(p);
    const ib=document.createElement('img');ib.src=D.b;ib.style.visibility='hidden';const inn=p.querySelector('.inner');inn.insertBefore(ib,inn.querySelector('svg'));
    const tag=p.querySelector('.tag'),svg=p.querySelector('svg');let f=0;markers(svg,'A',false);
    timer=setInterval(()=>{f^=1;ib.style.visibility=f?'visible':'hidden';tag.textContent=f?B:A;markers(svg,f?'B':'A',false);},1000/parseFloat($('hz').value));
  }else{
    const p=pane(D.a,'A | B');st.append(p);
    const ib=document.createElement('img');ib.src=D.b;const inn=p.querySelector('.inner');inn.insertBefore(ib,inn.querySelector('svg'));
    const h=document.createElement('div');h.className='handle';inn.appendChild(h);
    const set=v=>{ib.style.clipPath='inset(0 0 0 '+v+'%)';h.style.left=v+'%';};
    $('sw').oninput=e=>set(e.target.value);set($('sw').value);markers(p.querySelector('svg'),'B',true);
  }
  applyView();
}
render();
</script></body></html>"""


def viewer_html(pair, label_a, label_b, provenance="sim", ra0=None, dec0=None, pix=6.2,
                modes=("side", "blink", "swipe", "diff")):
    """modes: any of 'b', 'a' (single epoch), 'side', 'blink', 'swipe', 'diff'; first one is shown first."""
    data = dict(modes=list(modes), a=pair["a"], b=pair["b"], d=pair["d"], cands=pair["cands"], n=pair["n"],
                labelA=label_a, labelB=label_b, prov=provenance,
                wcs=ra0 is not None, ra0=ra0 or 0, dec0=dec0 or 0, pix=pix)
    return _TEMPLATE.replace("__DATA__", json.dumps(data))
