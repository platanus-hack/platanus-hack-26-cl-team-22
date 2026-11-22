// Simulador de comunas: globo d3 en canvas, del mundo a las calles de Santiago.
// Portado desde "Simulador de comunas.html" con cambios mínimos:
//  - datos y librerías como módulos en vez de <script> globales,
//  - el nivel de zoom se guarda en el contenedor (root.dataset.level), no en <body>,
//  - setIntro(): la landing controla el centro, el radio y la paleta del globo
//    mientras el usuario hace scroll desde el logo,
//  - carga en dos partes: lo que necesita el globo del logo (mundo 1:110m y
//    comunas) viene en este módulo; el mapa 1:50m, las calles de OSM y los
//    lugares (~2,3 MB, ver data/detail.js) llegan después, en segundo plano.
import * as d3 from "d3";
import * as topojson from "topojson-client";
import W110 from "./data/w110.json";
import RM from "./data/rm.json";
import { COMUNAS, PPDA_CRED, SEIA_PROB } from "./model.js";

// Communes the real simulator (viz/) ranks. The globe label shows this, not the 12 of the sample
// model below, so the landing and the simulator never disagree on the count.
const COMUNAS_SIMULADOR = 52;

const mounted = new WeakMap();

export function mountSimulator(root, opts={}){
if(mounted.has(root)) return mounted.get(root);
let intro=null;
// startHidden: no dibujar nada hasta el primer setIntro(). Sin esto, al cargar
// se alcanza a pintar un cuadro con el globo grande de la vista "Mundo".
let hidden=!!opts.startHidden;
const TINT_KEYS=["ocean","land","border","grat","accent"];
function tinted(mix){
  const out={...C};
  for(const key of TINT_KEYS) if(intro.tint[key]) out[key]=d3.interpolateRgb(intro.tint[key],C[key])(mix);
  return out;
}
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
const nf0 = new Intl.NumberFormat("es-CL",{maximumFractionDigits:0});
const nf1 = new Intl.NumberFormat("es-CL",{minimumFractionDigits:1, maximumFractionDigits:1});
const YEAR0 = 2026;
const SANTIAGO = [-70.66, -33.47];

/* ---------- datos de ejemplo (COMUNAS y credibilidades en model.js) ---------- */
const VARS = {
  pm:  {label:"PM2,5", unit:"µg/m³", fmt:v=>nf1.format(v), dim:"aire"},
  del: {label:"Delitos", unit:"casos por 100 mil hab.", fmt:v=>nf0.format(Math.round(v/10)*10), dim:"seguridad"},
  pob: {label:"Población", unit:"mil hab.", fmt:v=>nf0.format(v), dim:"crecimiento"}
};

/* Monte Carlo: corre en simulation.worker.js; null hasta que responde */
let SIM=null, VALID=null;

/* ---------- estado ---------- */
const PROFILES = [
  {id:"eq",  label:"Equilibrado", w:[50,50,50]},
  {id:"air", label:"Sensible a la contaminación", w:[90,35,15]},
  {id:"seg", label:"Prioriza seguridad", w:[35,90,15]},
  {id:"gro", label:"Busca un barrio que crece", w:[35,35,90]}
];
const S = {h:10, shock:false, w:[50,50,50], profile:"eq", sel:null, hover:null, v:"pm"};
let scores=[], order=[], baseline=null, moves={};

function sim(i){return SIM[i][S.shock?"on":"off"]}
function dimVals(){
  return COMUNAS.map((c,i)=>{const q=sim(i).q; return {pm:q.pm[S.h].mid, del:q.del[S.h].mid, pob:(q.pob[S.h].mid/q.pob[0].mid-1)*100}});
}
function compute(){
  const d=dimVals(), ext=k=>d3.extent(d,x=>x[k]);
  const [a0,a1]=ext("pm"),[s0,s1]=ext("del"),[p0,p1]=ext("pob");
  const tot=(S.w[0]+S.w[1]+S.w[2])||1, w=tot===1&&!S.w.some(Boolean)?[1/3,1/3,1/3]:S.w.map(x=>x/tot);
  scores=d.map((x,i)=>{
    const parts=[100*(a1-x.pm)/(a1-a0), 100*(s1-x.del)/(s1-s0), 100*(x.pob-p0)/(p1-p0)];
    return {i, parts, raw:x, total:parts[0]*w[0]+parts[1]*w[1]+parts[2]*w[2]};
  });
  order=scores.slice().sort((a,b)=>b.total-a.total).map(s=>s.i);
}
function rankOf(i){return order.indexOf(i)+1}
function snapshot(){return {rank:Object.fromEntries(order.map((i,p)=>[i,p+1])), w:S.w.slice(), h:S.h, shock:S.shock}}

/* ---------- geografía ---------- */
function prep(topo){return {land:topojson.merge(topo,topo.objects.countries.geometries), borders:topojson.mesh(topo,topo.objects.countries,(a,b)=>a!==b), chile:topojson.feature(topo,topo.objects.countries).features.find(f=>f.properties.name==="Chile")}}
const G110=prep(W110);
/* detalle (data/detail.js): null hasta que termina de cargar */
let G50=null, OSM=null, POI=null, ST=null, WATER=null, METRO=null;
const RMF=topojson.feature(RM,RM.objects.rm).features;
RMF.forEach(f=>{ if(d3.geoArea(f)>6){ const rev=p=>p.forEach(r=>r.reverse()); f.geometry.type==="Polygon"?rev(f.geometry.coordinates):f.geometry.coordinates.forEach(rev);} f.idx=COMUNAS.findIndex(c=>c.name===f.properties.Comuna); f.c=d3.geoCentroid(f); });
const MODELED=RMF.filter(f=>f.idx>=0);
const RM_MESH=topojson.mesh(RM,RM.objects.rm);
const graticule=d3.geoGraticule10();
const span=obj=>{const b=d3.geoBounds(obj); return Math.max((b[1][0]-b[0][0])*Math.cos(b[0][1]*Math.PI/180),(b[1][1]-b[0][1]))*Math.PI/180};
const REGION_FC={type:"FeatureCollection",features:MODELED}, REGION_C=d3.geoCentroid(REGION_FC), REGION_SPAN=span(REGION_FC);

/* ---------- mapa ---------- */
const stage=document.getElementById("stage"), canvas=document.getElementById("map"), ctx=canvas.getContext("2d");
const projection=d3.geoOrthographic().clipAngle(90).precision(.4), path=d3.geoPath(projection,ctx);
let Wd=0,Hd=0,R0=100, view={lon:-58,lat:-22,k:1}, C={}, ramp=()=>"#888", anim=null, drawQueued=false, t0=performance.now();
const smooth=(a,b,x)=>{const t=Math.max(0,Math.min(1,(x-a)/(b-a)));return t*t*(3-2*t)};
const wide=()=>innerWidth>860;
function panelW(){return wide()?432:0}
function centerX(k){const world=wide()?Wd*.62:Wd*.5, region=(Wd-panelW())/2; return world+(region-world)*smooth(Math.log(1.4),Math.log(20),Math.log(k))}
function centerY(k){const world=wide()?Hd*.5:Hd*.27; return world+(Hd*.5-world)*smooth(Math.log(1.4),Math.log(20),Math.log(k))}
function fitK(spanRad,frac){return Math.min(Wd-panelW(),Hd)*frac/(R0*spanRad)}
const regionK=()=>fitK(REGION_SPAN,.86);
function applyProj(){
  if(intro) projection.scale(intro.r).translate([intro.x,intro.y]).rotate([-view.lon,-view.lat]);
  else projection.scale(R0*view.k).translate([centerX(view.k),centerY(view.k)]).rotate([-view.lon,-view.lat]);
}
function readTheme(){
  const cs=getComputedStyle(document.documentElement), g=n=>cs.getPropertyValue(n).trim();
  C={page:g("--page"),ocean:g("--ocean"),land:g("--land"),border:g("--border"),grat:g("--grat"),ink:g("--ink"),muted:g("--muted"),accent:g("--accent"),ctx:g("--ctx"),panel:g("--panel"),font:g("--body"),road:g("--road"),roadEdge:g("--road-edge")};
  ramp=d3.interpolateRgbBasis([g("--worse"),g("--mid"),g("--better")]);
}
function resize(){
  const r=stage.getBoundingClientRect(), dpr=Math.min(devicePixelRatio||1,2);
  Wd=r.width; Hd=r.height; canvas.width=Wd*dpr; canvas.height=Hd*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
  R0=Math.min(Wd,Hd)*(wide()?.4:.36); draw();
}
function level(){const k=view.k; return k<2.2?"world":k<regionK()*.45?"country":"region"}
function requestDraw(){ if(!drawQueued){drawQueued=true; requestAnimationFrame(()=>{drawQueued=false; draw();});} }

function draw(){
  if(!Wd) return;
  if(hidden){ ctx.clearRect(0,0,Wd,Hd); return; }
  const C0=C; if(intro&&intro.mix<1) C=tinted(intro.mix);
  try{ drawFrame(); } finally { C=C0; }
}
function drawFrame(){
  applyProj();
  const k=view.k, G=k<3||!G50?G110:G50, lv=level();
  if(root.dataset.level!==lv) root.dataset.level=lv;
  ctx.clearRect(0,0,Wd,Hd);
  ctx.beginPath(); path({type:"Sphere"}); ctx.fillStyle=C.ocean; ctx.fill();
  const ga=1-smooth(4,14,k);
  if(ga>0){ctx.globalAlpha=ga; ctx.beginPath(); path(graticule); ctx.strokeStyle=C.grat; ctx.lineWidth=.7; ctx.stroke(); ctx.globalAlpha=1;}
  ctx.beginPath(); path(G.land); ctx.fillStyle=C.land; ctx.fill(); ctx.strokeStyle=C.border; ctx.lineWidth=.8; ctx.stroke();
  ctx.beginPath(); path(G.borders); ctx.lineWidth=.6; ctx.stroke();
  const ca=1-smooth(regionK()*.2,regionK()*.5,k);
  if(ca>0&&G.chile){ctx.globalAlpha=ca; ctx.beginPath(); path(G.chile); ctx.strokeStyle=C.accent; ctx.lineWidth=1.6; ctx.stroke(); ctx.globalAlpha=1;}
  ctx.beginPath(); path({type:"Sphere"}); ctx.strokeStyle=C.border; ctx.lineWidth=1; ctx.stroke();

  const ra=smooth(regionK()*.12,regionK()*.4,k), ppm=R0*k/6371000;
  if(ra>0){
    const placed=[];
    ctx.globalAlpha=ra*(1-.55*smooth(.05,.3,ppm));
    for(const f of RMF){ctx.beginPath(); path(f); ctx.fillStyle=f.idx>=0&&scores.length?ramp(scores[f.idx].total/100):C.ctx; ctx.fill();}
    ctx.globalAlpha=ra*smooth(.006,.012,ppm);
    if(OSM){
    ctx.beginPath(); path(WATER); ctx.strokeStyle=C.ocean; ctx.lineWidth=Math.max(2,30*ppm); ctx.lineCap="round"; ctx.lineJoin="round"; ctx.stroke();
    localFrame(); drawStreets(ppm,ra);
    }
    ctx.globalAlpha=ra; ctx.lineCap="butt";
    ctx.beginPath(); path(RM_MESH);
    if(ppm>.06){ctx.setLineDash([7,5]); ctx.strokeStyle=C.muted; ctx.lineWidth=1.4;} else {ctx.strokeStyle=C.page; ctx.lineWidth=1.2;}
    ctx.stroke(); ctx.setLineDash([]);
    if(OSM) drawPlaces(ppm,ra,placed);
    const hi=(i,w)=>{const f=MODELED.find(f=>f.idx===i); if(!f)return; ctx.beginPath(); path(f); ctx.strokeStyle=C.ink; ctx.lineWidth=w; ctx.lineJoin="round"; ctx.stroke();};
    if(S.hover!=null&&S.hover!==S.sel) hi(S.hover,1.5);
    if(S.sel!=null) hi(S.sel,2.6);
    if(k>regionK()*.55){
      ctx.font="700 13px "+C.font; ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.lineJoin="round";
      const pri=f=>f.idx===S.sel?-2:f.idx===S.hover?-1:rankOf(f.idx);
      for(const f of MODELED.slice().sort((a,b)=>pri(a)-pri(b))){
        const p=projection(f.c), name=COMUNAS[f.idx].name, tw=ctx.measureText(name).width;
        if(!p) continue;
        const box=[p[0]-tw/2-4,p[1]-9,p[0]+tw/2+4,p[1]+9];
        if(placed.some(q=>box[0]<q[2]&&box[2]>q[0]&&box[1]<q[3]&&box[3]>q[1])) continue;
        placed.push(box);
        ctx.strokeStyle=C.land; ctx.lineWidth=3.5; ctx.globalAlpha=ra*.85; ctx.strokeText(name,p[0],p[1]);
        ctx.globalAlpha=ra; ctx.fillStyle=C.ink; ctx.fillText(name,p[0],p[1]);
      }
    }
    if(OSM) drawStreetNames(ppm,ra,placed);
    ctx.globalAlpha=1;
  }

  const ma=(1-smooth(regionK()*.1,regionK()*.3,k))*(intro?intro.ui:1);
  if(ma>0&&d3.geoDistance(SANTIAGO,[view.lon,view.lat])<1.45){
    const p=projection(SANTIAGO), t=reduced?0:((performance.now()-t0)%2200)/2200;
    ctx.globalAlpha=ma*(1-t)*.7; ctx.beginPath(); ctx.arc(p[0],p[1],6+t*20,0,7); ctx.strokeStyle=C.accent; ctx.lineWidth=1.5; ctx.stroke();
    ctx.globalAlpha=ma; ctx.beginPath(); ctx.arc(p[0],p[1],5.5,0,7); ctx.fillStyle=C.accent; ctx.fill(); ctx.strokeStyle=C.land; ctx.lineWidth=2; ctx.stroke();
    const lx=p[0]+34, ly=p[1]-30;
    ctx.beginPath(); ctx.moveTo(p[0]+5,p[1]-5); ctx.lineTo(lx-6,ly+4); ctx.strokeStyle=C.ink; ctx.lineWidth=1; ctx.stroke();
    ctx.textAlign="left"; ctx.textBaseline="alphabetic"; ctx.font="600 13.5px "+C.font; ctx.fillStyle=C.ink; ctx.fillText("Santiago de Chile",lx,ly);
    ctx.font="12.5px "+C.font; ctx.fillStyle=C.muted; ctx.fillText(COMUNAS_SIMULADOR+" comunas simuladas",lx,ly+16);
    ctx.globalAlpha=1;
  }
  if(!reduced&&ma>0&&!anim) requestDraw();
}

function flyTo(lon,lat,k,ms,done){
  if(anim) cancelAnimationFrame(anim.raf);
  const from={...view}; let dl=lon-from.lon; dl=((dl+540)%360)-180;
  const lk0=Math.log(from.k), lk1=Math.log(k), start=performance.now(), dur=reduced?0:ms;
  anim={raf:0};
  (function step(now){
    const t=dur?Math.min(1,(now-start)/dur):1, e=d3.easeCubicInOut(t), em=d3.easeCubicOut(t);
    const zoomingIn=lk1>lk0;
    view.lon=from.lon+dl*(zoomingIn?em:e); view.lat=from.lat+(lat-from.lat)*(zoomingIn?em:e); view.k=Math.exp(lk0+(lk1-lk0)*(zoomingIn?d3.easeCubicIn(t)*.35+e*.65:e));
    draw();
    if(t<1) anim.raf=requestAnimationFrame(step); else {anim=null; requestDraw(); if(done) done();}
  })(start);
}
function go(where){
  if(where==="world"){ select(null,false); flyTo(-58,-22,1,1500); }
  else if(where==="country"){ select(null,false); flyTo(-70,-37,3.4,1500); }
  else if(where==="region"){ select(null,false); flyTo(REGION_C[0],REGION_C[1],regionK(),view.k<3?2600:1100); }
}
function flyComuna(i){const f=MODELED.find(f=>f.idx===i); flyTo(f.c[0],f.c[1],Math.min(fitK(span(f),.5),regionK()*3.2),900)}

/* ---------- capa de calles (extracto de OpenStreetMap guardado en la página) ---------- */
function decodeStreets(){
  const bin=atob(OSM.b64), n=bin.length, u=new Uint8Array(n); for(let i=0;i<n;i++) u[i]=bin.charCodeAt(i);
  let p=0; const vi=()=>{let r=0,s=0,b; do{b=u[p++]; r|=(b&127)<<s; s+=7;}while(b&128); return r>>>0}, zz=v=>(v>>>1)^-(v&1);
  const L=[];
  for(let l=0;l<4;l++){
    const np=vi(), nt=vi(), start=new Uint32Array(np+1), name=new Int32Array(np), bb=new Int16Array(np*4), pts=new Int16Array(nt*2); let o=0;
    for(let i=0;i<np;i++){
      const c=vi(); name[i]=vi()-1; start[i]=o; let x=0,y=0,x0=32767,y0=32767,x1=-32768,y1=-32768;
      for(let j=0;j<c;j++){x+=zz(vi()); y+=zz(vi()); pts[2*o]=x; pts[2*o+1]=y; o++; if(x<x0)x0=x; if(x>x1)x1=x; if(y<y0)y0=y; if(y>y1)y1=y;}
      bb[4*i]=x0; bb[4*i+1]=y0; bb[4*i+2]=x1; bb[4*i+3]=y1;
    }
    start[np]=o; L.push({n:np,start,name,bb,pts});
  }
  return L;
}
import("./data/detail.js").then(d=>{
  G50=prep(d.W50); OSM=d.OSM; POI=d.POI; ST=decodeStreets();
  WATER={type:"MultiLineString",coordinates:POI.water};
  METRO=POI.metro.map(l=>({c:l.c,g:{type:"LineString",coordinates:l.p}}));
  requestDraw();
});
const TH=[.006,.012,.03,.085], WM=[15,12,8,5.5], MINW=[1.7,1.2,.8,.55], LTH=[.05,.05,.13,.38];
const toLocal=g=>[(g[0]-OSM.lon0)*OSM.kx,(g[1]-OSM.lat0)*OSM.ky], toLL=(x,y)=>[OSM.lon0+x/OSM.kx,OSM.lat0+y/OSM.ky];
let AF=null;
function localFrame(){
  const cs=[[0,0],[Wd,0],[0,Hd],[Wd,Hd],[Wd/2,Hd/2]].map(p=>projection.invert(p));
  if(cs.some(c=>!c||!isFinite(c[0]))) return AF=null;
  const l=cs.map(toLocal), xs=l.map(p=>p[0]), ys=l.map(p=>p[1]), c=l[4], D=300;
  const p0=projection(toLL(c[0],c[1])), p1=projection(toLL(c[0]+D,c[1])), p2=projection(toLL(c[0],c[1]+D));
  const a=(p1[0]-p0[0])/D, cc=(p1[1]-p0[1])/D, b=(p2[0]-p0[0])/D, d=(p2[1]-p0[1])/D;
  return AF={a,b,c:cc,d,e:p0[0]-a*c[0]-b*c[1],f:p0[1]-cc*c[0]-d*c[1],x0:Math.min(...xs)-30,x1:Math.max(...xs)+30,y0:Math.min(...ys)-30,y1:Math.max(...ys)+30};
}
function drawStreets(ppm,ra){
  if(!AF) return;
  const {a,b,c,d,e,f,x0,x1,y0,y1}=AF;
  ctx.lineCap="round"; ctx.lineJoin="round";
  for(let l=3;l>=0;l--){
    const al=smooth(TH[l],TH[l]*1.6,ppm); if(al<=0) continue;
    const S_=ST[l], bb=S_.bb, pts=S_.pts, st=S_.start, path2=new Path2D();
    for(let i=0;i<S_.n;i++){
      if(bb[4*i]>x1||bb[4*i+2]<x0||bb[4*i+1]>y1||bb[4*i+3]<y0) continue;
      let j=st[i]; const en=st[i+1];
      path2.moveTo(a*pts[2*j]+b*pts[2*j+1]+e,c*pts[2*j]+d*pts[2*j+1]+f);
      for(j++;j<en;j++) path2.lineTo(a*pts[2*j]+b*pts[2*j+1]+e,c*pts[2*j]+d*pts[2*j+1]+f);
    }
    const w=Math.max(MINW[l],WM[l]*ppm);
    ctx.globalAlpha=ra*al;
    if(w>=2.6){ctx.strokeStyle=C.roadEdge; ctx.lineWidth=w+1.6; ctx.stroke(path2);}
    ctx.strokeStyle=C.road; ctx.lineWidth=w; ctx.stroke(path2);
  }
  ctx.globalAlpha=ra;
}
function hit(placed,box){ if(placed.some(q=>box[0]<q[2]&&box[2]>q[0]&&box[1]<q[3]&&box[3]>q[1])) return true; placed.push(box); return false; }
function drawPlaces(ppm,ra,placed){
  if(ppm>.012){
    ctx.lineCap="round"; ctx.lineJoin="round"; ctx.globalAlpha=ra*smooth(.012,.02,ppm)*.9;
    for(const l of METRO){ctx.beginPath(); path(l.g); ctx.strokeStyle=l.c; ctx.lineWidth=ppm>.1?3.5:2.2; ctx.stroke();}
    ctx.globalAlpha=ra;
  }
  if(ppm>.045){
    const r=ppm>.15?4.5:2.8; ctx.font="600 11px "+C.font; ctx.textAlign="left"; ctx.textBaseline="middle";
    for(const s of POI.st){
      const p=projection(s); if(!p||p[0]<-20||p[0]>Wd+20||p[1]<-20||p[1]>Hd+20) continue;
      ctx.beginPath(); ctx.arc(p[0],p[1],r,0,7); ctx.fillStyle=C.panel; ctx.fill(); ctx.strokeStyle=C.ink; ctx.lineWidth=1.6; ctx.stroke();
      if(ppm>.16){const t="Metro "+s[2], tw=ctx.measureText(t).width; if(hit(placed,[p[0]+6,p[1]-8,p[0]+10+tw,p[1]+8])) continue;
        ctx.strokeStyle=C.land; ctx.lineWidth=3.5; ctx.strokeText(t,p[0]+8,p[1]); ctx.fillStyle=C.ink; ctx.fillText(t,p[0]+8,p[1]);}
    }
  }
  if(ppm>.11){
    ctx.font="500 11px "+C.font; ctx.textAlign="left"; ctx.textBaseline="middle";
    for(const s of POI.lm){
      if(!s[3]&&ppm<.22) continue;
      const p=projection(s); if(!p||p[0]<0||p[0]>Wd||p[1]<0||p[1]>Hd) continue;
      const tw=ctx.measureText(s[2]).width; if(hit(placed,[p[0]-5,p[1]-8,p[0]+10+tw,p[1]+8])) continue;
      ctx.fillStyle=C.accent; ctx.beginPath();
      if(s[3]){ctx.moveTo(p[0],p[1]-5); ctx.lineTo(p[0]+5,p[1]+4); ctx.lineTo(p[0]-5,p[1]+4); ctx.closePath();} else ctx.rect(p[0]-3.5,p[1]-3.5,7,7);
      ctx.fill();
      ctx.strokeStyle=C.land; ctx.lineWidth=3.5; ctx.strokeText(s[2],p[0]+8,p[1]); ctx.fillStyle=C.accent; ctx.fillText(s[2],p[0]+8,p[1]);
    }
  }
}
function drawStreetNames(ppm,ra,placed){
  if(!AF||ppm<LTH[0]) return;
  const {a,b,c,d,e,f,x0,x1,y0,y1}=AF, best=new Map();
  for(let l=0;l<4;l++){
    if(ppm<LTH[l]) continue;
    const S_=ST[l], bb=S_.bb, pts=S_.pts, st=S_.start, nm=S_.name;
    for(let i=0;i<S_.n;i++){
      const id=nm[i]; if(id<0||bb[4*i]>x1||bb[4*i+2]<x0||bb[4*i+1]>y1||bb[4*i+3]<y0) continue;
      let len=0; const s0=st[i], en=st[i+1];
      for(let j=s0+1;j<en;j++) len+=Math.hypot(pts[2*j]-pts[2*j-2],pts[2*j+1]-pts[2*j-1]);
      const px=len*ppm, cur=best.get(id); if(px<46||(cur&&cur.px>=px)) continue;
      let acc=0, half=len/2, mx=0,my=0,ang=0;
      for(let j=s0+1;j<en;j++){
        const dx=pts[2*j]-pts[2*j-2], dy=pts[2*j+1]-pts[2*j-1], sl=Math.hypot(dx,dy);
        if(acc+sl>=half){const t=sl?(half-acc)/sl:0, X=pts[2*j-2]+dx*t, Y=pts[2*j-1]+dy*t; mx=a*X+b*Y+e; my=c*X+d*Y+f; ang=Math.atan2(c*dx+d*dy,a*dx+b*dy); break;}
        acc+=sl;
      }
      if(mx<20||mx>Wd-20||my<20||my>Hd-20) continue;
      best.set(id,{id,l,px,mx,my,ang});
    }
  }
  const list=[...best.values()].sort((p,q)=>p.l-q.l||q.px-p.px).slice(0,140);
  ctx.textAlign="center"; ctx.textBaseline="middle"; ctx.lineJoin="round"; let count=0;
  for(const s of list){
    if(count>70) break;
    ctx.font=(s.l<2?"600 11.5px ":"500 10.5px ")+C.font;
    const t=OSM.names[s.id], tw=ctx.measureText(t).width; if(s.px<tw+14) continue;
    let ang=s.ang; if(ang>Math.PI/2) ang-=Math.PI; if(ang<-Math.PI/2) ang+=Math.PI;
    const hw=(Math.abs(Math.cos(ang))*tw+Math.abs(Math.sin(ang))*13)/2+3, hh=(Math.abs(Math.sin(ang))*tw+Math.abs(Math.cos(ang))*13)/2+3;
    if(hit(placed,[s.mx-hw,s.my-hh,s.mx+hw,s.my+hh])) continue;
    ctx.save(); ctx.translate(s.mx,s.my); ctx.rotate(ang);
    ctx.strokeStyle=C.road; ctx.lineWidth=3.5; ctx.globalAlpha=ra*.9; ctx.strokeText(t,0,0);
    ctx.globalAlpha=ra; ctx.fillStyle=C.muted; if(s.l<2) ctx.fillStyle=C.ink; ctx.fillText(t,0,0); ctx.restore(); count++;
  }
}

/* interacción con el mapa */
const ptrs=new Map(); let moved=0, pinch0=null;
function zoomAt(x,y,factor){
  const kMax=regionK()*70, nk=Math.max(1,Math.min(kMax,view.k*factor)); if(nk===view.k) return;
  applyProj(); const a=projection.invert([x,y]); view.k=nk; applyProj(); const b=projection.invert([x,y]);
  if(a&&b&&isFinite(a[0])&&isFinite(b[0])){view.lon+=a[0]-b[0]; view.lat=Math.max(-85,Math.min(85,view.lat+a[1]-b[1]));}
  requestDraw();
}
function stop(){ if(anim){cancelAnimationFrame(anim.raf); anim=null;} }
function pos(e){const r=canvas.getBoundingClientRect(); return [e.clientX-r.left,e.clientY-r.top]}
canvas.addEventListener("pointerdown",e=>{stop(); canvas.setPointerCapture(e.pointerId); ptrs.set(e.pointerId,pos(e)); moved=0; pinch0=null; canvas.classList.add("dragging"); hideTip();});
canvas.addEventListener("pointermove",e=>{
  const p=pos(e);
  if(!ptrs.has(e.pointerId)){ hover(p); return; }
  const prev=ptrs.get(e.pointerId); ptrs.set(e.pointerId,p);
  if(ptrs.size===1){
    const dx=p[0]-prev[0], dy=p[1]-prev[1]; moved+=Math.abs(dx)+Math.abs(dy);
    const deg=180/Math.PI/(R0*view.k);
    view.lon-=dx*deg/Math.max(.2,Math.cos(view.lat*Math.PI/180)); view.lat=Math.max(-85,Math.min(85,view.lat+dy*deg)); requestDraw();
  } else if(ptrs.size===2){
    const [a,b]=[...ptrs.values()], d=Math.hypot(a[0]-b[0],a[1]-b[1]);
    if(pinch0) zoomAt((a[0]+b[0])/2,(a[1]+b[1])/2,d/pinch0); pinch0=d; moved=99;
  }
});
function up(e){
  const had=ptrs.has(e.pointerId); ptrs.delete(e.pointerId); pinch0=null; if(!ptrs.size) canvas.classList.remove("dragging");
  if(had&&moved<6&&e.type==="pointerup") click(pos(e));
}
canvas.addEventListener("pointerup",up); canvas.addEventListener("pointercancel",up);
canvas.addEventListener("pointerleave",()=>{hideTip(); setHover(null);});
canvas.addEventListener("wheel",e=>{e.preventDefault(); stop(); const p=pos(e); zoomAt(p[0],p[1],Math.exp(-e.deltaY*(e.ctrlKey?.01:.0018)));},{passive:false});
function comunaAt(p){applyProj(); const g=projection.invert(p); if(!g||!isFinite(g[0])) return null; return RMF.find(f=>d3.geoContains(f,g))||null}
const tip=document.getElementById("tip");
function hideTip(){tip.classList.remove("on")}
function setHover(i){ if(S.hover!==i){S.hover=i; document.querySelectorAll(".row").forEach(r=>r.classList.toggle("hover",+r.dataset.i===i)); requestDraw();} }
function hover(p){
  if(level()!=="region"){ canvas.classList.remove("pointing"); hideTip(); return; }
  const f=comunaAt(p); canvas.classList.toggle("pointing",!!(f&&f.idx>=0));
  if(!f){hideTip(); setHover(null); return;}
  setHover(f.idx>=0?f.idx:null);
  tip.innerHTML=f.idx>=0&&scores.length?`${f.properties.Comuna}<small>Puesto ${rankOf(f.idx)} de ${COMUNAS.length}, puntaje ${nf0.format(scores[f.idx].total)}</small>`:`${f.properties.Comuna}<small>${f.idx>=0?"Simulando…":"Sin simular todavía"}</small>`;
  tip.style.left=p[0]+"px"; tip.style.top=p[1]+"px"; tip.classList.add("on");
}
function click(p){
  // Clicking the globe does nothing: only the button or scrolling enter the simulator, after their
  // animation. A click used to fly straight to the sample model's 12 communes, off the main flow.
  if(level()!=="region") return;
  const f=comunaAt(p); if(f&&f.idx>=0&&SIM) select(f.idx,true);
}

/* ---------- panel ---------- */
const $=id=>document.getElementById(id);
const DIM=["aire","seguridad","crecimiento"];
function sign(x,d){const v=Math.abs(x)<.05?0:x; return (v>0?"+":v<0?"−":"")+(d?nf1:nf0).format(Math.abs(v))}

function renderRank(){
  const ol=$("rank"), old=new Map([...ol.children].map(li=>[li.dataset.i,li.getBoundingClientRect().top]));
  if(!ol.children.length) COMUNAS.forEach((c,i)=>{
    const li=document.createElement("li"); li.dataset.i=i;
    li.innerHTML=`<button class="row" data-i="${i}"><span class="pos num"></span><span class="name">${c.name}</span><span class="bar"><i></i></span><span class="sc num"></span><span class="mv num"></span></button>`;
    li.firstChild.addEventListener("click",()=>select(i,true));
    li.firstChild.addEventListener("pointerenter",()=>setHover(i)); li.firstChild.addEventListener("pointerleave",()=>setHover(null));
    ol.appendChild(li);
  });
  const lis=new Map([...ol.children].map(li=>[+li.dataset.i,li]));
  order.forEach((i,p)=>{
    const li=lis.get(i), s=scores[i]; ol.appendChild(li);
    li.querySelector(".pos").textContent=p+1;
    const bar=li.querySelector(".bar i"); bar.style.width=Math.max(3,s.total)+"%"; bar.style.background=ramp(s.total/100);
    li.querySelector(".sc").textContent=nf0.format(s.total);
    const m=moves[i]||0, mv=li.querySelector(".mv"); mv.textContent=m>0?"▲"+m:m<0?"▼"+(-m):""; mv.className="mv num "+(m>0?"up":m<0?"down":"");
    li.firstChild.setAttribute("aria-label",`${COMUNAS[i].name}, puesto ${p+1}, puntaje ${nf0.format(s.total)}`);
  });
  if(!reduced) [...ol.children].forEach(li=>{
    const before=old.get(li.dataset.i); if(before==null) return; const dy=before-li.getBoundingClientRect().top; if(!dy) return;
    li.animate([{transform:`translateY(${dy}px)`},{transform:"none"}],{duration:320,easing:"cubic-bezier(.2,.7,.2,1)"});
  });
}
function dimRank(i,d){const key=["pm","del","pob"][d], better=d===2?-1:1; return scores.slice().sort((a,b)=>better*(a.raw[key]-b.raw[key])).findIndex(s=>s.i===i)+1}
function dimText(i,d){const r=scores[i].raw; return d===0?`PM2,5 de ${nf1.format(r.pm)} µg/m³`:d===1?`${VARS.del.fmt(r.del)} delitos por 100 mil hab.`:`población ${sign(r.pob,1)} %`}
function explain(){
  if(!baseline) return;
  moves={}; order.forEach((i,p)=>moves[i]=baseline.rank[i]-(p+1));
  let cause, d;
  const dw=S.w.map((w,j)=>w-baseline.w[j]), jmax=dw.reduce((b,x,j)=>Math.abs(x)>Math.abs(dw[b])?j:b,0);
  if(S.h!==baseline.h){cause=`Al mirar a ${S.h} años`; d=S.w.indexOf(Math.max(...S.w));}
  else if(S.shock!==baseline.shock){cause=S.shock?"Con el escenario de migración encendido":"Sin el escenario de migración"; d=2;}
  else if(dw[jmax]){cause=`Con ${dw[jmax]>0?"más":"menos"} peso en ${DIM[jmax]}`; d=jmax;}
  else return;
  const ids=Object.keys(moves).map(Number), upI=ids.reduce((b,i)=>moves[i]>moves[b]?i:b), dnI=ids.reduce((b,i)=>moves[i]<moves[b]?i:b);
  const n=COMUNAS.length, pl=x=>x===1?"1 puesto":x+" puestos", el=$("why");
  if(moves[upI]<=0){el.textContent=`${cause}, el orden no cambia. ${COMUNAS[order[0]].name} sigue primera.`; return;}
  el.innerHTML=`${cause}, <b>${COMUNAS[upI].name}</b> sube ${pl(moves[upI])}: es ${dimRank(upI,d)}.ª de ${n} en ${DIM[d]} (${dimText(upI,d)}). <b>${COMUNAS[dnI].name}</b> baja ${pl(-moves[dnI])}: es ${dimRank(dnI,d)}.ª (${dimText(dnI,d)}).`;
}
function syncControls(){
  ["A","S","P"].forEach((k,j)=>{$("w"+k).value=S.w[j]; const t=S.w[0]+S.w[1]+S.w[2]; $("o"+k).textContent=(t?Math.round(100*S.w[j]/t):33)+" %";});
  document.querySelectorAll("#horizon button").forEach(b=>b.setAttribute("aria-pressed",+b.dataset.h===S.h));
  document.querySelectorAll("#profiles button").forEach(b=>b.setAttribute("aria-pressed",b.dataset.p===S.profile));
  document.querySelectorAll("#vars button").forEach(b=>b.setAttribute("aria-pressed",b.dataset.v===S.v));
  $("legendTitle").textContent=`Puntaje a ${S.h} años con tus pesos`;
}
function update(commit){
  if(!SIM) return;
  compute(); explain(); syncControls(); renderRank(); if(S.sel!=null) renderDetail(); requestDraw();
  if(commit) baseline=snapshot();
}

/* gráfico de abanico */
function fan(q,o){
  const Wc=364,Hc=178,m={l:40,r:14,t:18,b:24}, n=q.length-1;
  const lo=Math.min(d3.min(q,d=>d.lo),o.dots?d3.min(o.dots):Infinity), hi=Math.max(d3.max(q,d=>d.hi),o.dots?d3.max(o.dots):-Infinity), pad=(hi-lo)*.12||1;
  const x=d3.scaleLinear([0,n],[m.l,Wc-m.r]), y=d3.scaleLinear([lo-pad,hi+pad],[Hc-m.b,m.t]);
  const area=d3.area().x((d,i)=>x(i)).y0(d=>y(d.lo)).y1(d=>y(d.hi))(q), line=d3.line().x((d,i)=>x(i)).y(d=>y(d.mid))(q);
  let s=`<svg viewBox="0 0 ${Wc} ${Hc}" role="img" aria-label="${o.aria}">`;
  y.ticks(3).forEach(t=>{s+=`<line x1="${m.l}" x2="${Wc-m.r}" y1="${y(t)}" y2="${y(t)}" stroke="var(--line)"/><text x="${m.l-6}" y="${y(t)+4}" text-anchor="end">${o.fmt(t)}</text>`;});
  (o.refs||[]).forEach(r=>{const yy=y(r.v); if(yy>m.t+10&&yy<Hc-m.b) s+=`<line x1="${m.l}" x2="${Wc-m.r}" y1="${yy}" y2="${yy}" stroke="var(--worse)" stroke-width="1.2" stroke-dasharray="4 3"/><text x="${m.l+4}" y="${yy-4}" style="fill:var(--worse)">${r.label}</text>`;});
  s+=`<path d="${area}" fill="var(--band)"/><path d="${line}" fill="none" stroke="var(--accent)" stroke-width="2"/>`;
  (o.ticks||[]).forEach(t=>{s+=`<text x="${x(t)}" y="${Hc-6}" text-anchor="${t===n?"end":t===0?"start":"middle"}">${o.start+t}</text>`;});
  (o.marks||[]).forEach(t=>{const on=t===o.sel; s+=`<line x1="${x(t)}" x2="${x(t)}" y1="${y(q[t].hi)}" y2="${y(q[t].lo)}" stroke="var(--ink)" stroke-width="${on?2:1}" opacity="${on?1:.35}"/><circle cx="${x(t)}" cy="${y(q[t].mid)}" r="${on?4.5:3}" fill="var(--panel)" stroke="var(--ink)" stroke-width="${on?2:1.2}"/>`;
    if(on) s+=`<text class="v" x="${Math.min(x(t),Wc-m.r-2)}" y="${y(q[t].hi)-7}" text-anchor="${t===n?"end":"middle"}">${o.fmt(q[t].mid)}</text>`;});
  (o.dots||[]).forEach((v,i)=>{s+=`<circle cx="${x(i)}" cy="${y(v)}" r="3.4" fill="var(--ink)"/>`;});
  return s+"</svg>";
}
function drivers(i){
  const c=COMUNAS[i], src=sim(i).src, h=S.h, pct=a=>(Math.exp(a[h])-1)*100, out=[];
  const row=(nm,lv,ch,eff,cred,why)=>out.push(`<div class="drv"><div class="top"><span class="nm">${nm}</span><span class="eff num">${eff}</span></div><div class="ch"><span class="lv">${lv}</span>${ch}</div>${cred!=null?`<div class="cred"><span>Credibilidad ${Math.round(cred*100)} %</span><span class="m"><i style="width:${cred*100}%"></i></span></div><div class="ch">${why}</div>`:why?`<div class="ch" style="margin-top:6px">${why}</div>`:""}</div>`);
  if(S.v==="pm"){
    row("Plan de descontaminación de la RM","Regional","Menos emisiones, menos PM2,5",sign(pct(src.pm.ppda),1)+" %",PPDA_CRED,"Según los informes de avance de la SMA.");
    if(c.seia) row("Proyecto industrial aprobado en el SEIA","Nacional","Nueva fuente de emisiones cercana",sign(pct(src.pm.seia),1)+" %",SEIA_PROB,"Probabilidad de que se construya tras su aprobación.");
    row("Crecimiento de población","Variable puente","Más viajes y calefacción",sign(pct(src.pm.pob),1)+" %",null,S.shock?"Incluye el escenario de migración.":"");
  } else if(S.v==="del"){
    row("Plan Comunal de Seguridad Pública","Comunal","Prevención y patrullaje, menos delitos",sign(pct(src.del.plan),1)+" %",c.planCred,c.planCred<.4?"Sin historial de cumplimiento publicado: la credibilidad parte baja.":"Según el historial de ejecución de planes anteriores.");
    out.push(`<div class="drv"><div class="ch" style="margin:0">La seguridad se mide con resultados (delitos y victimización), nunca por quién vive en la comuna.</div></div>`);
  } else {
    row("Tendencia entre censos","Línea base","Censo 2017 a 2024, frenada con la proyección de la ONU para Chile",sign(pct(src.pob.tend),1)+" %",null,"");
    if(c.seia) row("Proyecto industrial aprobado en el SEIA","Nacional","Empleo nuevo que atrae residentes",sign(pct(src.pob.seia),1)+" %",SEIA_PROB,"Probabilidad de que se construya tras su aprobación.");
    row("Sanciones a Venezuela, más migración","Internacional","Llegada de nuevos residentes",S.shock?sign(pct(src.pob.shock),1)+" %":"Apagado",null,S.shock?"Efecto debatido: entra como un rango amplio.":"Enciende el escenario en el ranking para verlo.");
  }
  return out.join("");
}
const WHO_AQG=5, WHO_IT=[35,25,15,10];
const SRC={who:"https://www.ncbi.nlm.nih.gov/books/NBK574591/", unodc:"https://www.unodc.org/unodc/data-and-analysis/global-study-on-homicide.html", wpp:"https://population.un.org/wpp/", r4v:"https://www.r4v.info"};
const ext=(u,t)=>`<a href="${u}" target="_blank" rel="noopener">${t}</a>`;
function intl(i,qh){
  let t;
  if(S.v==="pm"){
    const met=WHO_IT.filter(v=>qh.mid<=v), next=WHO_IT.filter(v=>qh.mid>v)[0];
    t=`La ${ext(SRC.who,"guía de la OMS de 2021")} recomienda 5 µg/m³ de PM2,5 como media anual. En ${YEAR0+S.h}, ${COMUNAS[i].name} quedaría en <b>${nf1.format(qh.mid/WHO_AQG)} veces</b> esa guía`+(met.length?`: cumpliría la meta intermedia de ${Math.min(...met)} µg/m³`+(next?`, pero no la de ${next}.`:"."):", sin cumplir ninguna meta intermedia.");
  } else if(S.v==="del"){
    t=`El ${ext(SRC.unodc,"Estudio Mundial sobre el Homicidio 2023 de UNODC")} registra 15,0 homicidios por 100 mil habitantes en las Américas y 5,8 en el mundo (2021). Aquí se proyectan delitos de mayor connotación, que cada país define distinto: sirven para comparar comunas entre sí, no países.`;
  } else {
    t=`Según ${ext(SRC.wpp,"World Population Prospects 2024 de la ONU")} (variante media), Chile pasa de 19,9 millones de habitantes en 2025 a un máximo cercano a 20,5 millones hacia 2040 y baja a 20,3 millones en 2050. La tendencia de cada comuna se frena a ese ritmo.`+(S.shock?` Para el escenario, ${ext(SRC.r4v,"R4V")} cuenta 6,9 millones de personas venezolanas refugiadas y migrantes en América Latina y el Caribe a noviembre de 2025.`:"");
  }
  return `<div class="drv"><div class="ch" style="margin:0; color:var(--ink)">${t}</div></div>`;
}
const SOURCES=[
  {f:"Mapa base", n:"OpenStreetMap", u:"https://www.openstreetmap.org/copyright", d:"Calles con nombre, metro, ríos y lugares del Gran Santiago, guardados dentro de la página (licencia ODbL).", use:"Contexto para ubicarse al acercar el mapa. No entra al puntaje."},
  {f:"Aire", n:"OMS, Guías mundiales de calidad del aire (2021)", u:SRC.who, d:"Guía anual de PM2,5 de 5 µg/m³ y metas intermedias de 35, 25, 15 y 10 µg/m³.", use:"Línea de referencia en el gráfico de aire de cada comuna."},
  {f:"Seguridad", n:"UNODC, Estudio Mundial sobre el Homicidio 2023", u:SRC.unodc, d:"15,0 homicidios por 100 mil habitantes en las Américas y 5,8 en el mundo (2021).", use:"Contexto regional. No entra al puntaje, que compara comunas entre sí."},
  {f:"Población", n:"ONU, World Population Prospects 2024", u:SRC.wpp, d:"Chile: 19,9 millones en 2025, máximo cercano a 20,5 millones hacia 2040 y 20,3 millones en 2050 (variante media).", use:"Frena la tendencia censal de cada comuna para que no crezca sin tope a 30 años."},
  {f:"Migración", n:"R4V, plataforma de ACNUR y OIM", u:SRC.r4v, d:"6,9 millones de personas venezolanas refugiadas y migrantes en América Latina y el Caribe (noviembre de 2025).", use:"Acota el rango del escenario internacional. Solo mueve la población, nunca la seguridad."}
];
function renderDetail(){
  const i=S.sel, c=COMUNAS[i], V=VARS[S.v], q=sim(i).q[S.v], h=S.h;
  $("dName").textContent=c.name;
  $("dSub").textContent=`Puesto ${rankOf(i)} de ${COMUNAS.length} a ${h} años, puntaje ${nf0.format(scores[i].total)}`;
  $("chart").innerHTML=fan(q,{start:YEAR0,ticks:[0,10,20,30],marks:[5,10,30],sel:h,refs:S.v==="pm"?WHO_IT.map(v=>({v,label:"Meta intermedia OMS: "+v})):null,fmt:V.fmt,aria:`${V.label} proyectado en ${c.name}, ${YEAR0} a ${YEAR0+30}`});
  $("read").innerHTML=`En ${YEAR0+h}, ${S.v==="pob"?"la población":S.v==="pm"?"el PM2,5":"los delitos"} quedaría entre <b>${V.fmt(q[h].lo)}</b> y <b>${V.fmt(q[h].hi)}</b> ${V.unit.replace(/\.$/,"")}. Hoy: ${V.fmt(q[0].mid)}.`;
  $("drivers").innerHTML=drivers(i);
  $("intl").innerHTML=intl(i,q[h]);
  const vm=VALID[i].model[S.v], ob=VALID[i].obs[S.v].map(d=>d.mid), inside=ob.slice(1).filter((v,j)=>v>=vm[j+1].lo&&v<=vm[j+1].hi).length;
  $("vchart").innerHTML=fan(vm,{start:2017,ticks:[0,2,4,7],dots:ob,fmt:V.fmt,aria:`Prueba retroactiva de ${V.label} en ${c.name}`});
  $("vread").innerHTML=`El modelo parte en 2017 con los planes de entonces. Lo observado (puntos) cayó dentro de la banda en <b>${inside} de 7</b> años.`;
}
function select(i,fly){
  S.sel=i;
  $("viewRank").hidden=i!=null; $("viewDetail").hidden=i==null; $("viewSources").hidden=true;
  if(i!=null){renderDetail(); syncControls(); $("viewDetail").scrollTop=0; if(fly) flyComuna(i);}
  requestDraw();
}

/* eventos del panel */
$("profiles").innerHTML=PROFILES.map(p=>`<button data-p="${p.id}">${p.label}</button>`).join("");
$("profiles").addEventListener("click",e=>{const b=e.target.closest("button"); if(!b) return; const p=PROFILES.find(p=>p.id===b.dataset.p); S.profile=p.id; S.w=p.w.slice(); update(true);});
["A","S","P"].forEach((k,j)=>{
  $("w"+k).addEventListener("input",e=>{S.w[j]=+e.target.value; S.profile=null; update(false);});
  $("w"+k).addEventListener("change",()=>{baseline=snapshot();});
});
$("horizon").addEventListener("click",e=>{const b=e.target.closest("button"); if(!b) return; S.h=+b.dataset.h; update(true);});
$("shock").addEventListener("change",e=>{S.shock=e.target.checked; update(true);});
$("vars").addEventListener("click",e=>{const b=e.target.closest("button"); if(!b) return; S.v=b.dataset.v; syncControls(); renderDetail();});
$("back").addEventListener("click",()=>{select(null,false); flyTo(REGION_C[0],REGION_C[1],regionK(),800);});
$("cta").addEventListener("click",()=>go("region"));
$("zin").addEventListener("click",()=>{stop(); zoomAt(centerX(view.k),centerY(view.k),1.6)});
$("zout").addEventListener("click",()=>{stop(); zoomAt(centerX(view.k),centerY(view.k),1/1.6)});

$("srcList").innerHTML=SOURCES.map(s=>`<div class="drv"><div class="top"><span class="nm">${ext(s.u,s.n)}</span></div><div class="ch"><span class="lv">${s.f}</span>${s.d}</div><div class="use"><b>En el modelo:</b> ${s.use}</div></div>`).join("");
$("openSrc").addEventListener("click",()=>{$("viewRank").hidden=true; $("viewSources").hidden=false; $("viewSources").scrollTop=0;});
$("backSrc").addEventListener("click",()=>{$("viewSources").hidden=true; $("viewRank").hidden=false;});

/* arranque */
readTheme();
matchMedia("(prefers-color-scheme: dark)").addEventListener("change",()=>{readTheme(); update(false);});
new MutationObserver(()=>{readTheme(); update(false);}).observe(document.documentElement,{attributes:true,attributeFilter:["data-theme"]});
syncControls();
const worker=new Worker(new URL("./simulation.worker.js", import.meta.url), {type:"module"});
worker.onmessage=e=>{ ({SIM,VALID}=e.data); worker.terminate(); compute(); baseline=snapshot(); renderRank(); requestDraw(); };
new ResizeObserver(resize).observe(stage); resize();
if(document.fonts&&document.fonts.ready) document.fonts.ready.then(requestDraw);

const HOME=[-58,-22];
const api={
  setIntro(cam){ intro=cam; hidden=false; draw(); if(!cam) requestDraw(); },
  // Vuelve a la vista "Mundo" de partida (sin comuna seleccionada) y avisa al terminar.
  goHome(){
    return new Promise(done=>{
      stop(); hideTip(); setHover(null); select(null,false);
      const atHome=view.k<1.02&&Math.abs(view.lon-HOME[0])<.5&&Math.abs(view.lat-HOME[1])<.5;
      flyTo(HOME[0],HOME[1],1,atHome?0:view.k>1.5?1400:700,done);
    });
  },
  world(){
    const r=stage.getBoundingClientRect(), w=r.width, h=r.height, isWide=innerWidth>860;
    return {x:isWide?w*.62:w*.5, y:isWide?h*.5:h*.27, r:Math.min(w,h)*(isWide?.4:.36)};
  }
};
mounted.set(root,api);
return api;
}

// El motor monta listeners, observers y un worker sobre el DOM. En desarrollo,
// si este archivo (o model.js) cambia, recargar la página entera: un reemplazo
// en caliente dejaría dos copias dibujando en el mismo canvas.
if(import.meta.hot) import.meta.hot.accept(()=>location.reload());
