"""Standalone reader page kept outside the translation dashboard template.

The page is assembled from plain (non f-string) templates so that the CSS and
JavaScript can use single braces freely. Two placeholders are substituted:
``__FONTS__`` for the embedded font faces and ``__JOB_ID__`` for the job id.
"""
from __future__ import annotations
import json

from app.core.fonts import embedded_vazirmatn_font_faces


_READER_TEMPLATE = r"""<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light dark"><title>مطالعهٔ کتاب | KALIMA</title>__FONTS__<style>
:root{--app:#eef2f8;--surface:#fff;--surface-2:#f7f9fc;--text:#16202e;--muted:#69788e;--accent:#356df6;--accent-2:#7257e8;--accent-soft:#356df614;--line:#e2e8f1;--shadow:0 20px 50px rgba(30,48,80,.10);--font-size:18px;--line-height:1.9;--reading-width:760px;--radius:22px}
body.theme-night{--app:#14161a;--surface:#1e2126;--surface-2:#24272d;--text:#ddd8ce;--muted:#9b978f;--accent:#c9ad74;--accent-2:#b08d55;--accent-soft:#c9ad7420;--line:#33383f;--shadow:0 16px 44px rgba(0,0,0,.35)}
body.theme-sepia{--app:#efe3cd;--surface:#fbf4e4;--surface-2:#f5ead4;--text:#41341f;--muted:#8b785a;--accent:#a8763e;--accent-2:#8f5f2c;--accent-soft:#a8763e1f;--line:#e6d8bd;--shadow:0 18px 46px rgba(90,64,30,.12)}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;min-height:100vh;color:var(--text);background:radial-gradient(circle at 8% 0,#e8efff 0,transparent 32%),radial-gradient(circle at 96% 6%,#f1ecff 0,transparent 28%),var(--app);font:15px Vazirmatn,"Segoe UI",Tahoma,sans-serif;-webkit-font-smoothing:antialiased;transition:background .25s,color .25s}
body.theme-night{background:radial-gradient(circle at 0 0,#232b3a 0,transparent 38%),var(--app)}
body.theme-sepia{background:radial-gradient(circle at 100% 0,#f3e6cd 0,transparent 36%),var(--app)}
button,select,input{font:inherit}
button,select{cursor:pointer;transition:background .15s,border-color .15s,color .15s}
button:focus-visible,select:focus-visible,input:focus-visible,a:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
button:disabled{cursor:not-allowed}

.progress{position:fixed;top:0;left:0;right:0;height:3px;z-index:120;background:var(--line)}
.progress>i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--accent-2));transition:width .35s ease}

.bar{position:sticky;top:3px;z-index:90;display:flex;align-items:center;justify-content:space-between;gap:12px;padding:9px clamp(12px,4vw,24px);background:var(--surface);border-bottom:1px solid var(--line);transition:transform .28s ease}
@supports(backdrop-filter:blur(2px)){.bar{background:color-mix(in srgb,var(--surface) 86%,transparent);backdrop-filter:blur(14px)}}
body.bar-hidden .bar{transform:translateY(-115%)}
.bar-start{display:flex;align-items:center;gap:10px;min-width:0}
.bar-end{display:flex;align-items:center;gap:4px}
.book{display:flex;flex-direction:column;min-width:0;line-height:1.35}
.book-title{font-size:13px;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:38vw}
.book-sub{font-size:11px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:38vw}
.icon-btn{display:grid;place-items:center;width:38px;height:38px;border:0;border-radius:11px;background:transparent;color:var(--muted);font-size:17px}
.icon-btn:hover{background:var(--accent-soft);color:var(--accent)}
.icon-btn[aria-pressed=true]{background:var(--accent);color:#fff}
.chip{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--line);background:var(--surface-2);color:var(--muted);border-radius:999px;padding:7px 12px;font-size:12px;white-space:nowrap}
.chip[hidden]{display:none}

.main{padding:26px clamp(14px,4vw,28px) 130px;display:flex;justify-content:center}
.card{position:relative;width:min(100%,calc(var(--reading-width) + 80px));background:var(--surface);border:1px solid var(--line);border-radius:var(--radius);box-shadow:var(--shadow);padding:clamp(24px,5vw,54px) clamp(20px,5vw,54px);overflow:hidden}
.card:before{content:"";position:absolute;inset:0 0 auto;height:4px;background:linear-gradient(90deg,var(--accent),var(--accent-2))}
.eyebrow{font-size:12px;font-weight:800;letter-spacing:.06em;color:var(--accent);margin-bottom:6px}
.eyebrow:empty{display:none}
.card h1{font-size:clamp(1.3rem,2.6vw,1.7rem);line-height:1.55;margin:0 0 1.1em;font-weight:800;letter-spacing:-.2px}
.status{display:flex;align-items:center;gap:10px;flex-wrap:wrap;color:var(--muted);font-size:14px;margin:0 0 1em}
.status:empty{display:none}
.status button{padding:7px 12px;border:1px solid var(--line);border-radius:10px;background:var(--surface-2);color:var(--accent);font-weight:700}
.content{font-size:var(--font-size);line-height:var(--line-height);text-align:justify;word-break:break-word}
.content p,.content div{margin:0 0 1.1em}
.content h1,.content h2,.content h3,.content h4{text-align:start;line-height:1.5}
.content img{max-width:100%;height:auto;border-radius:12px;display:block;margin:1.2em auto;background:var(--surface-2);box-shadow:0 2px 10px rgba(30,48,80,.06)}
.content figure{margin:1.4em 0;text-align:center}
.content figcaption{font-size:.82em;color:var(--muted);margin-top:.6em;text-align:center}
.content picture{display:block}
.img-missing{display:flex;align-items:center;justify-content:center;gap:10px;flex-direction:column;min-height:96px;margin:1.2em 0;padding:18px;border:1px dashed var(--line);border-radius:12px;background:var(--surface-2);color:var(--muted);font-size:.85em;text-align:center}
.img-missing-text{opacity:.85}
.content a{color:var(--accent)}
.content blockquote{margin:1.3em 0;padding:.3em 1.1em;border-inline-start:3px solid var(--accent);background:var(--accent-soft);border-radius:0 12px 12px 0;color:var(--muted);text-align:start}
.content table{width:100%;border-collapse:collapse}
.content td,.content th{border:1px solid var(--line);padding:8px 10px}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.fade-in{animation:fadeIn .38s ease}

.chapter-nav{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-top:30px;padding-top:20px;border-top:1px solid var(--line)}
.chapter-nav button{font-weight:700;font-size:13px;padding:10px 16px;color:var(--accent);background:var(--accent-soft);border:1px solid transparent;border-radius:11px}
.chapter-nav button:disabled{opacity:.45;background:transparent;color:var(--muted);border-color:var(--line)}
.nav-pos{color:var(--muted);font-size:13px;white-space:nowrap}

.dock{position:fixed;bottom:18px;left:50%;transform:translateX(-50%);z-index:60;display:flex;align-items:center;gap:6px;padding:6px;border:1px solid var(--line);border-radius:999px;background:var(--surface);box-shadow:var(--shadow)}
.dock-btn{display:grid;place-items:center;width:40px;height:40px;border:0;border-radius:50%;background:transparent;color:var(--accent);font-size:20px;line-height:1}
.dock-btn:hover:not(:disabled){background:var(--accent-soft)}
.dock-btn:disabled{opacity:.35;color:var(--muted)}
.dock-pos{border:0;background:transparent;color:var(--muted);font-size:12px;font-weight:700;padding:0 10px;white-space:nowrap}

.backdrop{position:fixed;inset:0;z-index:95;background:rgba(12,20,34,.45);opacity:0;pointer-events:none;transition:opacity .25s}
.backdrop.show{opacity:1;pointer-events:auto}

.toc{position:fixed;top:0;right:0;bottom:0;z-index:100;width:min(88vw,340px);display:flex;flex-direction:column;background:var(--surface);box-shadow:-18px 0 50px rgba(10,20,40,.22);transform:translateX(105%);transition:transform .28s ease}
.toc.open{transform:translateX(0)}
.toc-head{display:flex;align-items:center;justify-content:space-between;padding:18px 18px 12px}
.toc-title{font-weight:800;font-size:15px}
.toc-search{padding:0 14px 12px}
.toc-search input{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:12px;background:var(--surface-2);color:var(--text)}
.toc-list{flex:1;overflow-y:auto;padding:0 10px 18px}
.toc-item{display:flex;align-items:center;gap:10px;width:100%;text-align:start;border:0;background:transparent;color:var(--muted);padding:11px 12px;border-radius:12px;font-size:13px;line-height:1.6}
.toc-item:hover{background:var(--accent-soft);color:var(--text)}
.toc-item.active{background:var(--accent-soft);color:var(--accent);font-weight:800}
.toc-num{flex:none;min-width:22px;font-size:11px;font-variant-numeric:tabular-nums;color:var(--muted)}
.toc-label{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.toc-mark{flex:none;display:grid;place-items:center;width:16px;height:16px;border-radius:50%;background:var(--line);color:var(--surface);font-size:10px}
.toc-item.read .toc-mark{background:var(--accent)}
.toc-item.read .toc-mark:after{content:"✓"}
.toc-empty{color:var(--muted);font-size:13px;text-align:center;padding:20px}

.sheet{position:fixed;left:0;right:0;bottom:0;z-index:100;transform:translateY(102%);transition:transform .3s ease}
.sheet.open{transform:translateY(0)}
.sheet-inner{max-width:720px;margin:0 auto;background:var(--surface);border:1px solid var(--line);border-bottom:0;border-radius:22px 22px 0 0;box-shadow:0 -14px 50px rgba(10,20,40,.22);padding:10px clamp(16px,4vw,26px) 26px}
.sheet-grip{width:42px;height:4px;border-radius:3px;background:var(--line);margin:6px auto 14px}
.sheet-head{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px}
.sheet-head span{font-weight:800;font-size:15px}
.field{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:14px}
.field-label{color:var(--muted);font-size:13px;font-weight:600}
.field select{min-width:150px;padding:9px 12px;border:1px solid var(--line);border-radius:11px;background:var(--surface-2);color:var(--text)}
.field-grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.field-grid .field{flex-direction:column;align-items:stretch;gap:6px}
.field-grid select{width:100%;min-width:0}
.segmented{display:inline-flex;gap:4px;padding:4px;border:1px solid var(--line);border-radius:12px;background:var(--surface-2)}
.segmented button{border:0;background:transparent;color:var(--muted);padding:7px 16px;border-radius:9px;font-size:13px;font-weight:700}
.segmented button.active{background:var(--accent);color:#fff}
.sheet-actions{display:flex;gap:10px;margin-top:18px}
.sheet-actions button{flex:1;padding:11px;font-weight:700;border:1px solid var(--line);border-radius:11px;background:var(--surface-2);color:var(--text)}
.hint{color:var(--muted);font-size:12px;line-height:1.8;margin:14px 0 0}

.toast{position:fixed;bottom:78px;left:50%;transform:translateX(-50%) translateY(16px);z-index:130;background:var(--text);color:var(--surface);padding:10px 18px;border-radius:12px;font-size:13px;opacity:0;pointer-events:none;transition:opacity .25s,transform .25s;box-shadow:0 10px 30px rgba(0,0,0,.25)}
.toast.show{opacity:1;transform:translateX(-50%) translateY(0)}

@media(max-width:760px){
.book-title,.book-sub{max-width:44vw}
#time-chip{display:none}
.field{flex-direction:column;align-items:stretch}
.field select{width:100%}
.dock{bottom:12px}
.toast{bottom:70px}
.chapter-nav button{font-size:12px;padding:9px 12px}
}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{transition:none!important;animation:none!important}}
</style></head><body>
<div class="progress" role="progressbar" aria-label="پیشرفت مطالعه" aria-valuemin="0" aria-valuemax="100" aria-valuenow="0"><i id="progress-fill"></i></div>
<header class="bar" id="bar">
<div class="bar-start">
<a class="icon-btn" href="/" aria-label="بازگشت به کارگاه" title="بازگشت">↩</a>
<div class="book"><span class="book-title" id="book-title">در حال بازکردن کتاب…</span><span class="book-sub" id="chapter-badge"></span></div>
</div>
<div class="bar-end">
<span class="chip" id="time-chip" hidden></span>
<button type="button" class="icon-btn" id="toc-btn" aria-label="فهرست فصل‌ها" aria-expanded="false" title="فهرست (T)">☰</button>
<button type="button" class="icon-btn" id="columns-btn" aria-label="دو ستون هماهنگ" aria-pressed="false" title="دو ستون هماهنگ (C)">▤</button>
<button type="button" class="icon-btn" id="settings-btn" aria-label="تنظیمات مطالعه" aria-expanded="false" title="تنظیمات (S)">⚙</button>
<button type="button" class="icon-btn" id="night-btn" aria-label="حالت شب" aria-pressed="false" title="شب/روز (N)">🌙</button>
</div>
</header>
<main class="main">
<article class="card">
<div class="eyebrow" id="chapter-eyebrow"></div>
<h1 id="chapter-title"></h1>
<p class="status" id="status" role="status"></p>
<section class="content" id="content" dir="rtl"></section>
<nav class="chapter-nav" aria-label="ناوبری فصل">
<button type="button" data-nav="prev">‹ فصل قبلی</button>
<span class="nav-pos" data-role="position"></span>
<button type="button" data-nav="next">فصل بعدی ›</button>
</nav>
</article>
</main>
<div class="dock" id="dock" role="group" aria-label="ناوبری سریع">
<button type="button" class="dock-btn" data-nav="prev" aria-label="فصل قبلی">‹</button>
<button type="button" class="dock-pos" id="dock-pos" aria-label="بازگشت به بالای فصل">—</button>
<button type="button" class="dock-btn" data-nav="next" aria-label="فصل بعدی">›</button>
</div>
<aside class="toc" id="toc" aria-label="فهرست فصل‌ها" aria-hidden="true">
<div class="toc-head"><span class="toc-title">فهرست فصل‌ها</span><button type="button" class="icon-btn" id="toc-close" aria-label="بستن فهرست">✕</button></div>
<div class="toc-search"><input id="toc-search" type="search" placeholder="جستجوی فصل…" aria-label="جستجوی فصل"></div>
<div class="toc-list" id="toc-list"></div>
</aside>
<div class="backdrop" id="toc-backdrop"></div>
<div class="sheet" id="settings-sheet" role="dialog" aria-modal="true" aria-label="تنظیمات مطالعه" aria-hidden="true">
<div class="sheet-inner">
<div class="sheet-grip"></div>
<div class="sheet-head"><span>تنظیمات مطالعه</span><button type="button" class="icon-btn" id="settings-close" aria-label="بستن تنظیمات">✕</button></div>
<div class="field"><span class="field-label">پوسته</span><div class="segmented" role="group" aria-label="پوسته"><button type="button" data-theme="light">روشن</button><button type="button" data-theme="sepia">گرم</button><button type="button" data-theme="night">شب</button></div></div>
<div class="field"><label class="field-label" for="mode">نوع نمایش</label><select id="mode"><option value="translation">فقط ترجمه</option><option value="bilingual">دوزبانه (پشت سر هم)</option><option value="columns">دو ستون هماهنگ</option><option value="original">فقط متن اصلی</option></select></div>
<div class="field-grid">
<div class="field"><label class="field-label" for="font">اندازهٔ متن</label><select id="font"><option value="16">کوچک</option><option value="18">معمولی</option><option value="20">بزرگ</option><option value="22">خیلی بزرگ</option></select></div>
<div class="field"><label class="field-label" for="leading">فاصلهٔ خطوط</label><select id="leading"><option value="1.7">فشرده</option><option value="1.9">راحت</option><option value="2.1">باز</option></select></div>
<div class="field"><label class="field-label" for="width">عرض متن</label><select id="width"><option value="640">باریک</option><option value="760">استاندارد</option><option value="880">عریض</option></select></div>
<div class="field"><label class="field-label" for="direction">جهت متن</label><select id="direction"><option value="auto">خودکار</option><option value="rtl">راست‌به‌چپ</option><option value="ltr">چپ‌به‌راست</option></select></div>
</div>
<div class="sheet-actions"><button type="button" id="reset-btn">بازنشانی تنظیمات</button></div>
<p class="hint">میان‌بر صفحه‌کلید: ←/→ جابه‌جایی فصل • N شب/روز • S تنظیمات • T فهرست • C دو ستون • F تمام‌صفحه • Esc بستن</p>
</div>
</div>
<div class="backdrop" id="sheet-backdrop"></div>
<div class="toast" id="toast" role="status" aria-live="polite"></div>
<script>
const jobId=__JOB_ID__;
const $=(sel,root=document)=>root.querySelector(sel);
const $$=(sel,root=document)=>Array.prototype.slice.call(root.querySelectorAll(sel));
const faNum=n=>new Intl.NumberFormat('fa-IR').format(n);
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

const DEFAULTS={study_night_mode:false,reading_theme:'light',reading_mode:'translation',reading_font_size:18,reading_line_height:1.9,reading_width:760,reading_direction:'auto',reading_last_location:null};
let settings=Object.assign({},DEFAULTS);
let chapters=[];
let currentId=null;
let lastMode='translation';
let bookName='';
let readSet=new Set();
let wordCount=0;
let loadToken=0;
let saveLocTimer=null;
let lastY=0;
let rafPending=false;
let toastTimer=null;

const LOC_KEY='jbook:loc:'+jobId;
const READ_KEY='jbook:read:'+jobId;

function loadRead(){try{return new Set(JSON.parse(localStorage.getItem(READ_KEY)||'[]'))}catch(e){return new Set()}}
function saveRead(){try{localStorage.setItem(READ_KEY,JSON.stringify(Array.from(readSet)))}catch(e){}}
function loadLoc(){try{return JSON.parse(localStorage.getItem(LOC_KEY)||'null')}catch(e){return null}}
function scrollFrac(){const h=document.documentElement.scrollHeight-window.innerHeight;return h>0?Math.min(1,Math.max(0,window.scrollY/h)):0}
function saveLoc(){try{localStorage.setItem(LOC_KEY,JSON.stringify({chapter:currentId,frac:scrollFrac()}))}catch(e){}}

function theme(){return settings.reading_theme||(settings.study_night_mode?'night':'light')}

function apply(){
  const t=theme();
  document.body.classList.toggle('theme-night',t==='night');
  document.body.classList.toggle('theme-sepia',t==='sepia');
  const root=document.documentElement.style;
  root.setProperty('--font-size',(Number(settings.reading_font_size)||18)+'px');
  root.setProperty('--line-height',String(Number(settings.reading_line_height)||1.9));
  root.setProperty('--reading-width',(Number(settings.reading_width)||760)+'px');
  const night=$('#night-btn');
  night.setAttribute('aria-pressed',String(t==='night'));
  night.textContent=t==='night'?'☀':'🌙';
  const cb=$('#columns-btn');
  if(cb)cb.setAttribute('aria-pressed',String(settings.reading_mode==='columns'));
  $('#mode').value=settings.reading_mode;
  $('#font').value=String(settings.reading_font_size);
  $('#leading').value=String(settings.reading_line_height);
  $('#width').value=String(settings.reading_width);
  $('#direction').value=settings.reading_direction;
  $$('[data-theme]').forEach(b=>b.classList.toggle('active',b.dataset.theme===t));
}

async function save(extra){
  Object.assign(settings,extra||{});
  if(extra&&Object.prototype.hasOwnProperty.call(extra,'reading_theme'))settings.study_night_mode=settings.reading_theme==='night';
  apply();
  try{await fetch('/api/reader/settings',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(settings)})}catch(e){}
}

function directionFor(html){if(settings.reading_direction!=='auto')return settings.reading_direction;return /[\u0600-\u06FF]/.test(html)?'rtl':'ltr'}

function updateTime(frac){
  const chip=$('#time-chip');
  if(!wordCount){chip.hidden=true;return}
  const remaining=Math.max(0,wordCount*(1-frac));
  const minutes=remaining/200;
  chip.hidden=false;
  chip.textContent=minutes<0.7?'چند لحظه تا پایان فصل':('⏳ حدود '+faNum(Math.ceil(minutes))+' دقیقه تا پایان فصل');
}

function updateChrome(){
  const total=chapters.length;
  const idx=chapters.findIndex(c=>c.id===currentId);
  const frac=scrollFrac();
  const overall=total?Math.min(1,(Math.max(0,idx)+frac)/total):0;
  const pct=Math.round(overall*100);
  $('#progress-fill').style.width=(overall*100).toFixed(2)+'%';
  $('#progress-fill').parentElement.setAttribute('aria-valuenow',String(pct));
  const pos=total?('فصل '+faNum(idx+1)+' از '+faNum(total)):'';
  $('#chapter-badge').textContent=total?(pos+' • '+faNum(pct)+'٪'):'';
  $$('[data-role="position"]').forEach(el=>{el.textContent=total?(faNum(idx+1)+' / '+faNum(total)):''});
  const dp=$('#dock-pos');
  if(dp)dp.textContent=pos||'—';
  updateTime(frac);
}

function updateNav(){
  const idx=chapters.findIndex(c=>c.id===currentId);
  const prevDisabled=idx<=0;
  const nextDisabled=idx<0||idx>=chapters.length-1;
  $$('[data-nav="prev"]').forEach(b=>{b.disabled=prevDisabled});
  $$('[data-nav="next"]').forEach(b=>{b.disabled=nextDisabled});
}

function renderToc(filter){
  const q=String(filter||'').trim().toLowerCase();
  const list=$('#toc-list');
  const items=chapters.filter(c=>!q||String(c.title).toLowerCase().indexOf(q)!==-1);
  if(!items.length){list.innerHTML='<p class="toc-empty">فصلی پیدا نشد.</p>';return}
  list.innerHTML=items.map(c=>{
    const idx=chapters.indexOf(c);
    const active=c.id===currentId;
    const read=readSet.has(c.id);
    return '<button type="button" class="toc-item'+(active?' active':'')+(read?' read':'')+'" data-id="'+c.id+'" aria-current="'+(active?'true':'false')+'">'+
      '<span class="toc-num">'+faNum(idx+1)+'</span>'+
      '<span class="toc-label">'+esc(c.title)+'</span>'+
      '<span class="toc-mark" aria-hidden="true"></span>'+
    '</button>';
  }).join('');
}

function renderBlocks(blocks,mode){
  const visible=blocks.filter(x=>mode==='original'||x.translation_html);
  if(!visible.length)return '';
  return '<div class="parallel-list">'+visible.map(x=>{
    if(mode==='original')return '<div class="parallel-block"><div class="parallel-side" dir="auto">'+x.original_html+'</div></div>';
    return '<div class="parallel-block"><div class="parallel-side" dir="auto"><span class="side-label">متن اصلی</span>'+x.original_html+'</div><div class="parallel-side" dir="auto"><span class="side-label">ترجمه</span>'+x.translation_html+'</div></div>';
  }).join('')+'</div>';
}

function renderColumns(blocks){
  const visible=blocks.filter(x=>x.translation_html);
  if(!visible.length)return '';
  const original=visible.map(x=>'<div class="col-block" dir="auto">'+x.original_html+'</div>').join('');
  const translation=visible.map(x=>'<div class="col-block" dir="auto">'+x.translation_html+'</div>').join('');
  const source=visible.map(x=>x.original_html).join('');
  const target=visible.map(x=>x.translation_html).join('');
  return '<div class="columns2">'+
    '<div class="cols-toolbar"><span class="cols-note">متن اصلی <b>↔</b> ترجمه</span><button type="button" class="swap-btn" id="cols-swap" aria-label="جابه‌جایی ستون‌ها" title="جابه‌جایی ستون‌ها">⇄</button></div>'+
    '<section class="col col-original" dir="'+directionFor(source)+'"><div class="col-head">متن اصلی</div>'+original+'</section>'+
    '<section class="col col-trans" dir="'+directionFor(target)+'"><div class="col-head">ترجمه</div>'+translation+'</section>'+
  '</div>';
}

function setStatus(msg){const s=$('#status');s.textContent=msg||''}

function showError(id){
  const s=$('#status');
  s.innerHTML='<span>خواندن این فصل ممکن نشد.</span> <button type="button" id="retry-btn">تلاش مجدد</button>';
  const btn=$('#retry-btn');
  if(btn)btn.addEventListener('click',()=>{loadChapter(id)});
}

async function loadChapter(id){
  const token=++loadToken;
  setStatus('');
  $('#chapter-title').textContent='';
  $('#chapter-eyebrow').textContent='';
  try{
    const res=await fetch('/api/reader/'+jobId+'/chapters/'+id);
    if(!res.ok)throw new Error('chapter');
    const data=await res.json();
    if(token!==loadToken)return;
    let html=data.html||'';
    if(settings.reading_mode!=='translation'){
      try{
        const blockRes=await fetch('/api/reader/'+jobId+'/chapters/'+id+'/blocks');
        if(blockRes.ok){
          const blockData=await blockRes.json();
          const items=(blockData&&blockData.items)||[];
          const rendered=settings.reading_mode==='columns'?renderColumns(items):renderBlocks(items,settings.reading_mode);
          if(rendered)html=rendered;
        }
      }catch(e){}
    }
    if(token!==loadToken)return;
    const idx=chapters.findIndex(c=>c.id===id);
    $('#chapter-title').textContent=data.title||'';
    $('#chapter-eyebrow').textContent=idx>=0?('فصل '+faNum(idx+1)):'';
    const content=$('#content');
    content.innerHTML='<div class="fade-in">'+html+'</div>';
    content.setAttribute('dir',(settings.reading_mode==='bilingual'||settings.reading_mode==='columns')?'auto':directionFor(html));
    wordCount=content.textContent.trim().split(/\s+/).filter(Boolean).length;
    currentId=id;
    readSet.add(id);saveRead();
    renderToc($('#toc-search').value);
    updateNav();
    window.scrollTo(0,0);
    requestAnimationFrame(updateChrome);
    saveLoc();
    save({reading_last_location:{job_id:jobId,chapter:id}});
  }catch(err){
    if(token!==loadToken)return;
    showError(id);
  }
}

function go(delta){
  const idx=chapters.findIndex(c=>c.id===currentId);
  const next=idx+delta;
  if(next<0||next>=chapters.length)return;
  loadChapter(chapters[next].id);
}

function setOverlay(panelSel,backSel,open){
  const panel=$(panelSel);
  if(!panel)return;
  panel.classList.toggle('open',open);
  panel.setAttribute('aria-hidden',String(!open));
  const back=$(backSel);
  if(back)back.classList.toggle('show',open);
}
function closeToc(){setOverlay('#toc','#toc-backdrop',false);$('#toc-btn').setAttribute('aria-expanded','false')}
function openToc(){setOverlay('#settings-sheet','#sheet-backdrop',false);setOverlay('#toc','#toc-backdrop',true);$('#toc-btn').setAttribute('aria-expanded','true')}
function toggleToc(){const p=$('#toc');p.classList.contains('open')?closeToc():openToc()}
function closeSettings(){setOverlay('#settings-sheet','#sheet-backdrop',false);$('#settings-btn').setAttribute('aria-expanded','false')}
function openSettings(){setOverlay('#toc','#toc-backdrop',false);setOverlay('#settings-sheet','#sheet-backdrop',true);$('#settings-btn').setAttribute('aria-expanded','true')}
function toggleSettings(){const p=$('#settings-sheet');p.classList.contains('open')?closeSettings():openSettings()}

function toast(msg){
  const t=$('#toast');
  t.textContent=msg;t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer=setTimeout(()=>t.classList.remove('show'),2400);
}

function toggleFullscreen(){
  if(!document.fullscreenElement){document.documentElement.requestFullscreen().catch(()=>{})}
  else{document.exitFullscreen().catch(()=>{})}
}

function onScroll(){
  if(rafPending)return;
  rafPending=true;
  requestAnimationFrame(()=>{
    rafPending=false;
    const y=window.scrollY;
    if(y>lastY+4&&y>140){document.body.classList.add('bar-hidden')}
    else if(y<lastY-4){document.body.classList.remove('bar-hidden')}
    lastY=y;
    updateChrome();
    clearTimeout(saveLocTimer);
    saveLocTimer=setTimeout(saveLoc,500);
  });
}

async function init(){
  readSet=loadRead();
  try{
    const responses=await Promise.all([fetch('/api/reader/settings'),fetch('/api/reader/'+jobId+'/chapters')]);
    const sRes=responses[0],cRes=responses[1];
    if(sRes.ok){const sd=await sRes.json();Object.assign(settings,(sd&&sd.value)||{});if(settings.reading_mode&&settings.reading_mode!=='columns')lastMode=settings.reading_mode}
    if(!cRes.ok)throw new Error('chapters');
    const cd=await cRes.json();
    chapters=(cd&&cd.items)||[];
    bookName=(cd&&cd.book)||'';
  }catch(err){
    $('#book-title').textContent='خطا در بارگذاری کتاب';
    setStatus('ارتباط با کتاب برقرار نشد. اتصال سرور را بررسی کنید.');
    return;
  }
  apply();
  $('#book-title').textContent=bookName||'کتاب ترجمه‌شده';
  if(!chapters.length){
    setStatus('فصلی برای این کتاب پیدا نشد.');
    renderToc('');
    updateChrome();
    return;
  }
  const loc=loadLoc();
  const serverLoc=settings.reading_last_location;
  let start=0;
  let restoreFrac=0;
  if(loc&&Number.isInteger(loc.chapter)&&loc.chapter>=0&&loc.chapter<chapters.length){
    start=loc.chapter;
    restoreFrac=Number(loc.frac)||0;
  }else if(serverLoc&&serverLoc.job_id===jobId&&Number.isInteger(serverLoc.chapter)&&serverLoc.chapter>=0&&serverLoc.chapter<chapters.length){
    start=serverLoc.chapter;
  }
  renderToc('');
  await loadChapter(chapters[start].id);
  if(restoreFrac>0){
    setTimeout(()=>{
      const h=document.documentElement.scrollHeight-window.innerHeight;
      if(h>0)window.scrollTo(0,Math.round(restoreFrac*h));
      updateChrome();
    },150);
  }
}

$('#toc-btn').addEventListener('click',toggleToc);
$('#toc-close').addEventListener('click',closeToc);
$('#toc-backdrop').addEventListener('click',closeToc);
$('#settings-btn').addEventListener('click',toggleSettings);
$('#settings-close').addEventListener('click',closeSettings);
$('#sheet-backdrop').addEventListener('click',closeSettings);
$$('[data-nav]').forEach(b=>b.addEventListener('click',()=>go(b.dataset.nav==='next'?1:-1)));
$('#dock-pos').addEventListener('click',()=>window.scrollTo({top:0,behavior:'smooth'}));
$('#toc-list').addEventListener('click',e=>{
  const item=e.target.closest('.toc-item');
  if(!item)return;
  const id=Number(item.dataset.id);
  closeToc();
  if(id!==currentId)loadChapter(id);
});
$('#night-btn').addEventListener('click',()=>{
  const next=theme()==='night'?'light':'night';
  save({reading_theme:next}).then(()=>toast(next==='night'?'حالت شب روشن شد':'حالت روشن فعال شد'));
});
$$('[data-theme]').forEach(b=>b.addEventListener('click',()=>save({reading_theme:b.dataset.theme})));
function setMode(m){
  settings.reading_mode=m;apply();
  save({reading_mode:m});
  if(currentId!==null)loadChapter(currentId);
}
$('#mode').addEventListener('change',async e=>{
  const v=e.target.value;
  if(v!=='columns')lastMode=v;
  await save({reading_mode:v});
  if(currentId!==null)loadChapter(currentId);
});
$('#columns-btn').addEventListener('click',()=>{
  if(settings.reading_mode==='columns')setMode(lastMode||'translation');
  else{lastMode=settings.reading_mode;setMode('columns')}
});
document.addEventListener('click',e=>{
  const btn=e.target.closest('#cols-swap');
  if(!btn)return;
  const wrap=btn.closest('.columns2');
  const a=wrap&&wrap.querySelector('.col-original');
  const b=wrap&&wrap.querySelector('.col-trans');
  if(a&&b)wrap.insertBefore(b,a);
});
$('#font').addEventListener('change',e=>save({reading_font_size:Number(e.target.value)}));
$('#leading').addEventListener('change',e=>save({reading_line_height:Number(e.target.value)}));
$('#width').addEventListener('change',e=>save({reading_width:Number(e.target.value)}));
$('#direction').addEventListener('change',e=>save({reading_direction:e.target.value}));
$('#reset-btn').addEventListener('click',async()=>{await save(Object.assign({},DEFAULTS));toast('تنظیمات بازنشانی شد')});
window.addEventListener('scroll',onScroll,{passive:true});
window.addEventListener('resize',updateChrome);
document.addEventListener('keydown',e=>{
  const tag=(e.target.tagName||'').toLowerCase();
  if(tag==='input'||tag==='select'||tag==='textarea')return;
  switch(e.key){
    case 'ArrowLeft':e.preventDefault();go(1);break;
    case 'ArrowRight':e.preventDefault();go(-1);break;
    case 'n':case 'N':$('#night-btn').click();break;
    case 's':case 'S':if(!e.ctrlKey&&!e.metaKey){e.preventDefault();toggleSettings()}break;
    case 't':case 'T':if(!e.ctrlKey&&!e.metaKey){e.preventDefault();toggleToc()}break;
    case 'c':case 'C':if(!e.ctrlKey&&!e.metaKey){e.preventDefault();$('#columns-btn').click()}break;
    case 'f':case 'F':toggleFullscreen();break;
    case '?':toggleSettings();break;
    case 'Escape':
      if($('#settings-sheet').classList.contains('open'))closeSettings();
      else if($('#toc').classList.contains('open'))closeToc();
      break;
  }
});
init();
</script></body></html>"""


_FOCUS_STYLE = r"""<style>
.parallel-list{display:flex;flex-direction:column;gap:14px}
.parallel-block{display:grid;gap:14px;padding:14px 16px;border:1px solid var(--line);border-radius:14px;background:var(--surface-2)}
.parallel-block:has(.parallel-side:nth-child(2)){grid-template-columns:1fr 1fr}
.parallel-side{min-width:0}
.parallel-block.sync-ready .parallel-side{max-height:70vh;overflow:auto;overscroll-behavior:contain}
.side-label{display:block;font-size:11px;font-weight:700;color:var(--muted);margin-bottom:6px}
.parallel-block .parallel-side:only-child .side-label{display:none}
.columns2{display:grid;grid-template-columns:1fr 1fr;grid-template-rows:auto minmax(0,1fr);gap:18px;height:clamp(340px,calc(100vh - 300px),860px)}
.columns2 .cols-toolbar{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;gap:10px;margin:0;color:var(--muted);font-size:12px;font-weight:700}
.cols-note b{color:var(--accent);font-weight:700}
.swap-btn{display:grid;place-items:center;width:32px;height:32px;border:1px solid var(--line);border-radius:10px;background:var(--surface-2);color:var(--muted);font-size:16px;line-height:1}
.swap-btn:hover{border-color:var(--accent);color:var(--accent)}
.columns2 .col{position:relative;overflow-y:auto;overscroll-behavior:contain;background:var(--surface-2);border:1px solid var(--line);border-radius:var(--radius);padding:0 22px 22px;scrollbar-width:thin}
.columns2 .col-trans{background:linear-gradient(180deg,color-mix(in srgb,var(--accent-soft) 45%,var(--surface-2)),var(--surface-2) 140px)}
.columns2 .col-head{position:sticky;top:0;z-index:2;display:flex;align-items:center;gap:8px;padding:16px 22px 12px;margin:0 -22px 16px;background:color-mix(in srgb,var(--surface) 92%,transparent);border-bottom:1px solid var(--line);color:var(--muted);font-size:11px;font-weight:700}
.columns2 .col-head:before{content:"";width:8px;height:8px;border-radius:50%;background:var(--accent)}
.columns2 .col-block{margin:0 0 1.1em;font-size:var(--font-size);line-height:var(--line-height)}
@media(max-width:760px){
.parallel-block:has(.parallel-side:nth-child(2)){grid-template-columns:1fr}
.parallel-block.sync-ready .parallel-side{max-height:none;overflow:visible}
.cols-toolbar{display:none}
.columns2{grid-template-columns:1fr;height:auto;gap:14px}
.columns2 .col{overflow:visible;max-height:none;padding:0 18px 18px}
.columns2 .col-head{margin:0 -18px 14px;padding:14px 18px 10px}
}
</style>"""


_FOCUS_SCRIPT = r"""<script>
(function(){
  var sides=[];
  var locking=false;
  var isNarrow=function(){return window.matchMedia('(max-width:760px)').matches};
  var partnerOf=function(el){
    var parent=el.parentElement;
    if(!parent)return null;
    var kids=Array.prototype.slice.call(parent.children);
    return kids.filter(function(c){
      return c!==el&&(c.classList.contains('col')||c.classList.contains('parallel-side'));
    })[0]||null;
  };
  var collect=function(){
    sides=Array.prototype.slice.call(document.querySelectorAll('.columns2 .col'))
      .concat(Array.prototype.slice.call(document.querySelectorAll('.parallel-block .parallel-side')));
    Array.prototype.slice.call(document.querySelectorAll('.parallel-block')).forEach(function(b){b.classList.add('sync-ready')});
  };
  const bind=()=>sides.forEach(el=>{
    if(el.dataset.syncBound)return;
    el.dataset.syncBound='1';
    el.addEventListener('scroll',function(){
      if(locking||isNarrow())return;
      var other=partnerOf(el);
      if(!other)return;
      var max=el.scrollHeight-el.clientHeight;
      var otherMax=other.scrollHeight-other.clientHeight;
      if(max<=0||otherMax<=0)return;
      locking=true;
      other.scrollTop=(el.scrollTop/max)*otherMax;
      requestAnimationFrame(function(){locking=false});
    },{passive:true});
  });
  var refresh=function(){collect();bind()};
  var content=document.getElementById('content');
  if(content)new MutationObserver(refresh).observe(content,{childList:true,subtree:true});
  refresh();
})();
</script>"""


def reader_page(job_id: str) -> str:
    encoded = json.dumps(job_id)
    page = (
        _READER_TEMPLATE
        .replace("__FONTS__", embedded_vazirmatn_font_faces())
        .replace("__JOB_ID__", encoded)
    )
    return page.replace("</head>", _FOCUS_STYLE + "</head>", 1).replace("</body>", _FOCUS_SCRIPT + "</body>", 1)
