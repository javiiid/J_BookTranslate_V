"""Glossary proposal panel: propose, review, approve.

A proposal is a draft the user decides on. Nothing reaches the live glossary
until it is approved, and the approved set is what gets snapshotted into the
job, so every chunk - including the first - translates with the same
terminology. Nothing is learned automatically during a run.
"""
from __future__ import annotations


def install_glossary_proposal(page: str) -> str:
    style = """<style>
.glossary-box{margin:0 0 14px;padding:14px 16px;border:1px solid var(--line);border-radius:14px;background:var(--surface-2)}
.glossary-head{display:flex;align-items:center;justify-content:space-between;gap:10px}
.glossary-head strong{font-size:13px}
.glossary-count{font-size:11px;padding:3px 10px;border-radius:999px;background:#edf3ff;color:#2e62dc;font-weight:700}
.glossary-note{margin:8px 0 12px;font-size:12px;line-height:1.9;color:var(--muted)}
.glossary-actions{display:flex;gap:8px;flex-wrap:wrap}
.glossary-status{margin-top:10px;font-size:12px;line-height:1.8;min-height:0}
.glossary-status:empty{display:none}
.glossary-status[data-tone=error]{color:var(--red)}
.glossary-status[data-tone=ok]{color:var(--green)}
body.app-dark .glossary-count{background:#1e3a5a;color:#b8caff}
.proposal-overlay{position:fixed;inset:0;z-index:70;display:none;place-items:center;padding:20px;background:rgba(12,20,34,.5);backdrop-filter:blur(4px)}
.proposal-overlay[data-open=true]{display:grid}
.proposal{width:min(720px,100%);max-height:86vh;overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:20px;padding:24px;box-shadow:0 24px 60px rgba(0,0,0,.3)}
.proposal h2{margin:0 0 4px;font-size:18px;font-weight:800}
.proposal>p{margin:0 0 16px;font-size:12.5px;line-height:1.9;color:var(--muted)}
.proposal-table{width:100%;border-collapse:collapse;font-size:12.5px}
.proposal-table th{text-align:start;padding:9px 10px;font-size:11px;color:var(--muted);border-bottom:1px solid var(--line)}
.proposal-table td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:middle}
.proposal-table input[type=text]{width:100%;min-height:38px;padding:6px 10px;border:1px solid var(--line);border-radius:9px;background:var(--surface);color:var(--ink);font:inherit}
.proposal-kind{font-size:10px;padding:3px 8px;border-radius:999px;background:#f1f5f9;color:#64748b;white-space:nowrap}
.proposal-foot{display:flex;gap:10px;justify-content:space-between;align-items:center;margin-top:18px;flex-wrap:wrap}
.proposal-foot small{color:var(--muted);font-size:12px}
</style>"""

    panel = """
<div class="proposal-overlay" id="proposal-overlay" role="dialog" aria-modal="true" aria-labelledby="proposal-title" data-open="false">
  <div class="proposal">
    <h2 id="proposal-title">بازبینی پیشنهاد واژه‌نامه</h2>
    <p>این‌ها پیشنهاد مدل هستند و هنوز واژه‌نامه نشده‌اند. هر موردی را که می‌خواهید نگه دارید تیک بزنید یا متنش را اصلاح کنید.</p>
    <table class="proposal-table">
      <thead><tr><th scope="col" style="width:34px">نگه‌داری</th><th scope="col">عبارت مبدأ</th><th scope="col">معادل</th><th scope="col" style="width:92px">نوع</th></tr></thead>
      <tbody id="proposal-body"></tbody>
    </table>
    <div class="proposal-foot">
      <small id="proposal-summary">—</small>
      <div style="display:flex;gap:10px">
        <button type="button" class="btn-primary" id="proposal-approve" aria-label="تأیید اصطلاحات انتخاب‌شده">تأیید انتخاب‌شده‌ها</button>
        <button type="button" class="btn-secondary" id="proposal-cancel" aria-label="انصراف از بازبینی">انصراف</button>
      </div>
    </div>
  </div>
</div>"""

    script = r"""<script>
(function(){
const $ = s => document.querySelector(s);
const box = $('#glossary-box');
if(!box) return;
const fa = n => new Intl.NumberFormat('fa-IR').format(n||0);
const status = (message, tone) => { const el=$('#glossary-status'); el.textContent=message||''; el.dataset.tone=tone||''; };
const overlay = $('#proposal-overlay');
let draft = [], bookId = null, languages = {from:'EN', to:'FA'}, busy = false;

function closeOverlay(){ overlay.dataset.open='false'; }

/* The glossary lives on a book, not on an upload, so a proposal needs a book
   id. New uploads get registered as a book on submit; until then the panel
   explains what to do instead of failing silently. */
function requireBook(){
  status('ابتدا کتاب را یک‌بار در کتابخانه ثبت کنید تا بتوان برایش واژه‌نامه ساخت.', 'error');
  box.scrollIntoView({behavior:'smooth', block:'nearest'});
}

async function loadGlossary(){
  if(!bookId) return;
  try{
    const [approved, draftBox] = await Promise.all([
      fetch(`/api/library/${bookId}/glossary?from=${languages.from}&to=${languages.to}`),
      fetch(`/api/library/${bookId}/glossary/proposal?from=${languages.from}&to=${languages.to}&origin=preflight`)
    ]);
    const terms = (await approved.json()).terms || [];
    const proposal = (await draftBox.json()).terms || [];
    $('#glossary-count').textContent = fa(terms.length) + ' اصطلاح تأییدشده';
    $('#glossary-review').hidden = proposal.length === 0;
    $('#auto_glossary_field').value = 'false';
    if(terms.length){
      status('این واژه‌نامه در همهٔ بخش‌ها، از جمله بخش اول، اعمال می‌شود.');
    }else if(proposal.length){
      status('پیشنهاد آمادهٔ بازبینی است. تا تأیید نکنید، ترجمه بدون واژه‌نامه انجام می‌شود.', 'error');
    }else{
      status('واژه‌نامه‌ای ثبت نشده. بدون آن هم ترجمه انجام می‌شود، اما اصطلاحات یکدست نمی‌مانند.', 'error');
    }
  }catch(error){ status('خواندن واژه‌نامه ممکن نشد.', 'error'); }
}

/* The upload response carries the book id, so the panel can offer proposals for
   a book the user has just added. Books added before this panel existed are
   reachable from the library page. */
function adoptFromJob(job){
  if(!job) return;
  if(job.book_id){
    setBook(job.book_id, job.from_lang, job.to_lang);
  }else{
    status('این کتاب در کتابخانه ثبت نشد؛ برای ساخت واژه‌نامه از صفحهٔ کتابخانه اقدام کنید.', 'error');
  }
}

$('#glossary-propose').onclick = async () => {
  if(!bookId) return requireBook();
  if(busy) return;
  busy = true;
  const button = $('#glossary-propose');
  button.disabled = true;
  status('در حال خواندن متن کتاب و ساخت پیشنهاد… این یک درخواست است و ممکن است ۲۰ تا ۶۰ ثانیه طول بکشد.');
  try{
    const response = await fetch(`/api/library/${bookId}/glossary/propose`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({from_lang: languages.from, to_lang: languages.to})
    });
    const data = await response.json();
    if(!response.ok) throw Error(data.error || 'ساخت پیشنهاد ناموفق بود');
    draft = data.terms || [];
    if(!draft.length){ status('مدل اصطلاح قابل‌اعتمادی پیدا نکرد. می‌توانید دستی واژه‌نامه بنویسید.', 'error'); }
    else { renderDraft(); openOverlay(); }
    await loadGlossary();
  }catch(error){ status(error.message, 'error'); }
  finally{ busy = false; button.disabled = false; }
};

function openOverlay(){ overlay.dataset.open='true'; }

function renderDraft(){
  $('#proposal-body').replaceChildren();
  draft.forEach((term, index) => {
    const row = document.createElement('tr');
    const check = document.createElement('td');
    const box = document.createElement('input');
    box.type = 'checkbox'; box.checked = true; box.dataset.index = String(index);
    box.setAttribute('aria-label', 'نگه‌داری ' + term.source_term);
    check.append(box);
    const source = document.createElement('td'); source.dir = 'ltr'; source.textContent = term.source_term;
    const target = document.createElement('td');
    const input = document.createElement('input');
    input.type = 'text'; input.dir = 'auto'; input.value = term.target_term;
    input.dataset.index = String(index);
    input.setAttribute('aria-label', 'معادل ' + term.source_term);
    target.append(input);
    const kind = document.createElement('td');
    const badge = document.createElement('span');
    badge.className = 'proposal-kind'; badge.textContent = term.kind || 'term';
    kind.append(badge);
    row.append(check, source, target, kind);
    $('#proposal-body').append(row);
  });
  updateSummary();
}

function updateSummary(){
  const kept = $('#proposal-body').querySelectorAll('input[type=checkbox]:checked').length;
  $('#proposal-summary').textContent = fa(kept) + ' از ' + fa(draft.length) + ' مورد انتخاب شده';
}

$('#proposal-body').addEventListener('change', event => {
  if(event.target.type === 'checkbox') updateSummary();
});

$('#proposal-cancel').onclick = closeOverlay;
overlay.addEventListener('click', event => { if(event.target === overlay) closeOverlay(); });
document.addEventListener('keydown', event => {
  if(event.key === 'Escape' && overlay.dataset.open === 'true') closeOverlay();
});

$('#proposal-approve').onclick = async () => {
  const inputs = $('#proposal-body').querySelectorAll('input[type=text]');
  inputs.forEach(input => { draft[Number(input.dataset.index)].target_term = input.value.trim(); });
  const approved = $('#proposal-body')
    .querySelectorAll('input[type=checkbox]:checked')
    .map(box => draft[Number(box.dataset.index)].source_term);
  if(!approved.length){ status('هیچ موردی انتخاب نشده است.', 'error'); return; }
  const button = $('#proposal-approve');
  button.disabled = true;
  try{
    const response = await fetch(`/api/library/${bookId}/glossary/proposal/approve`, {
      method:'PUT', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({from_lang: languages.from, to_lang: languages.to, origin:'preflight', approved})
    });
    const data = await response.json();
    if(!response.ok) throw Error(data.error || 'تأیید ناموفق بود');
    closeOverlay();
    status(fa(data.terms.length) + ' اصطلاح تأیید و ذخیره شد. در همهٔ بخش‌ها اعمال می‌شود.', 'ok');
    await loadGlossary();
  }catch(error){ status(error.message, 'error'); }
  finally{ button.disabled = false; }
};

$('#glossary-review').onclick = async () => {
  if(!bookId) return requireBook();
  try{
    const response = await fetch(`/api/library/${bookId}/glossary/proposal?from=${languages.from}&to=${languages.to}&origin=preflight`);
    draft = (await response.json()).terms || [];
    if(!draft.length){ status('پیشنهاد باقی‌مانده‌ای نیست.'); return; }
    renderDraft(); openOverlay();
  }catch(error){ status('خواندن پیشنهاد ممکن نشد.', 'error'); }
};

window.jbtGlossary = {
  setBook(id, from, to){
    bookId = id;
    languages = {from: from || languages.from, to: to || languages.to};
    loadGlossary();
  }
};
})();
</script>"""

    page = page.replace("</head>", style + "</head>", 1)
    page = page.replace("</body>", panel + script + "</body>", 1)
    return page
