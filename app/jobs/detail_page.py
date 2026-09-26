"""Deep job monitor: chunks, QA report, timeline, and asset downloads.

Route: ``GET /workspace/job/{job_id}``

The page follows the existing local-app conventions: server-rendered HTML with
Tailwind via CDN, embedded Vazirmatn font faces, RTL-first layout, and the
shared ``jbook-study-dark`` storage key so the theme stays in sync with the
landing page, workspace, library, and reader.
"""
from __future__ import annotations

from app.core.fonts import embedded_vazirmatn_font_faces


def job_detail_page(job_id: str) -> str:
    """Return the HTML for the translation-monitor page of one job."""
    return _TEMPLATE.replace("__FONTS__", embedded_vazirmatn_font_faces()).replace(
        "__JOB_ID__", job_id
    )


_TEMPLATE = r'''<!doctype html>
<html lang="fa" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>پایش ترجمه | J Book Translate</title>
__FONTS__
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config = { darkMode: 'class', theme: { extend: {
  fontFamily: { sans: ['Vazirmatn', 'system-ui', 'sans-serif'] },
  colors: {
    primary: '#356df6', accent: '#08966c', danger: '#e24a4a', warn: '#d98518',
    bg: '#f4f7fb', surface: '#ffffff', ink: '#142033', line: '#e3e9f2'
  },
  boxShadow: { soft: '0 18px 55px rgba(38,57,93,.08)', card: '0 12px 32px rgba(38,57,93,.07)' }
} } };
</script>
<style>
:root{
  --bg:#f4f7fb;--surface:#fff;--surface-2:#f8fafc;--ink:#142033;--muted:#6d7a90;
  --line:#e3e9f2;--blue:#356df6;--purple:#7257e8;--green:#08966c;--amber:#d98518;
  --red:#e24a4a;--shadow:0 18px 55px rgba(38,57,93,.08);
}
body.app-dark{
  --bg:#0e141e;--surface:#18202e;--surface-2:#1e293b;--ink:#f1f5f9;--ink-strong:#fff;
  --muted:#b8c6d6;--line:#243142;--line-strong:#2e4056;--blue:#60a5fa;--purple:#a78bfa;
  --green:#34d399;--amber:#fbbf24;--red:#f87171;--shadow:0 18px 55px rgba(0,0,0,.45);
}
*{box-sizing:border-box}
html{scroll-padding-top:80px}
body{
  margin:0;min-height:100dvh;background:var(--bg);color:var(--ink);
  font:15px/1.75 Vazirmatn,system-ui,sans-serif;
}
.card{background:var(--surface);border:1px solid var(--line);border-radius:20px;box-shadow:var(--shadow)}
:focus-visible{outline:2px solid var(--blue);outline-offset:2px}
.skeleton{background:linear-gradient(90deg,var(--surface-2) 25%,var(--line) 50%,var(--surface-2) 75%);
  background-size:200% 100%;animation:shimmer 1.4s infinite;border-radius:8px}
@keyframes shimmer{to{background-position:-200% 0}}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
/* Tabs */
.tab-btn{position:relative;padding:12px 4px;margin-inline-end:26px;font-size:14px;font-weight:600;
  color:var(--muted);background:none;border:0;cursor:pointer;white-space:nowrap}
.tab-btn::after{content:'';position:absolute;inset-inline:0;bottom:-1px;height:2px;border-radius:2px;
  background:transparent;transition:background 200ms ease}
.tab-btn:hover{color:var(--ink)}
.tab-btn[aria-selected=true]{color:var(--blue)}
.tab-btn[aria-selected=true]::after{background:var(--blue)}
/* Badges */
.badge{display:inline-flex;align-items:center;gap:6px;padding:4px 11px;border-radius:999px;
  font-size:11px;font-weight:700;border:1px solid transparent}
.badge-queued{background:#f1f5f9;color:#64748b;border-color:#e2e8f0}
.badge-running{background:#eff6ff;color:#2563eb;border-color:#bfdbfe}
.badge-stopping{background:#fffbeb;color:#b45309;border-color:#fde68a}
.badge-paused,.badge-stopped{background:#fff7ed;color:#c2410c;border-color:#fed7aa}
.badge-completed{background:#ecfdf5;color:#047857;border-color:#a7f3d0}
.badge-failed{background:#fef2f2;color:#b91c1c;border-color:#fecaca}
.badge-cancelled{background:#f8fafc;color:#64748b;border-color:#e2e8f0}
body.app-dark .badge-queued{background:#1e293b;color:#94a3b8;border-color:#334155}
body.app-dark .badge-running{background:#172a4a;color:#93c5fd;border-color:#1e40af}
body.app-dark .badge-stopping{background:#2e2400;color:#fde68a;border-color:#92400e}
body.app-dark .badge-paused,body.app-dark .badge-stopped{background:#3a2a00;color:#fde68a;border-color:#92400e}
body.app-dark .badge-completed{background:#0f2e22;color:#6ee7b7;border-color:#14532d}
body.app-dark .badge-failed{background:#3a1414;color:#fca5a5;border-color:#7f1d1d}
body.app-dark .badge-cancelled{background:#1e293b;color:#94a3b8;border-color:#334155}
/* Buttons */
.btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;min-height:44px;
  padding:0 20px;border-radius:12px;font-size:14px;font-weight:700;cursor:pointer;
  border:1px solid var(--line);background:var(--surface);color:var(--ink);
  transition:filter 200ms ease,box-shadow 200ms ease;text-decoration:none}
.btn:hover:not(:disabled){filter:brightness(.97)}
.btn:disabled{opacity:.45;cursor:not-allowed}
.btn-primary{background:var(--blue);border-color:var(--blue);color:#fff}
.btn-accent{background:var(--green);border-color:var(--green);color:#fff}
.btn-danger{background:var(--red);border-color:var(--red);color:#fff}
.btn:focus-visible{outline:3px solid #7299ff;outline-offset:3px}
/* Virtualized table */
.vtable-wrap{position:relative;overflow:auto;max-height:520px;border:1px solid var(--line);border-radius:16px;background:var(--surface)}
.vtable{border-collapse:collapse;width:100%;table-layout:fixed;font-size:13px}
.vtable thead th{position:sticky;top:0;z-index:2;background:var(--surface-2);
  padding:12px 14px;text-align:start;font-size:11px;font-weight:700;color:var(--muted);
  border-bottom:1px solid var(--line);white-space:nowrap}
.vtable tbody td{padding:12px 14px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}
.vtable tbody tr:hover{background:var(--surface-2)}
.vtable tbody tr[data-flagged=true]{background:color-mix(in srgb,var(--amber) 9%,transparent)}
.chunk-id{font-family:ui-monospace,monospace;font-size:12px;color:var(--muted)}
.chunk-text{font-size:12.5px;line-height:1.85;max-height:8.5em;overflow:auto}
.flag-pill{display:inline-block;padding:2px 8px;border-radius:6px;font-size:10px;font-weight:800;
  background:color-mix(in srgb,var(--amber) 22%,transparent);color:var(--amber);margin-inline-end:6px}
/* Dialog */
.dialog-overlay{position:fixed;inset:0;z-index:50;display:none;place-items:center;padding:20px;
  background:color-mix(in srgb,#000 55%,transparent);backdrop-filter:blur(4px)}
.dialog-overlay[data-open=true]{display:grid}
.dialog{width:100%;max-width:440px;background:var(--surface);border:1px solid var(--line);
  border-radius:20px;padding:28px;box-shadow:0 24px 60px rgba(0,0,0,.28)}
.dialog h2{margin:0 0 10px;font-size:18px;font-weight:800}
.dialog p{margin:0 0 22px;color:var(--muted);font-size:14px;line-height:1.85}
.dialog-actions{display:flex;gap:10px;justify-content:flex-start}
/* Toast */
.toast{position:fixed;z-index:60;inset-block-end:20px;inset-inline-start:20px;display:none;
  gap:10px;align-items:center;max-width:min(420px,calc(100vw - 40px));padding:14px 18px;
  border-radius:14px;border:1px solid var(--line);background:var(--surface);
  box-shadow:0 16px 40px rgba(0,0,0,.18);font-size:13px;font-weight:600}
.toast[data-show=true]{display:flex}
.toast[data-tone=error]{border-color:var(--red)}
.toast[data-tone=success]{border-color:var(--green)}
/* Timeline */
.timeline{display:grid;gap:2px}
.tl-row{display:grid;grid-template-columns:130px 1fr;gap:14px;padding:11px 0;border-bottom:1px solid var(--line);font-size:12.5px}
.tl-row time{color:var(--muted);white-space:nowrap;font-variant-numeric:tabular-nums}
.tl-row strong{font-weight:700}
.tl-row.error strong{color:var(--red)}
.tl-row.warn strong{color:var(--amber)}
.tl-row.info strong{color:var(--ink)}
/* Assets */
.asset-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(190px,1fr));gap:12px}
.asset{display:grid;gap:8px;padding:16px;border:1px solid var(--line);border-radius:16px;background:var(--surface-2);text-decoration:none;color:inherit}
.asset:hover{border-color:var(--blue);box-shadow:var(--shadow)}
.asset-name{font-size:12px;font-weight:800;letter-spacing:.02em}
.asset-meta{font-size:11px;color:var(--muted)}
/* Quality */
.qa-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}
.qa-item{padding:16px;border:1px solid var(--line);border-radius:16px;background:var(--surface-2)}
.qa-item span{display:block;font-size:11px;color:var(--muted);margin-bottom:6px}
.qa-item strong{font-size:22px;font-weight:800}
.empty{padding:40px 20px;text-align:center;color:var(--muted);font-size:13px}
.log-box{max-height:420px;overflow:auto;padding:16px;border-radius:16px;background:var(--surface-2);
  border:1px solid var(--line);font-family:ui-monospace,monospace;font-size:12px;line-height:1.9;white-space:pre-wrap;overflow-wrap:anywhere}
</style>
</head>
<body class="app-intro">
<header class="sticky top-0 z-40 backdrop-blur" style="background:color-mix(in srgb,var(--surface) 88%,transparent);border-bottom:1px solid var(--line)">
  <div class="mx-auto flex items-center gap-4 px-5 lg:px-8" style="max-width:1240px;height:64px">
    <a href="/workspace" class="btn" style="min-height:38px;padding:0 14px;font-size:13px" aria-label="بازگشت به میز کار">→ میز کار</a>
    <div class="min-w-0 flex-1">
      <strong class="block truncate text-[15px]" id="hdr-name">در حال بارگذاری…</strong>
      <span class="block text-[11px]" style="color:var(--muted)" id="hdr-meta">—</span>
    </div>
    <span id="hdr-status"><span class="badge badge-queued">—</span></span>
    <button type="button" class="btn" id="theme-toggle" style="min-height:38px;padding:0 12px"
      aria-label="تغییر حالت روشن و تاریک" aria-pressed="false">◐</button>
  </div>
</header>

<main class="mx-auto px-5 py-8 lg:px-8" style="max-width:1240px">
  <!-- Progress hero -->
  <section class="card mb-6" style="padding:24px" aria-labelledby="progress-title">
    <div class="flex flex-wrap items-center justify-between gap-4">
      <div class="min-w-0">
        <h1 id="progress-title" class="m-0 text-[20px] font-extrabold">پیشرفت ترجمه</h1>
        <p class="m-0 mt-1 text-[13px]" style="color:var(--muted)" id="progress-label">در حال دریافت اطلاعات…</p>
      </div>
      <div class="flex flex-wrap gap-2">
        <button type="button" class="btn btn-accent" id="act-resume" hidden aria-label="ادامهٔ ترجمه از آخرین جای سالم">ادامهٔ ترجمه</button>
        <button type="button" class="btn btn-primary" id="act-stop" hidden aria-label="توقف امن ترجمه">توقف امن</button>
        <button type="button" class="btn btn-danger" id="act-cancel" hidden aria-label="لغو کامل ترجمه">لغو ترجمه</button>
        <button type="button" class="btn" id="act-rescue" hidden aria-label="ساخت نسخهٔ نجات پروژه">نجات پروژه</button>
      </div>
    </div>
    <div class="mt-5">
      <div class="h-3 w-full overflow-hidden rounded-full" style="background:var(--surface-2)">
        <div id="progress-bar" class="h-full rounded-full" role="progressbar" aria-valuemin="0" aria-valuemax="100"
          aria-valuenow="0" aria-label="درصد پیشرفت ترجمه"
          style="width:0;background:linear-gradient(90deg,var(--blue),var(--purple))"></div>
      </div>
      <div class="mt-2 flex justify-between text-[12px]" style="color:var(--muted)">
        <span id="progress-count">—</span><span id="progress-percent">۰٪</span>
      </div>
    </div>
    <div class="mt-5 grid gap-3" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr))">
      <div class="qa-item"><span>سلامت ترجمه</span><strong id="stat-health">—</strong></div>
      <div class="qa-item"><span>سرعت</span><strong id="stat-speed">—</strong></div>
      <div class="qa-item"><span>زمان باقی‌مانده</span><strong id="stat-eta">—</strong></div>
      <div class="qa-item"><span>حجم فایل</span><strong id="stat-size">—</strong></div>
    </div>
    <div id="job-error" class="mt-4" hidden role="alert" aria-live="assertive"
      style="padding:14px 16px;border-radius:14px;border:1px solid var(--red);background:color-mix(in srgb,var(--red) 8%,transparent);color:var(--red);font-size:13px;font-weight:600"></div>
  </section>

  <!-- Tabs -->
  <section class="card" style="padding:0 24px 24px" aria-labelledby="tabs-title">
    <h2 id="tabs-title" class="sr-only">بخش‌های پایش ترجمه</h2>
    <div class="flex overflow-x-auto border-b" style="border-color:var(--line)" role="tablist" aria-label="بخش‌های پایش job">
      <button type="button" class="tab-btn" role="tab" id="tab-overview" aria-controls="panel-overview" aria-selected="true">نمای کلی</button>
      <button type="button" class="tab-btn" role="tab" id="tab-chunks" aria-controls="panel-chunks" aria-selected="false">بخش‌ها</button>
      <button type="button" class="tab-btn" role="tab" id="tab-qa" aria-controls="panel-qa" aria-selected="false">گزارش کیفیت</button>
      <button type="button" class="tab-btn" role="tab" id="tab-logs" aria-controls="panel-logs" aria-selected="false">رویدادها</button>
      <button type="button" class="tab-btn" role="tab" id="tab-assets" aria-controls="panel-assets" aria-selected="false">خروجی‌ها</button>
    </div>

    <!-- Overview -->
    <div id="panel-overview" role="tabpanel" aria-labelledby="tab-overview" class="pt-6">
      <div class="qa-grid mb-5">
        <div class="qa-item"><span>زبان مبدأ</span><strong id="ov-from">—</strong></div>
        <div class="qa-item"><span>زبان مقصد</span><strong id="ov-to">—</strong></div>
        <div class="qa-item"><span>مدل</span><strong id="ov-model" style="font-size:14px;overflow-wrap:anywhere">—</strong></div>
        <div class="qa-item"><span>حالت</span><strong id="ov-mode">—</strong></div>
        <div class="qa-item"><span>سبک</span><strong id="ov-style">—</strong></div>
        <div class="qa-item"><span>شناسهٔ Job</span><strong id="ov-id" style="font-size:13px;overflow-wrap:anywhere">—</strong></div>
      </div>
      <div class="grid gap-4" style="grid-template-columns:repeat(auto-fit,minmax(240px,1fr))">
        <div>
          <h3 class="m-0 mb-2 text-[14px] font-bold">زمان‌بندی</h3>
          <table class="w-full text-[12.5px]" id="ov-timeline"><tbody>
            <tr><td style="padding:7px 0;color:var(--muted)">ساخت</td><td id="ov-created">—</td></tr>
            <tr><td style="padding:7px 0;color:var(--muted)">شروع</td><td id="ov-started">—</td></tr>
            <tr><td style="padding:7px 0;color:var(--muted)">آخرین فعالیت</td><td id="ov-updated">—</td></tr>
          </tbody></table>
        </div>
        <div>
          <h3 class="m-0 mb-2 text-[14px] font-bold">پیوندهای سریع</h3>
          <div class="flex flex-wrap gap-2">
            <a class="btn" id="ln-download" hidden style="min-height:38px;font-size:13px" aria-label="دانلود خروجی اصلی">دانلود خروجی</a>
            <a class="btn" id="ln-reader" hidden style="min-height:38px;font-size:13px" aria-label="مطالعه در مرورگر">مطالعه در مرورگر</a>
            <a class="btn" href="/library" style="min-height:38px;font-size:13px" aria-label="رفتن به کتابخانه">کتابخانه</a>
          </div>
        </div>
      </div>
    </div>

    <!-- Chunks -->
    <div id="panel-chunks" role="tabpanel" aria-labelledby="tab-chunks" class="pt-6" hidden>
      <div class="mb-4 flex flex-wrap items-center gap-3">
        <input id="chunk-search" type="search" placeholder="جست‌وجو در متن بخش‌ها…"
          class="min-h-[44px] flex-1 rounded-xl border px-4 text-[14px]"
          style="background:var(--surface);color:var(--ink);border-color:var(--line);min-width:200px"
          aria-label="جست‌وجو در متن بخش‌ها">
        <label class="flex items-center gap-2 text-[13px]" style="color:var(--muted)">
          <input type="checkbox" id="chunk-flagged" class="h-4 w-4" style="accent-color:var(--amber)">
          فقط پرچم‌دارها
        </label>
        <select id="chunk-state" class="min-h-[44px] rounded-xl border px-3 text-[13px]"
          style="background:var(--surface);color:var(--ink);border-color:var(--line)" aria-label="فیلتر وضعیت بخش">
          <option value="all">همهٔ وضعیت‌ها</option>
          <option value="done">ترجمه‌شده</option>
          <option value="pending">در انتظار</option>
          <option value="flagged">پرچم‌دار</option>
        </select>
        <span class="text-[12px]" style="color:var(--muted)" id="chunk-count">—</span>
      </div>
      <div class="vtable-wrap" id="vtable-wrap">
        <table class="vtable">
          <colgroup><col style="width:96px"><col style="width:1fr"><col style="width:1fr"><col style="width:110px"></colgroup>
          <thead><tr>
            <th scope="col">شناسه</th><th scope="col">متن مبدأ</th><th scope="col">ترجمه</th><th scope="col">وضعیت</th>
          </tr></thead>
          <tbody id="chunk-body"></tbody>
        </table>
        <div id="chunk-empty" class="empty" hidden>بخشی برای نمایش وجود ندارد.</div>
      </div>
    </div>

    <!-- QA -->
    <div id="panel-qa" role="tabpanel" aria-labelledby="tab-qa" class="pt-6" hidden>
      <div id="qa-scores" class="qa-grid mb-5"></div>
      <div id="qa-body"><p class="empty">گزارش کیفیت هنوز تولید نشده است.</p></div>
    </div>

    <!-- Logs -->
    <div id="panel-logs" role="tabpanel" aria-labelledby="tab-logs" class="pt-6" hidden>
      <div class="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p class="m-0 text-[12.5px]" style="color:var(--muted)">تایم‌لاین رویدادهای ثبت‌شده در پایگاه‌داده و لاگ اجرا.</p>
        <div class="flex gap-2">
          <button type="button" class="btn" id="toggle-raw" style="min-height:36px;font-size:12px" aria-pressed="false" aria-label="نمایش لاگ خام">لاگ خام</button>
          <button type="button" class="btn" id="reload-logs" style="min-height:36px;font-size:12px" aria-label="بارگذاری دوبارهٔ رویدادها">تازه‌سازی</button>
        </div>
      </div>
      <div class="timeline" id="log-timeline"></div>
      <div class="log-box mt-4" id="raw-log" hidden aria-label="لاگ خام اجرا"></div>
    </div>

    <!-- Assets -->
    <div id="panel-assets" role="tabpanel" aria-labelledby="tab-assets" class="pt-6" hidden>
      <div class="asset-grid" id="asset-grid"></div>
      <div class="empty" id="asset-empty">هنوز خروجی‌ای تولید نشده است.</div>
    </div>
  </section>
</main>

<!-- Confirm dialog -->
<div class="dialog-overlay" id="confirm" role="dialog" aria-modal="true" aria-labelledby="confirm-title" data-open="false">
  <div class="dialog">
    <h2 id="confirm-title">تأیید عملیات</h2>
    <p id="confirm-text"></p>
    <div class="dialog-actions">
      <button type="button" class="btn btn-danger" id="confirm-yes" aria-label="تأیید و اجرا">تأیید</button>
      <button type="button" class="btn" id="confirm-no" aria-label="انصراف">انصراف</button>
    </div>
  </div>
</div>

<div class="toast" id="toast" role="status" aria-live="polite" data-show="false"></div>

<script>
(function(){
const JOB_ID = "__JOB_ID__".trim();
const $  = s => document.querySelector(s);
const $$ = s => Array.from(document.querySelectorAll(s));
const fa = n => new Intl.NumberFormat('fa-IR').format(n || 0);
const esc = v => String(v == null ? '' : v).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const bytes = n => !n ? '—' : n >= 1073741824 ? (n/1073741824).toFixed(1)+' GB' : (n/1048576).toFixed(1)+' MB';
const date  = v => { if(!v) return '—'; const d = new Date(v); return isNaN(d) ? '—'
  : d.toLocaleDateString('fa-IR',{year:'numeric',month:'short',day:'numeric'})+' · '
    + d.toLocaleTimeString('fa-IR',{hour:'2-digit',minute:'2-digit'}); };
const duration = s => { if(!s) return '—'; const m = Math.ceil(s/60);
  return m < 60 ? fa(m)+' دقیقه' : fa(Math.floor(m/60))+' ساعت و '+fa(m%60)+' دقیقه'; };

const STATUS_FA = {queued:'در صف',running:'در حال ترجمه',stopping:'در حال توقف',paused:'متوقف‌شده',
  stopped:'متوقف‌شده',completed:'تکمیل‌شده',failed:'خطادار',cancelled:'لغوشده'};
const MODE_FA = {fast:'سریع',batch:'Batch',batchcheck:'Batch + بازبینی',resumebatch:'ادامهٔ Batch',pdfbilingual:'PDF دوزبانه'};
const STYLE_FA = {literary:'ادبی',technical:'فنی',conversational:'محادثه‌ای',formal:'رسمی'};
const ASSET_FA = {main:'فایل اصلی',json_segments:'حافظهٔ ترجمه (JSON)',txt_bilingual:'متن دوزبانه',markdown:'مارک‌داون',
  docx:'ورد (DOCX)',translated_pdf:'PDF ترجمه‌شده',bilingual_pdf:'PDF دوزبانه',translated_epub:'EPUB ترجمه‌شده',
  srt:'زیرنویس (SRT)',quality_report:'گزارش کیفیت',qa_report:'گزارش کیفیت'};
const NOTE_RE = /\{(NOTE|BOUNDARY_WARNING|WARNING)[:\s][^}]*\}/g;
const isFlagged = t => NOTE_RE.test(String(t || ''));
const flaggedNotes = t => { NOTE_RE.lastIndex = 0; return String(t||'').match(NOTE_RE) || []; };

let job = null, chunks = [], busy = false, pending = false, actionBusy = false, selectedTab = 'overview';

/* ---------- theme ---------- */
function applyTheme(){
  const dark = localStorage.getItem('jbook-study-dark') === '1';
  document.body.classList.toggle('app-dark', dark);
  const btn = $('#theme-toggle');
  btn.textContent = dark ? '☀' : '◐';
  btn.setAttribute('aria-pressed', String(dark));
}
$('#theme-toggle').onclick = () => {
  const dark = !document.body.classList.contains('app-dark');
  localStorage.setItem('jbook-study-dark', dark ? '1' : '0');
  applyTheme();
};
applyTheme();

/* ---------- toast ---------- */
let toastTimer = null;
function toast(message, tone){
  const el = $('#toast');
  el.textContent = message;
  el.dataset.tone = tone || 'info';
  el.dataset.show = 'true';
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.dataset.show = 'false'; }, 4000);
}

/* ---------- confirm dialog ---------- */
let confirmResolve = null;
function confirmAction(title, text){
  $('#confirm-title').textContent = title;
  $('#confirm-text').textContent = text;
  $('#confirm').dataset.open = 'true';
  $('#confirm-yes').focus();
  return new Promise(resolve => { confirmResolve = resolve; });
}
function closeDialog(value){
  $('#confirm').dataset.open = 'false';
  if(confirmResolve){ confirmResolve(value); confirmResolve = null; }
}
$('#confirm-yes').onclick = () => closeDialog(true);
$('#confirm-no').onclick = () => closeDialog(false);
$('#confirm').addEventListener('click', e => { if(e.target.id === 'confirm') closeDialog(false); });
document.addEventListener('keydown', e => {
  if(e.key === 'Escape' && $('#confirm').dataset.open === 'true') closeDialog(false);
});

/* ---------- tabs ---------- */
const TABS = ['overview','chunks','qa','logs','assets'];
function selectTab(name){
  if(!TABS.includes(name)) name = 'overview';
  selectedTab = name;
  TABS.forEach(t => {
    const tab = $('#tab-' + t), panel = $('#panel-' + t);
    const on = t === name;
    tab.setAttribute('aria-selected', String(on));
    panel.hidden = !on;
  });
  if(location.hash.slice(1) !== name) history.replaceState(null, '', '#' + name);
  if(name === 'chunks') requestAnimationFrame(renderChunks);
}
$$('.tab-btn').forEach(btn => {
  btn.onclick = () => selectTab(btn.id.replace('tab-',''));
  btn.onkeydown = e => {
    const i = TABS.indexOf(btn.id.replace('tab-',''));
    if(e.key === 'ArrowLeft'){ e.preventDefault(); $('#tab-' + TABS[i-1]).focus(); selectTab(TABS[i-1]); }
    if(e.key === 'ArrowRight'){ e.preventDefault(); $('#tab-' + TABS[i+1]).focus(); selectTab(TABS[i+1]); }
  };
});

/* ---------- actions ---------- */
async function runAction(name){
  if(!job || actionBusy) return;
  const destructive = name === 'stop' || name === 'cancel';
  if(destructive){
    const ok = await confirmAction(
      name === 'stop' ? 'توقف امن ترجمه' : 'لغو کامل ترجمه',
      name === 'stop'
        ? 'ترجمه در نقطهٔ امن بعدی متوقف می‌شود و می‌توانید بعداً ادامه دهید. ادامه می‌دهید؟'
        : 'این کار همهٔ پیشرفت ذخیره‌شده را نادیده می‌گیرد و Job لغو می‌شود. مطمئن هستید؟'
    );
    if(!ok) return;
  }
  actionBusy = true; renderActions();
  try{
    const response = await fetch('/api/jobs/' + encodeURIComponent(JOB_ID) + '/' + name, { method:'POST' });
    const data = await response.json();
    if(!response.ok) throw Error(data.error || 'عملیات انجام نشد');
    const messages = { stop:'ترجمه در نقطهٔ امن متوقف می‌شود.', resume:'ترجمه از آخرین نقطهٔ سالم ادامه یافت.',
      cancel:'Job لغو شد.', rescue:'نسخهٔ نجات آماده شد.' };
    toast(messages[name] || 'انجام شد.', 'success');
    if(name === 'rescue' && data.download) window.location.href = data.download;
    await refresh(true);
  }catch(error){
    toast(error.message, 'error');
  }finally{
    actionBusy = false; renderActions();
  }
}
$('#act-stop').onclick = () => runAction('stop');
$('#act-resume').onclick = () => runAction('resume');
$('#act-cancel').onclick = () => runAction('cancel');
$('#act-rescue').onclick = () => runAction('rescue');

function renderActions(){
  const s = job ? job.status : '';
  const show = (id, visible) => { $(id).hidden = !visible; };
  show('#act-stop', !!job && job.can_stop);
  show('#act-resume', !!job && job.can_resume);
  show('#act-cancel', !!job && job.can_cancel);
  show('#act-rescue', !!job && !!job.id);
  ['#act-stop','#act-resume','#act-cancel'].forEach(sel => { $(sel).disabled = actionBusy; });
}

/* ---------- overview ---------- */
const HEALTH_FA = { green:'سالم', yellow:'نیازمند توجه', red:'دارای مشکل' };
function renderOverview(){
  if(!job) return;
  $('#hdr-name').textContent = job.filename;
  $('#hdr-meta').textContent = [job.filetype, job.source_language + ' → ' + job.target_language, job.model]
    .filter(Boolean).join(' · ');
  $('#hdr-status').innerHTML = '<span class="badge badge-' + esc(job.status) + '">'
    + esc(STATUS_FA[job.status] || job.status) + '</span>';

  const p = job.progress || { completed:0, total:0, percent:0 };
  $('#progress-count').textContent = p.total ? fa(p.completed) + ' از ' + fa(p.total) + ' بخش ترجمه شده' : 'در حال آماده‌سازی کتاب…';
  $('#progress-percent').textContent = fa(p.percent) + '٪';
  const bar = $('#progress-bar');
  bar.style.width = Math.max(0, Math.min(100, p.percent)) + '%';
  bar.setAttribute('aria-valuenow', String(p.percent));

  const health = $('#stat-health');
  health.textContent = HEALTH_FA[job.health] || '—';
  health.style.color = job.health === 'red' ? 'var(--red)' : job.health === 'yellow' ? 'var(--amber)' : 'var(--green)';
  $('#stat-speed').textContent = job.chunks_per_minute ? fa(job.chunks_per_minute) + ' بخش/دقیقه' : 'در حال محاسبه';
  $('#stat-eta').textContent = duration(job.eta_seconds);
  $('#stat-size').textContent = bytes(job.file_size);

  $('#ov-from').textContent = job.source_language || '—';
  $('#ov-to').textContent = job.target_language || '—';
  $('#ov-model').textContent = job.model || '—';
  $('#ov-mode').textContent = MODE_FA[job.mode] || job.mode || '—';
  $('#ov-style').textContent = STYLE_FA[job.style] || job.style || '—';
  $('#ov-id').textContent = job.id || '—';
  $('#ov-created').textContent = date(job.created_at);
  $('#ov-started').textContent = date(job.started_at);
  $('#ov-updated').textContent = date(job.updated_at);

  const dl = $('#ln-download'), rd = $('#ln-reader');
  dl.hidden = !job.download; if(job.download) dl.href = job.download;
  rd.hidden = !job.reader;   if(job.reader)   rd.href = job.reader;

  const err = $('#job-error');
  err.hidden = !job.error;
  err.textContent = job.error || '';
  renderActions();
  renderAssets();
  renderQa();
}

/* ---------- virtualized chunks ---------- */
const ROW_H = 96, OVERSCAN = 6;
let filtered = [];
function applyChunkFilter(){
  const q = ($('#chunk-search').value || '').trim().toLowerCase();
  const state = $('#chunk-state').value;
  const onlyFlagged = $('#chunk-flagged').checked;
  filtered = chunks.filter(row => {
    if(onlyFlagged && !row.flagged) return false;
    if(state === 'done' && !row.translated) return false;
    if(state === 'pending' && row.translated) return false;
    if(state === 'flagged' && !row.flagged) return false;
    if(q && !(row.source.toLowerCase().includes(q) || String(row.target).toLowerCase().includes(q))) return false;
    return true;
  });
  $('#chunk-count').textContent = fa(filtered.length) + ' بخش';
  $('#vtable-wrap').scrollTop = 0;
  renderChunks();
}
function chunkRowHtml(row){
  const badge = row.flagged
    ? '<span class="flag-pill">پرچم</span>'
    : (row.translated ? '<span class="badge badge-completed">انجام شد</span>' : '<span class="badge badge-queued">در انتظار</span>');
  const target = row.translated
    ? esc(row.target)
    : '<span style="color:var(--muted)">—</span>';
  return '<tr data-flagged="' + row.flagged + '">'
    + '<td><span class="chunk-id">' + esc(row.id) + '</span>'
    + (row.chapter ? '<div class="chunk-id" style="margin-top:4px">' + esc(row.chapter) + '</div>' : '') + '</td>'
    + '<td><div class="chunk-text">' + esc(row.source) + '</div></td>'
    + '<td><div class="chunk-text" dir="rtl">' + target + '</div></td>'
    + '<td>' + badge + (row.notes.length ? '<div style="margin-top:6px">' + row.notes.map(n => '<span class="flag-pill">' + esc(n) + '</span>').join('') + '</div>' : '') + '</td>'
    + '</tr>';
}
function renderChunks(){
  const wrap = $('#vtable-wrap'), body = $('#chunk-body');
  if(!chunks.length){
    body.replaceChildren();
    $('#chunk-empty').hidden = false;
    $('#chunk-empty').textContent = job && job.paths ? 'هنوز بخشی برای این Job ساخته نشده است.' : 'اطلاعات بخش‌ها در دسترس نیست.';
    return;
  }
  $('#chunk-empty').hidden = true;
  if(!filtered.length){
    body.innerHTML = '<tr><td colspan="4"><div class="empty">بخشی با این فیلترها پیدا نشد.</div></td></tr>';
    return;
  }
  const viewport = wrap.clientHeight || 520;
  const start = Math.max(0, Math.floor(wrap.scrollTop / ROW_H) - OVERSCAN);
  const end = Math.min(filtered.length, start + Math.ceil(viewport / ROW_H) + OVERSCAN * 2);
  const top = start * ROW_H;
  const bottom = Math.max(0, (filtered.length - end) * ROW_H);
  body.innerHTML = (top ? '<tr style="height:' + top + 'px" aria-hidden="true"><td colspan="4"></td></tr>' : '')
    + filtered.slice(start, end).map(chunkRowHtml).join('')
    + (bottom ? '<tr style="height:' + bottom + 'px" aria-hidden="true"><td colspan="4"></td></tr>' : '');
}
$('#vtable-wrap').addEventListener('scroll', () => requestAnimationFrame(renderChunks), { passive:true });
$('#chunk-search').addEventListener('input', applyChunkFilter);
$('#chunk-state').addEventListener('change', applyChunkFilter);
$('#chunk-flagged').addEventListener('change', applyChunkFilter);
window.addEventListener('resize', () => { if(selectedTab === 'chunks') renderChunks(); });

async function loadChunks(){
  const body = $('#chunk-body');
  if(!chunks.length){
    body.innerHTML = Array.from({length:6}, () =>
      '<tr><td><div class="skeleton" style="height:14px"></div></td>'
      + '<td><div class="skeleton" style="height:56px"></div></td>'
      + '<td><div class="skeleton" style="height:56px"></div></td>'
      + '<td><div class="skeleton" style="height:22px"></div></td></tr>').join('');
  }
  try{
    const response = await fetch('/api/jobs/' + encodeURIComponent(JOB_ID) + '/chunks', { cache:'no-store' });
    if(response.status === 404){ chunks = []; $('#chunk-count').textContent = '—'; renderChunks(); return; }
    const data = await response.json();
    if(!response.ok) throw Error(data.error || 'بخش‌ها بارگذاری نشدند');
    chunks = (data.items || []).map(item => {
      const source = item.source || '', target = item.target || '';
      return { id: item.id, chapter: item.chapter || '', source, target,
        translated: !!target, flagged: item.flagged != null ? item.flagged : isFlagged(target) || isFlagged(source),
        notes: flaggedNotes(target).concat(flaggedNotes(source)).slice(0, 3) };
    });
    applyChunkFilter();
  }catch(error){
    chunks = [];
    body.innerHTML = '<tr><td colspan="4"><div class="empty">' + esc(error.message) + '</div></td></tr>';
    $('#chunk-count').textContent = '—';
  }
}

/* ---------- QA ---------- */
function renderQa(){
  const scores = $('#qa-scores'), body = $('#qa-body');
  const quality = job && job.quality;
  if(quality && typeof quality === 'object'){
    const entries = Object.entries(quality).filter(([, v]) => typeof v === 'number');
    scores.innerHTML = entries.map(([k, v]) =>
      '<div class="qa-item"><span>' + esc(k) + '</span><strong>' + fa(Math.round(v)) + '</strong></div>').join('');
  }else if(typeof quality === 'number'){
    scores.innerHTML = '<div class="qa-item"><span>امتیاز کلی</span><strong>' + fa(Math.round(quality)) + '</strong></div>';
  }else{
    scores.innerHTML = '';
  }
  const report = job && job.qa_report;
  if(!report){
    body.innerHTML = '<p class="empty">گزارش کیفیت هنوز تولید نشده است.</p>';
    return;
  }
  const flagged = chunks.filter(c => c.flagged);
  const head = '<p class="m-0 mb-3 text-[13px]" style="color:var(--muted)">'
    + (flagged.length ? fa(flagged.length) + ' بخش پرچم‌دار نیاز به بازبینی دارد.' : 'هیچ بخش پرچم‌داری وجود ندارد.') + '</p>';
  const reportText = '<pre class="log-box" style="direction:ltr;text-align:left">' + esc(report) + '</pre>';
  const list = flagged.length
    ? '<div class="mt-4"><ul style="display:grid;gap:10px;padding:0;margin:0;list-style:none">'
      + flagged.slice(0, 50).map(c => '<li style="padding:14px;border:1px solid var(--line);border-radius:14px;background:var(--surface-2)">'
        + '<div class="chunk-id" style="margin-bottom:6px">' + esc(c.id) + (c.chapter ? ' · ' + esc(c.chapter) : '') + '</div>'
        + c.notes.map(n => '<span class="flag-pill">' + esc(n) + '</span>').join('')
        + '<div class="chunk-text mt-2" dir="rtl">' + esc(c.target || c.source) + '</div></li>').join('')
      + '</ul></div>'
    : '';
  body.innerHTML = head + reportText + list;
}

/* ---------- assets ---------- */
function renderAssets(){
  const grid = $('#asset-grid'), empty = $('#asset-empty');
  const assets = (job && job.assets) || {};
  const downloads = (job && job.asset_downloads) || {};
  const items = Object.entries(downloads);
  if(!items.length){
    grid.replaceChildren();
    empty.hidden = false;
    return;
  }
  empty.hidden = true;
  grid.innerHTML = items.map(([name, href]) => {
    const label = ASSET_FA[name] || name;
    const raw = job.assets && job.assets[name] ? job.assets[name] : '';
    const size = raw ? '' : '';
    return '<a class="asset" href="' + esc(href) + '" aria-label="دانلود ' + esc(label) + '">'
      + '<span class="asset-name">' + esc(label.toUpperCase()) + '</span>'
      + '<span class="asset-meta">' + esc(size || name) + '</span>'
      + '<span class="btn btn-primary" style="min-height:36px;font-size:12px">دانلود</span>'
      + '</a>';
  }).join('');
}

/* ---------- logs ---------- */
async function loadLogs(){
  const timeline = $('#log-timeline');
  if(!timeline.childElementCount){
    timeline.innerHTML = '<div class="skeleton" style="height:18px;margin-bottom:10px"></div>'
      .repeat(4) + '<div class="skeleton" style="height:18px;width:70%"></div>';
  }
  try{
    const [eventsResponse, jobResponse] = await Promise.all([
      fetch('/api/jobs/' + encodeURIComponent(JOB_ID) + '/logs', { cache:'no-store' }),
      fetch('/api/jobs/' + encodeURIComponent(JOB_ID), { cache:'no-store' })
    ]);
    const data = await eventsResponse.json();
    const jobData = await jobResponse.json();
    const items = (data.items || []).slice().reverse();
    if(!items.length){
      timeline.innerHTML = '<p class="empty">هنوز رویدادی ثبت نشده است.</p>';
    }else{
      timeline.innerHTML = items.map(event =>
        '<div class="tl-row ' + esc(String(event.level || 'info').toLowerCase()) + '">'
        + '<time>' + esc(date(event.timestamp)) + '</time>'
        + '<strong>' + esc(event.message || event.event || '—') + '</strong></div>').join('');
    }
    $('#raw-log').textContent = (jobData && jobData.log) || 'لاگی برای نمایش وجود ندارد.';
  }catch(error){
    timeline.innerHTML = '<p class="empty">دریافت رویدادها ممکن نشد.</p>';
    $('#raw-log').textContent = 'دریافت لاگ ممکن نشد.';
  }
}
$('#reload-logs').onclick = loadLogs;
$('#toggle-raw').onclick = () => {
  const box = $('#raw-log'), btn = $('#toggle-raw');
  box.hidden = !box.hidden;
  btn.setAttribute('aria-pressed', String(!box.hidden));
  btn.textContent = box.hidden ? 'لاگ خام' : 'بستن لاگ خام';
};

/* ---------- refresh loop ---------- */
async function refresh(force){
  if(busy){ pending = true; return; }
  busy = true;
  try{
    const response = await fetch('/api/jobs/' + encodeURIComponent(JOB_ID), { cache:'no-store' });
    if(response.status === 404){
      toast('این Job پیدا نشد یا حذف شده است.', 'error');
      setTimeout(() => { window.location.href = '/workspace'; }, 1800);
      return;
    }
    const data = await response.json();
    if(!response.ok) throw Error(data.error || 'دریافت اطلاعات Job ممکن نشد');
    const wasRunning = job && job.status === 'running';
    job = data;
    renderOverview();
    if(force || !wasRunning || job.status === 'running') loadChunks();
    if(selectedTab === 'logs') loadLogs();
    document.title = (STATUS_FA[job.status] || job.status) + ' · ' + job.filename + ' | J Book Translate';
  }catch(error){
    if(!job) toast(error.message, 'error');
  }finally{
    busy = false;
    if(pending){ pending = false; refresh(); }
  }
}

/* ---------- boot ---------- */
const initial = new URLSearchParams(location.search);
selectTab(location.hash.slice(1) || 'overview');
refresh(true);
loadLogs();
setInterval(() => { if(!document.hidden) refresh(); }, 2000);
window.addEventListener('pageshow', () => refresh(true));
document.addEventListener('visibilitychange', () => { if(!document.hidden) refresh(true); });
})();
</script>
</body>
</html>
'''
