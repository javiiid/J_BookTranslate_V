"""Persistent dashboard selection and live job overview."""


def install_jobs_dashboard(page):
    panel = '''<section class="card" id="active-jobs" style="margin-bottom:18px">
<h2>کارهای فعال و اخیر</h2>
<p>با خروج از این صفحه، ترجمه ادامه دارد. برای دیدن پیشرفت و کنترل هر کار، آن را انتخاب کنید.</p>
<p id="jobs-connection" role="status">در حال دریافت کارها…</p>
<div class="jobs-filters"><input id="jobs-search" type="search" placeholder="نام کتاب را جست‌وجو کنید…" aria-label="جست‌وجوی کارها"><select id="jobs-filter" aria-label="فیلتر وضعیت"><option value="all">همهٔ کارها</option><option value="active">در حال انجام</option><option value="paused">متوقف‌شده و نیازمند بررسی</option><option value="completed">تکمیل‌شده</option></select></div>
<div id="jobs-list" style="display:grid;gap:8px;max-height:320px;overflow:auto"></div>
<div class="job-live-grid" id="job-live" hidden><div class="job-live-stat"><span>سلامت ترجمه</span><strong id="job-health" aria-label="وضعیت سلامت ترجمه">—</strong></div><div class="job-live-stat"><span>سرعت واقعی</span><strong id="job-speed" aria-label="سرعت ترجمه در بخش‌های دقیقه">—</strong></div><div class="job-live-stat"><span>زمان باقی‌مانده</span><strong id="job-eta" aria-label="زمان تقریبی باقی‌مانده">—</strong></div></div>
<div class="job-ux-actions" id="job-ux-actions" hidden><button type="button" class="secondary" id="safe-resume" aria-label="ادامه ترجمه از آخرین جای سالم">ادامه از آخرین جای سالم</button><button type="button" class="secondary" id="rescue-project" aria-label="ساخت نسخهٔ نجات پروژه">نجات پروژه</button></div>
<details class="job-timeline" id="job-timeline" hidden><summary>تایم‌لاین کامل اتفاقات Job</summary><div id="job-events">در حال دریافت…</div></details>
</section>'''
    page = page.replace('<section class="card job"', panel + '<section class="card job"', 1)
    return page.replace('</body>', SCRIPT + '</body>', 1)


SCRIPT = '''<script>
(()=>{
const storageKey='jbook-selected-job';
const statuses={queued:'در صف',running:'در حال ترجمه',stopping:'در حال توقف',paused:'متوقف‌شده',stopped:'متوقف‌شده',completed:'تکمیل‌شده',failed:'خطا',cancelled:'لغوشده'};
const active=status=>['queued','running','stopping'].includes(status);
const rank=status=>active(status)?0:['paused','failed'].includes(status)?1:2;
const list=document.getElementById('jobs-list'),connection=document.getElementById('jobs-connection');
const search=document.getElementById('jobs-search'),filter=document.getElementById('jobs-filter');
const originalRender=render;
let items=[],busy=false,actionBusy=false,pending=false,selectedByUser=false,connected=false;
let timelineJob='';
try{jobId=localStorage.getItem(storageKey)||undefined}catch{}
function remember(){try{if(jobId)localStorage.setItem(storageKey,jobId);else localStorage.removeItem(storageKey)}catch{}}
function chooseJob(jobs,selected,explicit){
 const found=jobs.find(item=>item.id===selected);
 if(explicit&&found)return found;
 return jobs.find(item=>active(item.status))||found||jobs.find(item=>['paused','failed'].includes(item.status))||jobs[0];
}
function controls(){
 const occupied=items.some(item=>active(item.status));
 submit.disabled=!connected;
 submit.textContent=!connected?'در انتظار اتصال…':occupied?'افزودن کتاب به صف':'شروع ترجمه';
 $('#stop').disabled=!connected||actionBusy;
 $('#resume').disabled=!connected||actionBusy||occupied;
}
const duration=value=>{if(!value)return '—';const minutes=Math.ceil(value/60);return minutes<60?fa(minutes)+' دقیقه':fa(Math.floor(minutes/60))+' ساعت و '+fa(minutes%60)+' دقیقه'};
async function loadTimeline(id){try{const response=await fetch('/api/jobs/'+encodeURIComponent(id)+'/logs',{cache:'no-store'});const data=await response.json();const box=$('#job-events');box.replaceChildren();for(const event of (data.items||[]).slice(-30).reverse()){const row=document.createElement('div');row.className='timeline-event '+String(event.level||'').toLowerCase();const title=document.createElement('strong');title.textContent=event.message;const time=document.createElement('span');time.textContent=date(event.timestamp);row.append(title,time);box.append(row)}if(!box.childElementCount)box.textContent='هنوز رویدادی ثبت نشده است.'}catch{$('#job-events').textContent='دریافت تایم‌لاین ممکن نشد.'}}
function showSelected(){
 const selected=items.find(item=>item.id===jobId);
 if(selected){
  jobBox.style.display='block';
  originalRender(selected);
  $('#chip').textContent=statuses[selected.status]||selected.status;
  $('#job-meta').textContent=[selected.filetype,selected.source_language,selected.target_language,selected.model].filter(Boolean).join(' · ');
  $('#progress-label').textContent=selected.progress.total?fa(selected.progress.completed)+' از '+fa(selected.progress.total)+' بخش ترجمه شده':'در حال آماده‌سازی کتاب…';
  const bar=$('#progress');
  bar.setAttribute('role','progressbar');
  bar.setAttribute('aria-valuenow',String(selected.progress.percent));
  bar.setAttribute('aria-valuemin','0');
  bar.setAttribute('aria-valuemax','100');
  bar.setAttribute('aria-label','پیشرفت ترجمه');
  $('#job-live').hidden=false;$('#job-ux-actions').hidden=false;$('#job-timeline').hidden=false;
  const healthNames={green:'سالم',yellow:'نیازمند توجه',red:'دارای مشکل'};$('#job-health').textContent=healthNames[selected.health]||'—';$('#job-health').className='health-'+selected.health;
  $('#job-speed').textContent=selected.chunks_per_minute?fa(selected.chunks_per_minute)+' بخش/دقیقه':'در حال محاسبه';$('#job-eta').textContent=duration(selected.eta_seconds);
  $('#safe-resume').hidden=!selected.can_resume;
  if(timelineJob!==selected.id||selected.status==='running'){timelineJob=selected.id;loadTimeline(selected.id)}
 }
 else{jobBox.style.display='none';$('#job-live').hidden=true;$('#job-ux-actions').hidden=true;$('#job-timeline').hidden=true}
 controls();
}
function draw(){
 const query=(search.value||'').trim().toLocaleLowerCase();
 const sorted=items.filter(item=>item.filename.toLocaleLowerCase().includes(query)&&(!filter.value||filter.value==='all'||(filter.value==='active'?active(item.status):filter.value==='paused'?['paused','failed'].includes(item.status):item.status==='completed'))).sort((left,right)=>rank(left.status)-rank(right.status)||String(right.created_at).localeCompare(String(left.created_at)));
 const signature=JSON.stringify([query,filter.value,sorted.map(item=>[item.id,item.filename,item.status,item.progress.percent,item.id===jobId])]);
 if(list.dataset.signature===signature)return;
 list.dataset.signature=signature;
 list.replaceChildren();
 if(!sorted.length){list.textContent=items.length?'کاری با این مشخصات پیدا نشد.':'اولین کتابت را از «ترجمهٔ جدید» اضافه کن.';return}
 for(const item of sorted){
  const button=document.createElement('button');button.type='button';button.className='job-list-item';
  button.setAttribute('aria-pressed',String(item.id===jobId));
  button.setAttribute('aria-label',item.filename+' - '+(statuses[item.status]||item.status)+' - '+Math.round(item.progress.percent)+'%');
  button.textContent=item.filename;
  button.replaceChildren();
  const title=document.createElement('strong');title.className='job-list-title';title.textContent=item.filename;
  const meta=document.createElement('span');meta.className='job-list-meta';meta.textContent=(statuses[item.status]||item.status)+' · '+fa(item.progress.percent)+'٪';
  const track=document.createElement('span');track.className='job-list-track';const fill=document.createElement('span');fill.style.width=Math.max(0,Math.min(100,item.progress.percent))+'%';track.append(fill);
  button.append(title);button.append(meta);button.append(track);
  button.onclick=()=>{jobId=item.id;selectedByUser=true;remember();draw();showSelected();jobBox.scrollIntoView({behavior:'smooth',block:'nearest'})};
  list.append(button);
 }
}
async function refresh(){
 if(busy){pending=true;return}
 busy=true;
 try{
  const response=await fetch('/api/jobs',{cache:'no-store'});
  if(!response.ok)throw Error('jobs');
  const data=await response.json();
  if(pending)return;
  if(!Array.isArray(data.items))throw Error('jobs');
  items=data.items;connected=true;
  const selected=chooseJob(items,jobId,selectedByUser);
  jobId=selected?.id;remember();
  connection.textContent='متصل · '+fa(items.filter(item=>active(item.status)).length)+' کار فعال';
  draw();showSelected();
 }catch{connected=false;connection.textContent='ارتباط با سرور قطع است؛ اطلاعات قبلی نمایش داده می‌شود. تلاش مجدد خودکار…';controls()}
 finally{busy=false;if(pending){pending=false;refresh()}}
}
watch=function(){clearInterval(timer);selectedByUser=true;remember();const composer=document.getElementById('new-translation');if(composer)composer.open=false;refresh()};
action=async function(name){
 if(!jobId||actionBusy||!connected)return;
 if(name==="stop"||name==="cancel"){
   if(!confirm("آیا از توقف/لغو این ترجمه مطمئن هستید؟"))return;
 }
 actionBusy=true;controls();const selected=jobId;
 try{const response=await fetch('/api/jobs/'+encodeURIComponent(selected)+'/'+name,{method:'POST'});const data=await response.json();if(!response.ok)throw Error(data.error||'عملیات انجام نشد')}
 catch(error){$('#error').textContent=error.message;$('#error').style.display='block';const toast=document.getElementById('sidebar-toast');if(toast){toast.textContent=name==='stop'?'ترجمه متوقف شد.':name==='cancel'?'ترجمه لغو شد.':'عملیات انجام نشد.';toast.style.display='block';setTimeout(function(){toast.style.display='none'},3000)}}finally{actionBusy=false;await refresh();controls()}
};
$('#safe-resume').onclick=()=>action('resume');
$('#rescue-project').onclick=async()=>{if(!jobId)return;const button=$('#rescue-project');button.disabled=true;try{const response=await fetch('/api/jobs/'+encodeURIComponent(jobId)+'/rescue',{method:'POST'}),data=await response.json();if(!response.ok)throw Error(data.error||'ساخت نسخهٔ نجات ناموفق بود');location.href=data.download}catch(error){$('#error').textContent=error.message;$('#error').style.display='block'}finally{button.disabled=false;loadTimeline(jobId)}};
search.addEventListener('input',draw);filter.addEventListener('change',draw);
submit.disabled=true;
refresh();
setInterval(()=>{if(!document.hidden)refresh()},2000);
window.addEventListener('pageshow',refresh);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)refresh()});
})();
</script>'''
