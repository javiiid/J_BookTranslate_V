"""Small presentation adapter for the Library page."""
from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

from .page import _library_page_base
from .glossary import glossary_panel


@lru_cache(maxsize=1)
def _embedded_vazirmatn_font_faces() -> str:
    """Return the local Vazirmatn font files as inline CSS font faces."""
    fonts = (
        ("Vazirmatn-Regular.woff2", 400),
        ("Vazirmatn-Medium.woff2", 500),
        ("Vazirmatn-SemiBold.woff2", 600),
        ("Vazirmatn-Bold.woff2", 700),
        ("Vazirmatn-Black.woff2", 800),
    )
    font_dir = Path(__file__).parent
    faces = []

    for filename, weight in fonts:
        encoded = base64.b64encode((font_dir / filename).read_bytes()).decode("ascii")
        faces.append(
            "@font-face{font-family:Vazirmatn;font-style:normal;"
            f"font-weight:{weight};src:url(data:font/woff2;base64,{encoded}) "
            "format('woff2');font-display:swap}"
        )

    return "<style>" + "".join(faces) + "</style>"


def library_page() -> str:
    page = _library_page_base()
    page = page.replace('<button data-detail="${b.id}">', '<button data-glossary="${b.id}">واژه‌نامه</button><button data-detail="${b.id}">', 1)
    page = page.replace('</body>', glossary_panel() + '</body>', 1)
    page = page.replace("</head>", _embedded_vazirmatn_font_faces() + "</head>", 1)
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
    theme = '''<style>body,.btn,.toolbar input,.toolbar select,.library-nav a,.library-nav button{font-family:Tahoma,"Segoe UI",Arial,sans-serif!important;font-synthesis:none}body{font-size:14px;line-height:1.65}.btn{font:700 13px Tahoma,"Segoe UI",Arial,sans-serif!important}.library-nav a,.library-nav button{font:600 13px Tahoma,"Segoe UI",Arial,sans-serif!important}body.app-dark{--bg:#17191d;--surface:#22252b;--ink:#d8d2c8;--muted:#aaa69f;--line:#343941;--shadow:0 16px 45px rgba(0,0,0,.22);background:radial-gradient(circle at 0 0,#252d3c,transparent 35%),var(--bg)}body.app-dark .book,body.app-dark .toolbar input,body.app-dark .toolbar select,body.app-dark .btn,body.app-dark .panel,body.app-dark .empty{background:#22252b;border-color:#343941;color:#d8d2c8}body.app-dark .cover{background:linear-gradient(135deg,#293448,#252932);color:#b8caff}</style><script>const dark=localStorage.getItem('jbook-study-dark')==='1';document.addEventListener('DOMContentLoaded',()=>{if(dark)document.body.classList.add('app-dark')});</script>'''
    refinement = '''<style>body,.btn,.toolbar input,.toolbar select,.library-nav a,.library-nav button{font-family:Vazirmatn,Tahoma,"Segoe UI",Arial,sans-serif!important}.library-shell .wrap{padding-top:36px}.head{align-items:center;margin-bottom:28px}.head h1{font-size:27px;letter-spacing:-.4px}.head p{font-size:13px;margin-top:7px}.toolbar{padding:11px;background:rgba(255,255,255,.74);border:1px solid var(--line);border-radius:16px;box-shadow:0 8px 24px rgba(38,57,93,.035)}.toolbar input,.toolbar select{height:43px;border-radius:11px;font-size:13px}.summary{padding:11px 14px;background:rgba(255,255,255,.64);border:1px solid var(--line);border-radius:13px;gap:18px}.grid{grid-template-columns:repeat(auto-fill,minmax(275px,1fr));gap:18px;align-items:stretch}.book{border-radius:18px;box-shadow:0 12px 32px rgba(38,57,93,.07);transition:transform .18s ease,box-shadow .18s ease}.book:hover{transform:translateY(-3px);box-shadow:0 18px 38px rgba(38,57,93,.13)}.cover{height:126px;background:linear-gradient(145deg,#dce8ff,#f2f5ff);font-size:37px}.book-body{padding:17px}.book-title{font-size:16px;line-height:1.7}.book-meta{font-size:12px;margin-top:6px}.badge{margin-top:13px;padding:5px 10px}.book-actions{border-top:1px solid var(--line);padding-top:13px;margin-top:15px}.book-actions a,.book-actions button{font-family:Vazirmatn,Tahoma,sans-serif!important;font-size:11px;padding:8px 10px;border-radius:9px}.note{line-height:1.8}body.app-dark .toolbar,body.app-dark .summary{background:#20242b;border-color:#343941}body.app-dark .book-actions{border-color:#343941}body.app-dark .badge{background:#29344b;color:#c1d0ff}body.app-dark .badge.completed{background:#183c34;color:#a7dfca}@media(max-width:600px){.library-shell .wrap{padding:24px 13px 54px}.head h1{font-size:23px}.toolbar{padding:9px}.toolbar input{min-width:100%}.grid{grid-template-columns:1fr}}</style>'''
    sidebar = '''<style>.library-sidebar{position:fixed;z-index:4;right:18px;top:18px;bottom:18px;width:250px;padding:18px 14px;background:rgba(255,255,255,.94);border:1px solid #e2e8f2;border-radius:20px;box-shadow:0 18px 55px rgba(38,57,93,.1);display:flex;flex-direction:column;gap:16px}.library-sidebar .brand{display:flex;align-items:center;gap:9px;padding:4px 7px 15px;border-bottom:1px solid #e9edf4}.library-sidebar .mark{width:36px;height:36px;border-radius:11px;display:grid;place-items:center;color:#fff;background:linear-gradient(140deg,#356df6,#7257e8);font-size:18px}.library-sidebar .brand strong{font-size:14px}.library-sidebar .brand small{display:block;color:#78859a;font-size:10px}.library-nav{display:grid;gap:5px}.library-nav a,.library-nav button{display:block;width:100%;border:0;background:transparent;color:#69778d;text-align:right;padding:10px 11px;border-radius:9px;font:600 12px Vazirmatn,Segoe UI,sans-serif;text-decoration:none;cursor:pointer}.library-nav a:hover,.library-nav a.active,.library-nav button:hover{background:#edf3ff;color:#2e62dc}.library-nav span{display:inline-block;width:23px;color:#7890bd;font-size:15px}.library-theme{margin-top:auto}.library-shell .wrap{margin-right:292px;max-width:calc(1240px - 292px)}body.app-dark .library-sidebar{background:rgba(34,37,43,.96);border-color:#343941;box-shadow:0 18px 55px rgba(0,0,0,.22)}body.app-dark .library-sidebar .brand{border-color:#343941}body.app-dark .library-sidebar .brand small,body.app-dark .library-sidebar a,body.app-dark .library-sidebar button{color:#aaaeb8}body.app-dark .library-sidebar a:hover,body.app-dark .library-sidebar a.active,body.app-dark .library-sidebar button:hover{background:#29344b;color:#b8caff}@media(max-width:850px){.library-sidebar{position:relative;right:auto;top:auto;bottom:auto;width:auto;margin:12px 13px 0;padding:12px;border-radius:15px;display:block}.library-sidebar .brand{display:none}.library-nav{display:flex;overflow:auto}.library-nav a,.library-nav button{white-space:nowrap;width:auto}.library-theme{display:inline-block}.library-shell .wrap{margin-right:auto;max-width:1240px}}</style><aside class="library-sidebar" aria-label="ناوبری اصلی"><div class="brand"><div class="mark">文</div><div><strong>J Book Translate</strong><small>Translation Studio</small></div></div><nav class="library-nav"><a href="/"><span>⌂</span>داشبورد</a><a href="/#translate-form"><span>＋</span>ترجمهٔ جدید</a><a class="active" href="/library"><span>▣</span>کتابخانه</a></nav><div class="library-theme"><button id="library-theme-toggle"><span>◐</span> حالت شب</button></div></aside><script>document.querySelector('#library-theme-toggle').onclick=function(){document.body.classList.toggle('app-dark');localStorage.setItem('jbook-study-dark',document.body.classList.contains('app-dark')?'1':'0')};</script>'''
    return page.replace('</head>', theme + refinement + sidebar + '</head>', 1).replace('<body>', '<body class="library-shell">', 1)
