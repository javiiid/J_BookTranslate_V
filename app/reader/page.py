"""Standalone reader page kept outside the translation dashboard template."""
from __future__ import annotations
import json

from app.core.fonts import embedded_vazirmatn_font_faces


def reader_page(job_id: str) -> str:
    encoded = json.dumps(job_id)
    font_faces = embedded_vazirmatn_font_faces()
    return f'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مطالعهٔ کتاب | J Book Translate</title>{font_faces}<style>
:root{{--app:#f4f7fb;--surface:#fff;--text:#142033;--muted:#6d7a90;--accent:#356df6;--accent-soft:#356df614;--line:#e3e9f2;--shadow:0 18px 50px rgba(38,57,93,.10);--font-size:18px;--line-height:1.9;--reading-width:760px;--radius:20px}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth}}
body{{margin:0;min-height:100vh;background:radial-gradient(circle at 8% 0,#e9f0ff 0,transparent 30%),radial-gradient(circle at 96% 8%,#f2edff 0,transparent 26%),var(--app);color:var(--text);font:15px Vazirmatn,Segoe UI,Tahoma,sans-serif;transition:background .25s,color .25s}}
body.study-night{{--app:#17191d;--surface:#22252b;--text:#d8d2c8;--muted:#aaa69f;--accent:#c9ad74;--accent-soft:#c9ad7420;--line:#343941;--shadow:0 16px 45px rgba(0,0,0,.28);background:radial-gradient(circle at 0 0,#252d3c,transparent 35%),var(--app)}}
button,select{{font:inherit;border:1px solid var(--line);background:var(--surface);color:var(--text);border-radius:10px;padding:9px 12px;cursor:pointer;transition:.15s}}
button:hover:not(:disabled),select:hover{{border-color:var(--accent)}}
button:disabled{{cursor:not-allowed}}
button:focus-visible,select:focus-visible,a:focus-visible{{outline:3px solid var(--accent);outline-offset:2px}}
.bar{{position:sticky;top:0;z-index:5;display:flex;gap:14px;align-items:center;justify-content:space-between;padding:12px max(18px,calc((100vw - var(--reading-width))/2));background:color-mix(in srgb,var(--surface) 88%,transparent);backdrop-filter:blur(10px);border-bottom:1px solid var(--line)}}
.bar-left{{display:flex;align-items:center;gap:12px;min-width:0}}
.brand{{display:flex;align-items:center;gap:8px;text-decoration:none;color:var(--text);flex-shrink:0}}
.brand .mark{{width:30px;height:30px;border-radius:9px;display:grid;place-items:center;background:linear-gradient(140deg,var(--accent),#7257e8);color:#fff;font-size:15px;box-shadow:0 6px 16px rgba(53,109,246,.3)}}
body.study-night .brand .mark{{background:linear-gradient(140deg,var(--accent),#8a6b3a);box-shadow:none}}
.brand-text{{font-size:12px;font-weight:700;color:var(--muted);white-space:nowrap}}
.toc-toggle{{display:flex;align-items:center;gap:6px;font-size:12px;font-weight:700;padding:8px 12px;flex-shrink:0}}
.toc-toggle-icon{{font-size:14px;line-height:1}}
.bar strong{{font-size:13px;font-weight:700;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding-inline-start:12px;border-inline-start:1px solid var(--line)}}
.controls{{display:flex;gap:7px;align-items:center;flex-wrap:wrap}}
.controls button,.controls select{{font-size:12px;font-weight:600}}
#night{{color:var(--accent);border-color:var(--accent-soft);background:var(--accent-soft)}}
#night[aria-pressed=true]{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.toc-backdrop{{display:none;position:fixed;inset:0;background:rgba(20,32,51,.4);z-index:6}}
.layout{{max-width:1180px;margin:0 auto;display:grid;grid-template-columns:230px minmax(0,1fr);gap:30px;padding:32px 18px 80px}}
.toc{{position:sticky;top:78px;align-self:start;max-height:calc(100vh - 108px);overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:16px;padding:10px;box-shadow:0 8px 24px rgba(38,57,93,.04);transition:width .2s ease,opacity .2s ease,padding .2s ease}}
.toc:not(:empty):before{{content:'فهرست فصل‌ها';display:block;font-size:11px;font-weight:700;color:var(--muted);letter-spacing:.02em;padding:6px 12px 10px}}
.toc button{{display:flex;align-items:center;gap:9px;width:100%;text-align:right;border:0;background:transparent;padding:10px 12px;color:var(--muted);border-radius:10px;font-size:13px;margin-bottom:2px}}
.toc-num{{flex:none;min-width:20px;font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}}
.toc-title{{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.toc-status{{flex:none;width:16px;height:16px;border-radius:50%;display:grid;place-items:center;font-size:9px;color:#fff;background:var(--line)}}
.toc button.read .toc-status:after{{content:'✓'}}
.toc button.read .toc-status{{background:var(--accent)}}
.toc button:hover{{background:var(--accent-soft);color:var(--text)}}
.toc button.active{{color:var(--accent);font-weight:700;background:var(--accent-soft)}}
.toc button.active .toc-num{{color:var(--accent)}}
body.toc-collapsed .toc{{width:0;min-width:0;padding:0;border:0;opacity:0;overflow:hidden;pointer-events:none}}
body.toc-collapsed .layout{{grid-template-columns:0 minmax(0,1fr);gap:0}}
.book{{position:relative;overflow:hidden;width:min(100%,var(--reading-width));justify-self:center;background:var(--surface);padding:clamp(28px,6vw,64px);border-radius:var(--radius);min-height:70vh;box-shadow:var(--shadow);border:1px solid var(--line)}}
.book:before{{content:'';position:absolute;inset:0 0 auto 0;height:4px;background:linear-gradient(90deg,var(--accent),#7257e8)}}
body.study-night .book:before{{background:linear-gradient(90deg,var(--accent),#8a6b3a)}}
.book h1{{font-size:1.6em;line-height:1.55;margin:0 0 1.6em;font-weight:800;letter-spacing:-.2px}}
.content{{font-size:var(--font-size);line-height:var(--line-height)}}
.content p,.content div{{margin:0 0 1.15em}}
.content blockquote{{margin:1.4em 0;padding:.2em 1.1em;border-inline-start:3px solid var(--accent);color:var(--muted);background:var(--accent-soft);border-radius:0 10px 10px 0}}
.content a{{color:var(--accent)}}
.content img{{max-width:100%;height:auto;border-radius:10px}}
.parallel-list{{display:grid;gap:18px}}
.parallel-block{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;padding:18px;border:1px solid var(--line);border-radius:14px;background:color-mix(in srgb,var(--surface) 94%,var(--accent-soft))}}
.parallel-side{{min-width:0}}
.parallel-side+.parallel-side{{border-inline-start:1px solid var(--line);padding-inline-start:18px}}
.parallel-label{{display:block;margin-bottom:8px;color:var(--muted);font-size:11px;font-weight:700}}
.status{{color:var(--muted);font-size:12px;margin:0 0 14px}}
.status:empty{{display:none}}
.chapter-nav{{display:flex;align-items:center;justify-content:space-between;gap:10px;margin:0 0 22px}}
.chapter-nav-bottom{{margin:34px 0 0;padding-top:22px;border-top:1px solid var(--line)}}
.chapter-nav button{{font-size:12px;font-weight:700;padding:9px 14px;color:var(--accent);border-color:var(--accent-soft);background:var(--accent-soft)}}
.chapter-nav button:disabled{{opacity:.4;color:var(--muted);background:transparent;border-color:var(--line)}}
.chapter-position{{font-size:12px;color:var(--muted);white-space:nowrap}}
@media(max-width:760px){{
.layout{{display:block;padding:18px 12px}}
.book{{padding:26px 20px;border-radius:14px}}
.bar{{padding:10px 12px}}
.brand-text{{display:none}}
.toc-toggle-label{{display:none}}
.bar strong{{border-inline-start:0;padding-inline-start:0}}
.toc{{position:fixed;top:0;bottom:0;right:0;left:auto;width:min(82vw,320px);max-height:none;border-radius:18px 0 0 18px;margin:0;transform:translateX(100%);transition:transform .25s ease;z-index:7;box-shadow:-16px 0 40px rgba(20,32,51,.18)}}
.parallel-block{{grid-template-columns:1fr}}
.parallel-side+.parallel-side{{border-inline-start:0;border-top:1px solid var(--line);padding-inline-start:0;padding-top:16px}}
body.toc-open .toc{{transform:translateX(0)}}
body.toc-open .toc-backdrop{{display:block}}
}}
@media(prefers-reduced-motion:reduce){{html{{scroll-behavior:auto}}*{{transition:none!important}}}}
</style></head><body><header class="bar"><div class="bar-left"><a class="brand" href="/" aria-label="بازگشت به میز کار"><span class="mark">文</span><span class="brand-text">J Book Translate</span></a><button id="toc-toggle" class="toc-toggle" type="button" aria-expanded="true" aria-controls="toc"><span class="toc-toggle-icon">☰</span><span class="toc-toggle-label">فهرست</span></button><strong id="title">در حال بازکردن کتاب…</strong></div><div class="controls"><button id="night" aria-pressed="false">حالت شب مطالعه</button><select id="mode" aria-label="نوع نمایش"><option value="translation">ترجمه</option><option value="bilingual">دوزبانه</option><option value="original">متن اصلی</option></select><select id="font" aria-label="اندازهٔ متن"><option value="16">متن کوچک</option><option value="18">متن معمولی</option><option value="20">متن بزرگ</option><option value="22">متن خیلی بزرگ</option></select><select id="leading" aria-label="فاصلهٔ خطوط"><option value="1.7">فشرده</option><option value="1.9">راحت</option><option value="2.1">باز</option></select><select id="width" aria-label="عرض متن"><option value="640">باریک</option><option value="760">استاندارد</option><option value="880">عریض</option></select><select id="direction" aria-label="جهت متن"><option value="auto">خودکار</option><option value="rtl">راست‌به‌چپ</option><option value="ltr">چپ‌به‌راست</option></select><button id="reset">بازنشانی</button></div></header><div class="toc-backdrop" id="toc-backdrop"></div><main class="layout"><nav class="toc" id="toc" aria-label="فهرست فصل‌ها"></nav><article class="book"><div class="chapter-nav chapter-nav-top"><button type="button" data-action="prev">‹ فصل قبلی</button><span class="chapter-position" data-role="position"></span><button type="button" data-action="next">فصل بعدی ›</button></div><p class="status" id="status"></p><h1 id="chapter-title"></h1><section class="content" id="content"></section><div class="chapter-nav chapter-nav-bottom"><button type="button" data-action="prev">‹ فصل قبلی</button><span class="chapter-position" data-role="position"></span><button type="button" data-action="next">فصل بعدی ›</button></div></article></main><script>
const jobId={encoded},$=s=>document.querySelector(s),$$=s=>document.querySelectorAll(s);
const defaults={{study_night_mode:false,reading_mode:'translation',reading_font_size:18,reading_line_height:1.9,reading_width:760,reading_direction:'auto'}},settings={{...defaults}};
let chapters=[],currentId=null;
const faNum=n=>new Intl.NumberFormat('fa-IR').format(n);
const escHtml=s=>String(s).replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}})[c]);
const readKey=()=>'jbook-read:'+jobId;
function loadRead(){{try{{return new Set(JSON.parse(localStorage.getItem(readKey())||'[]'))}}catch{{return new Set()}}}}
let readSet=loadRead();
function saveRead(){{try{{localStorage.setItem(readKey(),JSON.stringify([...readSet]))}}catch{{}}}}
function apply(){{document.body.classList.toggle('study-night',!!settings.study_night_mode);document.documentElement.style.setProperty('--font-size',settings.reading_font_size+'px');document.documentElement.style.setProperty('--line-height',settings.reading_line_height);document.documentElement.style.setProperty('--reading-width',settings.reading_width+'px');$('#night').setAttribute('aria-pressed',!!settings.study_night_mode);$('#mode').value=settings.reading_mode;$('#font').value=settings.reading_font_size;$('#leading').value=settings.reading_line_height;$('#width').value=settings.reading_width;$('#direction').value=settings.reading_direction}}
async function save(extra={{}}){{Object.assign(settings,extra);apply();await fetch('/api/reader/settings',{{method:'PUT',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(settings)}})}}
function directionFor(html){{if(settings.reading_direction!=='auto')return settings.reading_direction;return /[\u0600-\u06FF]/.test(html)?'rtl':'ltr'}}
function closeTocIfMobile(){{if(window.matchMedia('(max-width:760px)').matches){{document.body.classList.remove('toc-open');document.body.classList.remove('toc-collapsed')}}}}
function renderToc(){{$('#toc').innerHTML=chapters.map((x,i)=>`<button type="button" data-id="${{x.id}}" class="${{x.id===currentId?'active':''}} ${{readSet.has(x.id)?'read':'unread'}}" aria-current="${{x.id===currentId?'true':'false'}}"><span class="toc-num">${{faNum(i+1)}}</span><span class="toc-title">${{escHtml(x.title)}}</span><span class="toc-status" aria-hidden="true"></span></button>`).join('');$$('.toc button').forEach(b=>b.onclick=()=>{{loadChapter(Number(b.dataset.id));closeTocIfMobile()}})}}
function updateNav(){{const disablePrev=currentId===null||currentId<=0,disableNext=currentId===null||currentId>=chapters.length-1;$$('[data-action="prev"]').forEach(b=>b.disabled=disablePrev);$$('[data-action="next"]').forEach(b=>b.disabled=disableNext);$$('[data-role="position"]').forEach(el=>el.textContent=currentId===null||!chapters.length?'':`فصل ${{faNum(currentId+1)}} از ${{faNum(chapters.length)}}`)}}
function renderBlocks(blocks,mode){{const visible=blocks.filter(x=>mode==='original'||x.translation_html);if(!visible.length)return '';return `<div class="parallel-list">${{visible.map(x=>{{if(mode==='original')return `<div class="parallel-block"><div class="parallel-side" dir="auto">${{x.original_html}}</div></div>`;return `<div class="parallel-block"><div class="parallel-side" dir="auto"><span class="parallel-label">متن اصلی</span>${{x.original_html}}</div><div class="parallel-side" dir="auto"><span class="parallel-label">ترجمه</span>${{x.translation_html}}</div></div>`}}).join('')}}</div>`}}
async function loadChapter(id){{try{{const r=await fetch(`/api/reader/${{jobId}}/chapters/${{id}}`);if(!r.ok)throw Error();const d=await r.json();$('#chapter-title').textContent=d.title;const content=$('#content');let html=d.html;if(settings.reading_mode!=='translation'){{const blocksResponse=await fetch(`/api/reader/${{jobId}}/chapters/${{id}}/blocks`);if(blocksResponse.ok){{const blockData=await blocksResponse.json();html=renderBlocks(blockData.items||[],settings.reading_mode)||d.html}}}}content.innerHTML=html;content.dir=settings.reading_mode==='bilingual'?'auto':directionFor(html);content.style.textAlign=content.dir==='rtl'?'right':'start';currentId=id;readSet.add(id);saveRead();renderToc();updateNav();$('#status').textContent='';$('.book').scrollIntoView({{behavior:'smooth',block:'start'}});await save({{reading_last_location:{{job_id:jobId,chapter:id}}}})}}catch{{$('#status').textContent='خواندن این فصل ممکن نشد.'}}}}
async function init(){{const [s,c]=await Promise.all([fetch('/api/reader/settings'),fetch(`/api/reader/${{jobId}}/chapters`)]);const sd=await s.json(),cd=await c.json();Object.assign(settings,sd.value||{{}});chapters=cd.items||[];apply();$('#title').textContent=cd.book||'کتاب ترجمه‌شده';renderToc();updateNav();const saved=settings.reading_last_location;if(chapters.length)loadChapter(saved&&saved.job_id===jobId?Math.min(saved.chapter,chapters.length-1):0)}}
$('#night').onclick=()=>save({{study_night_mode:!settings.study_night_mode}});
$('#mode').onchange=async e=>{{await save({{reading_mode:e.target.value}});if(currentId!==null)loadChapter(currentId)}};
$('#font').onchange=e=>save({{reading_font_size:Number(e.target.value)}});
$('#leading').onchange=e=>save({{reading_line_height:Number(e.target.value)}});
$('#width').onchange=e=>save({{reading_width:Number(e.target.value)}});
$('#direction').onchange=e=>save({{reading_direction:e.target.value}});
$('#reset').onclick=()=>save({{...defaults}});
$('#toc-toggle').onclick=()=>{{document.body.classList.toggle('toc-collapsed');document.body.classList.toggle('toc-open')}};
$('#toc-backdrop').onclick=()=>closeTocIfMobile();
document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeTocIfMobile()}});
document.addEventListener('click',e=>{{const btn=e.target.closest('[data-action]');if(!btn||btn.disabled)return;if(currentId===null)return;const next=currentId+(btn.dataset.action==='prev'?-1:1);if(next<0||next>=chapters.length)return;loadChapter(next);closeTocIfMobile()}});
init();
</script></body></html>'''
