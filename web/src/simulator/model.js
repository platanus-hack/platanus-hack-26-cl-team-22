// Modelo del "Simulador de comunas": datos de ejemplo y Monte Carlo con semilla.
// Lo usan engine.js (los datos) y simulation.worker.js (la simulación, fuera
// del hilo principal para no retrasar el globo del logo).
export const COMUNAS = [
  {name:"Santiago",         pm:24, del:9800, pob:440, growth:0.9, planCred:.45, seia:false, sens:1.0},
  {name:"Providencia",      pm:22, del:7200, pob:145, growth:0.5, planCred:.70, seia:false, sens:0.3},
  {name:"Las Condes",       pm:20, del:3600, pob:300, growth:0.6, planCred:.75, seia:false, sens:0.2},
  {name:"Ñuñoa",            pm:22, del:3900, pob:245, growth:0.8, planCred:.65, seia:false, sens:0.4},
  {name:"Maipú",            pm:25, del:2600, pob:505, growth:0.3, planCred:.50, seia:true,  sens:0.4},
  {name:"Puente Alto",      pm:26, del:2900, pob:570, growth:0.4, planCred:.40, seia:false, sens:0.3},
  {name:"La Florida",       pm:24, del:3200, pob:375, growth:0.2, planCred:.55, seia:false, sens:0.3},
  {name:"Pudahuel",         pm:29, del:3400, pob:230, growth:0.7, planCred:.35, seia:true,  sens:0.3},
  {name:"Cerro Navia",      pm:30, del:3100, pob:130, growth:-0.2,planCred:.25, seia:false, sens:0.2},
  {name:"Quilicura",        pm:27, del:3800, pob:215, growth:1.0, planCred:.40, seia:true,  sens:0.7},
  {name:"Estación Central", pm:26, del:6100, pob:210, growth:1.2, planCred:.30, seia:false, sens:1.0},
  {name:"Peñalolén",        pm:23, del:2700, pob:240, growth:0.3, planCred:.60, seia:false, sens:0.2}
];
export const PPDA_CRED = .60, SEIA_PROB = .70;

/* ---------- Monte Carlo (corre una vez) ---------- */
export function mulberry32(a){return function(){a|=0;a=a+0x6D2B79F5|0;let t=Math.imul(a^a>>>15,1|a);t=t+Math.imul(t^t>>>7,61|t)^t;return((t^t>>>14)>>>0)/4294967296}}
export function simulate(c, o){
  const years=o.years, n=o.n, vals={pm:[],del:[],pob:[]};
  const src={pm:{ppda:[],seia:[],pob:[]}, del:{plan:[]}, pob:{tend:[],seia:[],shock:[]}};
  for(let y=0;y<=years;y++){ for(const v in vals) vals[v][y]=new Float64Array(n); for(const v in src) for(const s in src[v]) src[v][s][y]=0; }
  for(let r=0;r<n;r++){
    const rnd=mulberry32(o.seed+r*7919), U=(a,b)=>a+(b-a)*rnd();
    const G=()=>{let u=0,v=0;while(!u)u=rnd();v=rnd();return Math.sqrt(-2*Math.log(u))*Math.cos(6.283185307*v)};
    const ppdaOk=rnd()<PPDA_CRED, ppdaRate=U(.008,.022)*(ppdaOk?U(.5,1):U(0,.25));
    const planOk=rnd()<c.planCred, planRate=U(.006,.025)*(planOk?U(.5,1):U(0,.2));
    const built=(rnd()<SEIA_PROB)&&c.seia, seiaPm=U(.4,1.4);
    const shockRate=U(0,.009)*c.sens, beta=U(.1,.3), drift=G()*.004;
    let pm=c.pm, del=c.del, pob=c.pob;
    const L={ppda:0,seiaPm:0,bridge:0,plan:0,tend:0,seiaPob:0,shock:0};
    vals.pm[0][r]=pm; vals.del[0][r]=del; vals.pob[0][r]=pob;
    for(let y=1;y<=years;y++){
      const g=c.growth/100+NAT(y+(o.y0||0))+G()*.003;
      const gS=(built&&y>=3&&y<=12)?.0015:0, gK=(o.shock&&y<=6)?shockRate:0;
      pob*=1+g+gS+gK; L.tend+=Math.log(1+g); L.seiaPob+=Math.log(1+gS); L.shock+=Math.log(1+gK);
      const fP=y<=12?-ppdaRate:-ppdaRate*.15, fB=beta*(g+gS+gK);
      pm*=(1+fP)*(1+fB)*(1+G()*.015); L.ppda+=Math.log(1+fP); L.bridge+=Math.log(1+fB);
      if(built&&y===3){const b=pm; pm+=seiaPm; L.seiaPm+=Math.log(pm/b);}
      pm=Math.max(pm,8);
      const fL=y<=8?-planRate:-planRate*.2;
      del*=(1+fL)*(1+drift+G()*.025); L.plan+=Math.log(1+fL);
      vals.pm[y][r]=pm; vals.del[y][r]=del; vals.pob[y][r]=pob;
      src.pm.ppda[y]+=L.ppda/n; src.pm.seia[y]+=L.seiaPm/n; src.pm.pob[y]+=L.bridge/n;
      src.del.plan[y]+=L.plan/n;
      src.pob.tend[y]+=L.tend/n; src.pob.seia[y]+=L.seiaPob/n; src.pob.shock[y]+=L.shock/n;
    }
  }
  const q={};
  for(const v in vals) q[v]=vals[v].map(a=>{const s=Array.from(a).sort((x,y)=>x-y); const at=p=>s[Math.min(n-1,Math.floor(p*n))]; return {lo:at(.1),mid:at(.5),hi:at(.9)}});
  return {q, src};
}
/* ONU, World Population Prospects 2024: el crecimiento de Chile se frena y pasa a negativo cerca de 2040 */
export function NAT(y){return y<=0?0:Math.max(-.0075,-.0003*y)}
/** Corre todas las réplicas (unos 300 ms): la usa simulation.worker.js. */
export function runAll(){
  const SIM = COMUNAS.map((c,i)=>({
    off: simulate(c,{years:30,n:500,seed:1000+i*131,shock:false}),
    on:  simulate(c,{years:30,n:500,seed:1000+i*131,shock:true})
  }));
  const VALID = COMUNAS.map((c,i)=>{
    const c17={...c, pm:c.pm*1.13, del:c.del*1.05, pob:c.pob/Math.pow(1+c.growth/100,7)};
    return {model:simulate(c17,{years:7,n:300,seed:50+i*17,shock:false,y0:-9}).q, obs:simulate(c17,{years:7,n:1,seed:9000+i*29,shock:false,y0:-9}).q};
  });
  return {SIM, VALID};
}
