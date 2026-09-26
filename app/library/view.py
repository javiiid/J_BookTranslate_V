"""Small presentation adapter for the Library page."""
from __future__ import annotations

from app.core.fonts import embedded_vazirmatn_font_faces
from .page import _library_page_base
from .glossary import glossary_panel


def library_page() -> str:
    page = _library_page_base()
    page = page.replace('<button data-detail="${b.id}">', '<button data-glossary="${b.id}">واژه‌نامه</button><button data-detail="${b.id}">', 1)
    page = page.replace('</body>', glossary_panel() + '</body>', 1)
    page = page.replace("</head>", embedded_vazirmatn_font_faces() + "</head>", 1)
    page = page.replace(
        '<option value="available">',
        '<option value="archived">آرشیوشده</option><option value="available">',
        1,
    )
    page = page.replace(
        '<button data-delete="${b.id}">',
        '<button data-archive="${b.id}">آرشیو</button><button data-delete="${b.id}">',
        1,
    )
    page = page.replace(
        "document.querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>removeBook(Number(b.dataset.delete)))",
        "document.querySelectorAll('[data-archive]').forEach(b=>b.onclick=()=>archiveBook(Number(b.dataset.archive)));document.querySelectorAll('[data-delete]').forEach(b=>b.onclick=()=>removeBook(Number(b.dataset.delete)))",
        1,
    )
    page = page.replace(
        "async function removeBook(id)",
        "async function archiveBook(id){if(!confirm('این کتاب آرشیو شود؟'))return;await fetch('/api/library/'+id+'/archive',{method:'POST'});load()}async function removeBook(id)",
        1,
    )
    # Apply the saved theme before first paint to avoid a light-mode flash.
    theme = '''<script>document.addEventListener('DOMContentLoaded',()=>document.body.classList.toggle('app-dark',localStorage.getItem('jbook-study-dark')==='1'))</script>'''
    sidebar = '''<style>.library-sidebar{position:fixed;z-index:30;right:18px;top:18px;bottom:18px;width:252px;padding:20px 14px;background:color-mix(in srgb,var(--surface) 92%,transparent);backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:22px;box-shadow:var(--shadow);display:flex;flex-direction:column;gap:18px}.library-sidebar .brand{display:flex;align-items:center;gap:10px;padding:2px 6px 16px;border-bottom:1px solid var(--line)}.library-sidebar .mark{width:38px;height:38px;border-radius:12px;display:grid;place-items:center;color:#fff;background:var(--grad);font-size:18px;box-shadow:0 8px 18px rgba(53,109,246,.3)}.library-sidebar .brand strong{font-size:14px;font-weight:800}.library-sidebar .brand small{display:block;color:var(--muted);font-size:10px;font-weight:600;margin-top:2px}.library-nav{display:grid;gap:4px}.library-nav a,.library-nav button{display:flex;align-items:center;gap:10px;width:100%;border:0;background:transparent;color:var(--ink-2);text-align:right;padding:10px 12px;border-radius:11px;font:600 12.5px Vazirmatn,Segoe UI,sans-serif;text-decoration:none;cursor:pointer;transition:background .15s ease,color .15s ease,transform .15s ease}.library-nav a span,.library-nav button span{display:inline-block;width:22px;color:var(--muted);font-size:15px;text-align:center}.library-nav a:hover,.library-nav a.active,.library-nav button:hover{background:var(--blue-soft);color:var(--brand);transform:translateX(-2px)}.library-nav a.active{font-weight:800}.library-theme{margin-top:auto}.library-theme button#library-theme-toggle{display:flex;align-items:center;justify-content:center;gap:8px;width:100%;border:1px solid var(--line);background:var(--surface-2);color:var(--ink-2);border-radius:12px;padding:11px;font:700 12px inherit;cursor:pointer;transition:background .15s ease,color .15s ease,border-color .15s ease}.library-theme button#library-theme-toggle:hover{background:var(--blue-soft);color:var(--brand);border-color:#c9d9fb}.library-shell .wrap{margin-right:292px;max-width:calc(1260px - 292px)}@media(max-width:860px){.library-sidebar{position:relative;right:auto;top:auto;bottom:auto;width:auto;margin:14px 14px 0;padding:12px 14px;border-radius:16px;display:block}.library-sidebar .brand{display:none}.library-nav{display:flex;overflow-x:auto}.library-nav a,.library-nav button{display:inline-flex;padding:8px 14px;white-space:nowrap}.library-shell .wrap{margin-right:0;max-width:1260px}}</style><aside class="library-sidebar" aria-label="ناوبری اصلی"><div class="brand"><div class="mark">文</div><div><strong>J Book Translate</strong><small>Translation Studio</small></div></div><nav class="library-nav"><a href="/"><span>⌂</span>داشبورد</a><a href="/#translate-form"><span>＋</span>ترجمهٔ جدید</a><a class="active" href="/library"><span>▣</span>کتابخانه</a></nav><div class="library-theme"><button id="library-theme-toggle"><span>◐</span> حالت شب</button></div></aside><script>document.querySelector('#library-theme-toggle').onclick=function(){document.body.classList.toggle('app-dark');localStorage.setItem('jbook-study-dark',document.body.classList.contains('app-dark')?'1':'0')};</script>'''
    gloss = '''<style>#glossary-dialog{width:min(960px,96vw);max-height:90vh;border:1px solid var(--line);border-radius:20px;background:var(--surface);color:var(--ink);font-family:Vazirmatn,Tahoma,sans-serif;padding:0;overflow:hidden;box-shadow:var(--shadow-lg)}#glossary-dialog h2{margin:0;padding:16px 20px;border-bottom:1px solid var(--line);position:sticky;top:0;background:var(--surface);z-index:2;font-size:17px}#glossary-dialog .glossary-controls{padding:0 20px 18px;margin:14px 0 0}#glossary-dialog>p,#glossary-dialog>label{padding:0 20px}#glossary-dialog #glossary-rows{padding:0 20px;margin:10px 0 0}#glossary-dialog input,#glossary-dialog button{border-radius:9px;font:inherit;padding:8px 11px;border:1px solid var(--line);background:var(--surface-2);color:var(--ink)}#glossary-dialog button{cursor:pointer;font-weight:700}#glossary-dialog button:hover{border-color:#c9d9fb;background:var(--blue-soft);color:var(--brand)}#glossary-dialog #glossary-close{position:absolute;top:13px;left:15px;z-index:3;float:none}#glossary-dialog #glossary-error{color:var(--red)}#glossary-dialog::backdrop{background:#0d152688;backdrop-filter:blur(3px)}</style>'''
    return page.replace('</head>', theme + sidebar + gloss + '</head>', 1).replace('<body>', '<body class="library-shell">', 1)