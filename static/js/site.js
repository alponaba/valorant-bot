const coachSamples = [
  {text:"Son maçlarında HS oranı güçlü kalırken ADR düşmüş. Bir sonraki ranked'da ilk temasta kill zorlamak yerine utility sonrası trade mesafesini koru; özellikle Lotus'ta erken re-peek sayını azalt.", meta:"Aim iyi • Impact düşüyor • Lotus odak"},
  {text:"K/D dengeli ama kaybettiğin maçlarda ilk ölüm zinciri uzuyor. Warm-up'ı büyütmek yerine ilk 5 round boyunca yalnızca pozisyon ve trade kararını takip et; aim rutinin zaten yeterli görünüyor.", meta:"Consistency odak • Tilt riski orta"},
  {text:"Jett ile giriş etkisi yüksek, fakat avantaj aldıktan sonra ikinci düelloda değer kaybediyorsun. Entry sonrası takımın yetişene kadar açıyı kapatman V-Score istikrarını artırabilir.", meta:"Jett main • Aggressive Entry DNA"}
];
let coachIndex=0;
function rotateCoach(){
  const quote=document.querySelector('[data-coach-quote]');
  const meta=document.querySelector('[data-coach-meta]');
  if(!quote||!meta)return;
  coachIndex=(coachIndex+1)%coachSamples.length;
  quote.style.opacity='0';
  setTimeout(()=>{quote.textContent=coachSamples[coachIndex].text;meta.textContent=coachSamples[coachIndex].meta;quote.style.opacity='1';},180);
}
setInterval(rotateCoach,5200);

async function loadStatus(){
  const boxes=document.querySelectorAll('[data-status-key]');
  if(!boxes.length)return;
  try{
    const res=await fetch('/health',{cache:'no-store'}); const data=await res.json();
    boxes.forEach(el=>{
      const key=el.dataset.statusKey;
      if(key==='service') el.textContent=data.status==='ok'?'Online':'Degraded';
      if(key==='uptime'){
        const h=Math.floor((data.uptime_seconds||0)/3600); const m=Math.floor(((data.uptime_seconds||0)%3600)/60); el.textContent=`${h}h ${m}m`;
      }
      if(key==='api') el.textContent=data.api?.circuit_open?'Cooldown':'Ready';
      if(key==='latency') el.textContent=`${Math.round(data.api?.last_latency_ms||0)} ms`;
    });
  }catch(e){boxes.forEach(el=>el.textContent='Offline');}
}
loadStatus();

const search=document.querySelector('[data-command-search]');
const tabs=[...document.querySelectorAll('[data-command-tab]')];
function filterCommands(){
  if(!search)return;
  const q=search.value.trim().toLowerCase();
  const active=document.querySelector('[data-command-tab].active')?.dataset.commandTab||'all';
  document.querySelectorAll('[data-command-card]').forEach(card=>{
    const hay=card.textContent.toLowerCase();
    const cat=card.dataset.category;
    card.style.display=(!q||hay.includes(q))&&(active==='all'||cat===active)?'block':'none';
  });
}
search?.addEventListener('input',filterCommands);
tabs.forEach(t=>t.addEventListener('click',()=>{tabs.forEach(x=>x.classList.remove('active'));t.classList.add('active');filterCommands();}));
