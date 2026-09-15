"""Responsive, task-focused dashboard presentation."""

from app.library.view import _embedded_vazirmatn_font_faces


def install_workspace(page):
    page = page.replace("@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap');", '')
    return page.replace('</head>', _embedded_vazirmatn_font_faces() + STYLE + '</head>', 1).replace('</body>', SCRIPT + '</body>', 1)


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
.job-list-item[aria-pressed=true]{border-color:#356df6;background:#356df610}.job-list-title{font-size:13px;font-weight:600;overflow-wrap:anywhere;unicode-bidi:plaintext}.job-list-meta{font-size:12px;font-weight:400;color:var(--muted)}.job-list-track{height:4px;border-radius:8px;background:var(--line);overflow:hidden}.job-list-track>span{display:block;height:100%;background:var(--blue)}
.workspace-detail{min-width:0}.workspace-detail:has(#job[style*="none"])::before{content:'برای دیدن جزئیات، یک کار را انتخاب کن. بعد از شروع ترجمه، پیشرفت اینجا نمایش داده می‌شود.';display:block;padding:54px 28px;border:1px dashed var(--line);border-radius:18px;color:var(--muted);text-align:center}
#job{margin-top:0;padding:28px}#job-name{font-size:20px;line-height:1.7}#job-meta{overflow-wrap:anywhere}.job-actions>*{min-height:44px}.job .stats{gap:12px}.stat{padding:14px;background:var(--bg)!important;border-color:var(--line)!important}.stat strong{color:var(--ink)}.chip{margin:0}.chip.paused{background:#e7a02320;color:#ad7915}
.composer{border:1px solid var(--line);border-radius:16px;background:var(--surface);overflow:hidden}.composer>summary{cursor:pointer;padding:18px 22px;font-size:16px;font-weight:700;color:var(--blue)}.composer>summary small{font-weight:400;color:var(--muted);margin-inline-start:12px;font-size:12px}.composer .form-card{border:0!important;box-shadow:none;padding:0 24px 24px}.composer .section-title{display:none}.composer .drop{min-height:120px}.composer .primary{max-width:360px}#auto-glossary-note{font-size:12px;color:var(--muted)}
body input,body select,body textarea{background:var(--surface)!important;color:var(--ink)!important;border-color:var(--line)!important}input[type=checkbox]{min-height:auto;width:auto}.drop{background:var(--bg)!important}.drop:focus-within{outline:3px solid #356df6}
button:focus-visible,a:focus-visible,summary:focus-visible,input:focus-visible,select:focus-visible{outline:3px solid #7299ff;outline-offset:3px}button:hover:not(:disabled){transform:none}button[hidden],a[hidden]{display:none!important}
@media(max-width:900px){body .shell{padding:20px 18px 40px}.workspace-main{grid-template-columns:1fr}.dashboard-cards{grid-template-columns:repeat(2,1fr)}#jobs-list{max-height:270px!important}.top{flex-wrap:wrap}.workspace-nav strong{width:100%}}
@media(max-width:540px){body .shell{padding:16px 12px 32px}.workspace-nav{gap:2px}.workspace-nav a{padding:8px 12px}.dashboard-card{padding:12px 16px}.brand h1{font-size:22px}.api-pill{border-radius:12px}#job,#active-jobs{padding:18px}.job .stats{grid-template-columns:1fr}.composer>summary small{display:block;margin:4px 0}.composer .form-card{padding:0 16px 20px}.job-head{display:flex;flex-direction:column}.grid2{grid-template-columns:1fr}}
@media(prefers-reduced-motion:reduce){*,*::before,*::after{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
</style>'''


SCRIPT = '''<script>
(()=>{
const shell=document.querySelector('.shell'),dashboard=document.querySelector('.dashboard'),form=document.querySelector('.form-card');
const nav=document.createElement('nav');nav.className='workspace-nav';nav.setAttribute('aria-label','ناوبری اصلی');nav.innerHTML='<strong>J Book Translate</strong><a href="/" aria-current="page">میز کار</a><a href="/library">کتابخانه</a><a href="#active-jobs">کارهای من</a><a href="#new-translation" id="open-composer">＋ ترجمهٔ جدید</a>';shell.prepend(nav);
document.querySelector('.brand h1').textContent='میز کار ترجمه';document.querySelector('.brand p').textContent='کتاب‌هایت را ترجمه کن؛ پیشرفتشان را همین‌جا دنبال کن.';
const main=document.createElement('div');main.className='workspace-main';const detail=document.createElement('div');detail.className='workspace-detail';detail.append(document.getElementById('job'));main.append(document.getElementById('active-jobs'));main.append(detail);
const composer=document.createElement('details');composer.id='new-translation';composer.className='composer';const summary=document.createElement('summary');summary.innerHTML='＋ ترجمهٔ جدید <small>انتخاب کتاب، زبان و تنظیمات ترجمه</small>';composer.append(summary);composer.append(form);
dashboard.append(main);dashboard.append(composer);
document.getElementById('open-composer').onclick=()=>{composer.open=true;composer.scrollIntoView({behavior:'smooth',block:'start'})};
document.querySelector('#job .stat span').textContent='بخش‌های ترجمه‌شده';document.querySelector('#stop').textContent='توقف امن ترجمه';
document.querySelector('#job .logs summary').textContent='جزئیات فنی و گزارش اجرا';
const hint=document.createElement('p');hint.className='small';hint.textContent='با بستن این صفحه ترجمه متوقف نمی‌شود. برای توقف، از دکمهٔ «توقف امن ترجمه» استفاده کن.';document.querySelector('.job-actions').after(hint);
document.querySelectorAll('#translate-form input:not([type=checkbox]),#translate-form select,#translate-form textarea').forEach((input,index)=>{input.id=input.id||'translation-field-'+index;const label=input.previousElementSibling;if(label?.tagName==='LABEL')label.htmlFor=input.id});
if(location.hash==='#new-translation')composer.open=true;
})();
</script>'''
