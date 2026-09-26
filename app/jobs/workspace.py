"""Responsive, task-focused dashboard presentation."""

from app.core.fonts import embedded_vazirmatn_font_faces


def install_workspace(page):
    page = page.replace("@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap');", '')
    return page.replace('</head>', embedded_vazirmatn_font_faces() + STYLE + '</head>', 1).replace('</body>', SCRIPT + '</body>', 1)


STYLE = '''<style>
:root{--bg:#f5f6fa;--surface:#fff;--ink:#202c43;--muted:#68758a;--line:#e3e7ee;--shadow:0 4px 24px #172f5610}
body{background:var(--bg);line-height:1.8;font-family:Vazirmatn,Tahoma,sans-serif!important}
body.app-dark{--bg:#131923;--surface:#1c2533;--ink:#e6edf7;--muted:#a8b6ca;--line:#344155;background:var(--bg)!important}
body .shell{margin:0 auto!important;padding:28px 32px 64px;max-width:1440px!important}
.app-sidebar,.dashboard>.side,.summary-strip{display:none!important}
.workspace-nav{display:flex;gap:8px;align-items:center;flex-wrap:wrap;padding:0 0 20px;border-bottom:1px solid var(--line);margin-bottom:24px}
.workspace-nav strong{margin-inline-end:auto;font-size:18px}.workspace-nav a{padding:8px 16px;text-decoration:none;color:var(--muted);border-radius:10px;font-size:14px}.workspace-nav a[aria-current]{background:#356df614;color:var(--blue);font-weight:700}
.top{margin-bottom:24px}.brand h1{font-size:26px}.brand p{font-size:14px}.logo{box-shadow:none}.api-pill{box-shadow:none;flex-wrap:wrap;max-width:100%}
body .dashboard{display:flex;flex-direction:column;gap:20px}.dashboard-cards{margin:0!important;gap:16px}.dashboard-card{border-top:0!important;border-radius:14px;box-shadow:none;padding:18px 22px}.dashboard-card label{font-size:13px}.dashboard-card strong{font-size:28px}
.workspace-main{display:grid;grid-template-columns:minmax(280px,.8fr) minmax(0,1.5fr);gap:20px;align-items:start}
body .card,body .dashboard-card{background:var(--surface)!important;color:var(--ink);border:1px solid var(--line)!important;box-shadow:var(--shadow)}
#active-jobs{padding:22px;margin:0!important;min-width:0}#active-jobs h2{font-size:18px;margin:0}#active-jobs>p{font-size:12px;color:var(--muted);margin:6px 0 16px}#jobs-connection{padding:8px 12px;border-radius:8px;background:#356df60b;font-size:12px!important}
.jobs-filters{display:grid;gap:8px;margin-bottom:16px}.jobs-filters input,.jobs-filters select{font-size:13px;min-height:44px}
#jobs-list{max-height:580px!important}.job-list-item{display:grid;gap:7px;width:100%;min-width:0;text-align:right;padding:14px;background:var(--surface);color:var(--ink);border:1px solid var(--line);border-radius:12px;box-shadow:none}
.job-live-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:16px}.job-live-stat{padding:12px;border:1px solid var(--line);border-radius:11px;background:var(--bg)}.job-live-stat span{display:block;font-size:10px;color:var(--muted)}.job-live-stat strong{font-size:13px}.health-green{color:#078a63!important}.health-yellow{color:#bd7a0d!important}.health-red{color:#cf3f4a!important}.job-ux-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:12px}.job-timeline{margin-top:14px;border-top:1px solid var(--line);padding-top:12px}.job-timeline summary{cursor:pointer;font-weight:700}.timeline-event{display:flex;justify-content:space-between;gap:12px;padding:9px 0;border-bottom:1px solid var(--line);font-size:11px}.timeline-event span{color:var(--muted);white-space:nowrap}.timeline-event.error strong{color:#cf3f4a}
.job-list-item[aria-pressed=true]{border-color:#356df6;background:#356df610}.job-list-title{font-size:13px;font-weight:600;overflow-wrap:anywhere;unicode-bidi:plaintext}.job-list-meta{font-size:12px;font-weight:400;color:var(--muted)}.job-list-track{height:4px;border-radius:8px;background:var(--line);overflow:hidden}.job-list-track>span{display:block;height:100%;background:var(--blue)}
.workspace-detail{min-width:0}.workspace-detail:has(#job[style*="none"])::before{content:'برای دیدن جزئیات، یک کار را انتخاب کن. بعد از شروع ترجمه، پیشرفت اینجا نمایش داده می‌شود.';display:block;padding:54px 28px;border:1px dashed var(--line);border-radius:18px;color:var(--muted);text-align:center}
#job{margin-top:0;padding:28px}#job-name{font-size:20px;line-height:1.7}#job-meta{overflow-wrap:anywhere}.job-actions>*{min-height:44px}.job .stats{gap:12px}.stat{padding:14px;background:var(--bg)!important;border-color:var(--line)!important}.stat strong{color:var(--ink)}.chip{margin:0}.chip.paused{background:#e7a02320;color:#ad7915}
.composer{border:1px solid var(--line);border-radius:16px;background:var(--surface);overflow:hidden;transition:border-color .2s}.composer[open]{border-color:var(--blue);box-shadow:0 4px 20px rgba(53,109,246,.08)}.composer>summary{cursor:pointer;padding:18px 22px;font-size:16px;font-weight:700;color:var(--blue);list-style:none;display:flex;align-items:center;gap:12px}.composer>summary::-webkit-details-marker{display:none}.composer>summary small{font-weight:400;color:var(--muted);margin-inline-start:auto;font-size:12px}.composer .form-card{border:0!important;box-shadow:none;padding:0 24px 24px}.composer .section-title{display:none}.composer .drop{min-height:120px}.composer .primary{max-width:360px}#auto-glossary-note{font-size:12px;color:var(--muted)}
/* Ordered form steps */
.form-step{border:1px solid var(--line);border-radius:12px;padding:16px;background:var(--bg);margin-bottom:12px}
.form-step legend{font-size:13px;font-weight:700;color:var(--ink);padding:0 6px;display:flex;align-items:center;gap:8px}
.form-step legend span.step-num{width:22px;height:22px;border-radius:50%;background:var(--blue);color:#fff;display:grid;place-items:center;font-size:11px;font-weight:800}
/* Convert card as ordered second composer */
#convert-card{border:1px solid var(--line);border-radius:16px;background:var(--surface);overflow:hidden}
#convert-card .section-title{font-size:15px}
#convert-card .drop{min-height:100px}
.composer-convert{border:1px solid var(--line);border-radius:16px;background:var(--surface);overflow:hidden}
.composer-convert[open]{border-color:var(--green);box-shadow:0 4px 20px rgba(8,150,108,.08)}
.composer-convert>summary{cursor:pointer;padding:18px 22px;font-size:16px;font-weight:700;color:var(--green);display:flex;align-items:center;gap:12px;list-style:none}
.composer-convert>summary::-webkit-details-marker{display:none}
.composer-convert>summary small{font-weight:400;color:var(--muted);margin-inline-start:auto;font-size:12px}

body input,body select,body textarea{background:var(--surface)!important;color:var(--ink)!important;border-color:var(--line)!important}input[type=checkbox]{min-height:auto;width:auto}.drop{background:var(--bg)!important}.drop:focus-within{outline:3px solid #356df6}
button:focus-visible,a:focus-visible,summary:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #7299ff;outline-offset:3px}button:hover:not(:disabled){transform:none}button[hidden],a[hidden]{display:none!important}
@media(max-width:900px){body .shell{padding:20px 18px 40px}.workspace-main{grid-template-columns:1fr}.dashboard-cards{grid-template-columns:repeat(2,1fr)}#jobs-list{max-height:270px!important}.top{flex-wrap:wrap}.workspace-nav strong{width:100%}}
@media(max-width:540px){body .shell{padding:16px 12px 32px}.workspace-nav{gap:2px}.workspace-nav a{padding:8px 12px}.dashboard-card{padding:12px 16px}.brand h1{font-size:22px}.api-pill{border-radius:12px}#job,#active-jobs{padding:18px}.job .stats{grid-template-columns:1fr}.composer>summary small{display:block;margin:4px 0}.composer .form-card{padding:0 16px 20px}.job-head{display:flex;flex-direction:column}.grid2{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
</style>'''


SCRIPT = '''<script>
(()=>{
const shell=document.querySelector('.shell'),dashboard=document.querySelector('.dashboard'),formCard=document.querySelector('.form-card');
const nav=document.createElement('nav');nav.className='workspace-nav';nav.setAttribute('aria-label','ناوبری اصلی');nav.innerHTML='<strong>J Book Translate</strong><a href="/" aria-current="page" aria-label="میز کار">میز کار</a><a href="/library" aria-label="کتابخانه">کتابخانه</a><a href="#active-jobs" aria-label="کارهای فعال">کارهای من</a><a href="#new-translation" id="open-composer" aria-label="ترجمهٔ جدید">＋ ترجمهٔ جدید</a><a href="#convert-card" id="open-convert" aria-label="تبدیل فایل بدون ترجمه">⇄ تبدیل فایل</a>';shell.prepend(nav);
document.querySelector('.brand h1').textContent='میز کار ترجمه';document.querySelector('.brand p').textContent='کتاب‌هایت را ترجمه کن؛ پیشرفتشان را همین‌جا دنبال کن.';
const main=document.createElement('div');main.className='workspace-main';const detail=document.createElement('div');detail.className='workspace-detail';detail.append(document.getElementById('job'));main.append(document.getElementById('active-jobs'));main.append(detail);
const composer=document.createElement('details');composer.id='new-translation';composer.className='composer';composer.open=true;const summary=document.createElement('summary');summary.innerHTML='<span style="width:28px;height:28px;border-radius:50%;background:var(--blue);color:#fff;display:grid;place-items:center;font-size:14px">1</span> ترجمهٔ جدید <small>انتخاب کتاب، زبان و خروجی‌ها → شروع</small>';composer.append(summary);composer.append(formCard);
dashboard.append(main);dashboard.append(composer);
// --- Convert: ordered second step, user-friendly ---
const convertCard=document.getElementById('convert-card');
if(convertCard){
  convertCard.classList.remove('form-card');
  convertCard.style.marginTop='0';
  const cWrap=document.createElement('details');cWrap.id='convert-section';cWrap.className='composer-convert';cWrap.open=false;
  const cSum=document.createElement('summary');cSum.innerHTML='<span style="width:28px;height:28px;border-radius:50%;background:var(--green);color:#fff;display:grid;place-items:center;font-size:14px">2</span> تبدیل سریع فایل <small>بدون ترجمه — EPUB/PDF/SRT → TXT/MD/DOCX/PDF/JSON</small>';
  const cInner=document.createElement('div');cInner.style.padding='0 24px 24px';
  cInner.append(convertCard);
  cWrap.append(cSum);cWrap.append(cInner);
  dashboard.append(cWrap);
  document.getElementById('open-convert').onclick=(e)=>{e.preventDefault();cWrap.open=true;cWrap.scrollIntoView({behavior:'smooth',block:'start'})};
  // Order hint: if no active jobs, keep convert collapsed to avoid overwhelm
}
// Add ordered helper inside translate form
const langRow=formCard.querySelector('.grid2');
if(langRow && !formCard.querySelector('.form-step')){
  // Wrap existing grids into ordered steps
  const steps=document.createElement('div');steps.style.display='grid';steps.style.gap='12px';
  const s1=document.createElement('fieldset');s1.className='form-step';s1.innerHTML='<legend><span class="step-num">1</span> فایل و زبان</legend>';
  const s2=document.createElement('fieldset');s2.className='form-step';s2.innerHTML='<legend><span class="step-num">2</span> تنظیمات خروجی</legend>';
  // Move file drop + lang selects into s1, rest into s2 (best effort)
  const drop=formCard.querySelector('.drop');
  const grid2s=[...formCard.querySelectorAll('.grid2')];
  if(drop) s1.append(drop, formCard.querySelector('.file-info')||document.createElement('div'));
  grid2s.slice(0,1).forEach(g=>s1.append(g));
  grid2s.slice(1).forEach(g=>s2.append(g));
  const adv=formCard.querySelector('details.advanced');
  if(adv) s2.append(adv);
  // CRITICAL: prepend into the <form> itself — inputs outside <form> are
  // excluded from FormData(form) and the server rejects the job with
  // "only EPUB/PDF accepted" (empty upload_name).
  const tForm=document.getElementById('translate-form');
  tForm.prepend(s2);tForm.prepend(s1);
}
document.getElementById('open-composer').onclick=()=>{composer.open=true;composer.scrollIntoView({behavior:'smooth',block:'start'})};document.getElementById('open-composer').setAttribute('aria-label','باز کردن فرم ترجمهٔ جدید');
document.querySelector('#job .stat span').textContent='بخش‌های ترجمه‌شده';document.querySelector('#stop').textContent='توقف امن ترجمه';
document.querySelector('#job .logs summary').textContent='جزئیات فنی و گزارش اجرا';
const hint=document.createElement('p');hint.className='small';hint.textContent='با بستن این صفحه ترجمه متوقف نمی‌شود. برای توقف، از دکمهٔ «توقف امن ترجمه» استفاده کن.';document.querySelector('.job-actions').after(hint);
document.querySelectorAll('#translate-form input:not([type=checkbox]),#translate-form select,#translate-form textarea').forEach((input,index)=>{input.id=input.id||'translation-field-'+index;const label=input.previousElementSibling;if(label?.tagName==='LABEL')label.htmlFor=input.id});
const translationForm=document.getElementById('translate-form'),bookInput=document.getElementById('book');bookInput.multiple=true;bookInput.addEventListener('change',()=>{const files=[...bookInput.files];if(files.length>1){const total=files.reduce((sum,file)=>sum+file.size,0);fileInfo.textContent=files.length+' کتاب · '+size(total);fileInfo.style.display='block'}});
translationForm.addEventListener('submit',async event=>{const files=[...bookInput.files];if(files.length<2)return;event.preventDefault();event.stopImmediatePropagation();submit.disabled=true;const originalText=submit.textContent;try{for(let index=0;index<files.length;index++){submit.textContent='افزودن '+fa(index+1)+' از '+fa(files.length)+' به صف…';const payload=new FormData(translationForm);payload.delete('book');payload.append('book',files[index],files[index].name);const response=await fetch('/api/jobs',{method:'POST',body:payload}),data=await response.json();if(!response.ok)throw Error(data.error||'افزودن کتاب به صف ناموفق بود');jobId=data.id;if(window.jbtGlossary&&data.book_id)window.jbtGlossary.setBook(data.book_id,data.from_lang,data.to_lang)}bookInput.value='';fileInfo.style.display='none';watch()}catch(error){alert(error.message)}finally{submit.disabled=false;submit.textContent=originalText}},true);
if(location.hash==='#new-translation')composer.open=true;
})();
</script>'''
