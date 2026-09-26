"""Client-side language switcher shared by local web screens."""
from __future__ import annotations

import json


TRANSLATIONS = {
    "خانه": "Home", "میز کار": "Workspace", "کتابخانه": "Library", "کارهای من": "My jobs",
    "ترجمهٔ جدید": "New translation", "ورود به میز کار": "Open workspace", "امکانات": "Features",
    "شروع ترجمهٔ جدید": "Start a new translation", "مشاهدهٔ کارهای من": "View my jobs",
    "برنامه روی همین دستگاه اجرا می‌شود": "Runs locally on this device", "آمادهٔ شروع ترجمه": "Ready to translate",
    "ترجمه‌های فعال": "Active translations", "کتاب‌های کتابخانه": "Library books", "تکمیل‌شده": "Completed",
    "متوقف‌شده": "Paused", "آخرین کارها": "Recent jobs", "مشاهدهٔ همه": "View all",
    "در حال دریافت اطلاعات…": "Loading data…", "هنوز کاری ثبت نشده است.": "No jobs yet.",
    "شروع سریع": "Quick start", "در سه مرحله ترجمه را شروع کن": "Start translating in three steps",
    "کتاب را انتخاب کن": "Choose a book", "زبان و مدل را مشخص کن": "Choose language and model",
    "پیشرفت را دنبال کن": "Track progress", "همه‌چیز در یک فضای کاری": "Everything in one workspace",
    "کتابخانهٔ منظم": "Organized library", "واژه‌نامهٔ ثابت": "Consistent glossary", "Reader دوزبانه": "Bilingual reader",
    "مرکز نگهداری و مطالعهٔ کتاب‌های اصلی و ترجمه‌شده": "Manage and read original and translated books",
    "بازگشت به میز کار": "Back to workspace", "جست‌وجوی نام کتاب…": "Search books…",
    "همهٔ وضعیت‌ها": "All statuses", "همهٔ فرمت‌ها": "All formats", "نمایش فهرستی": "List view",
    "نمایش شبکه‌ای": "Grid view", "فایل اصلی": "Original file", "در حال ترجمه": "Translating",
    "خطادار": "Failed", "مطالعه": "Read", "دانلود": "Download", "جزئیات": "Details",
    "حذف": "Delete", "آرشیو": "Archive", "واژه‌نامه": "Glossary", "حالت شب": "Dark mode",
    "حالت روشن": "Light mode", "میز کار ترجمه": "Translation workspace",
    "کارهای فعال و اخیر": "Active and recent jobs", "جست‌وجوی نام کتاب یا شناسهٔ کار": "Search book or job ID",
    "همه": "All", "در صف": "Queued", "متوقف شده": "Paused", "در حال توقف": "Stopping",
    "تکمیل شد": "Completed", "پایان یافت": "Finished", "خطا": "Failed", "قطع ارتباط": "Disconnected",
    "توقف امن ترجمه": "Pause safely", "ادامهٔ ترجمه": "Resume translation", "دریافت خروجی": "Download output",
    "جزئیات فنی و گزارش اجرا": "Technical details and logs", "ترجمهٔ جدید": "New translation",
    "زبان مبدأ": "Source language", "زبان مقصد": "Target language", "مدل ترجمه": "Translation model",
    "حالت اجرا": "Processing mode", "سریع (پیشنهادی)": "Fast (recommended)", "ساخت خودکار واژه‌نامه حین ترجمه": "Build glossary automatically",
    "حفظ لحن و صدای نویسنده": "Preserve author voice and tone", "شروع ترجمه": "Start translation",
    "تنظیمات پیشرفته و دستور ترجمه": "Advanced settings and translation instructions",
    "حالت شب مطالعه": "Reading dark mode", "متن کوچک": "Small text", "متن معمولی": "Normal text",
    "متن بزرگ": "Large text", "متن خیلی بزرگ": "Extra large text", "فشرده": "Compact", "راحت": "Comfortable",
    "باز": "Spacious", "باریک": "Narrow", "استاندارد": "Standard", "عریض": "Wide", "خودکار": "Auto",
    "راست‌به‌چپ": "Right to left", "چپ‌به‌راست": "Left to right", "بازنشانی": "Reset",
    "ترجمه": "Translation", "دوزبانه": "Bilingual", "متن اصلی": "Original", "فهرست": "Contents",
    "فصل قبلی": "Previous chapter", "فصل بعدی": "Next chapter", "فهرست فصل‌ها": "Chapters",
    "داشبورد": "Dashboard", "پنل کاربری": "Account portal", "تنظیمات API آماده است": "API configuration is ready",
    "ارتباط API برقرار است": "API connection is ready", "وضعیت API نامشخص است": "API status is unknown",
    "مرکز مطالعه و نگهداری": "Reading & study center", "بازگشت به داشبورد": "Back to dashboard",
    "آرشیوشده": "Archived", "کتاب‌ها": "Books", "حجم کتابخانه": "Library size", "فضای آزاد": "Free space",
    "جست‌وجو": "Search", "پاک کردن": "Clear", "وضعیت": "Status", "فرمت": "Format", "بستن": "Close",
    "نسخه": "Version", "حذف این کتاب": "Delete this book",
    "کتابی در این بخش پیدا نشد.": "No books found in this section.",
    "کتابی در کتابخانه ثبت نشده است.": "No books registered yet.",
    "فیلترها را تغییر دهید و دوباره جست‌وجو کنید.": "Adjust the filters and search again.",
    "اولین کتاب EPUB یا PDF را ترجمه کنید تا اینجا نمایش داده شود.": "Translate your first EPUB or PDF to see it here.",
    "خطایی رخ داد": "An error occurred",
    "دریافت فهرست کتابخانه ناموفق بود؛ دوباره تلاش کنید.": "Could not load the library; please retry.",
    "ترجمه‌شده": "Translated", "نسخهٔ اصلی": "Original version", "آخرین فعالیت": "Last activity",
}


def language_switcher() -> str:
    translations = json.dumps(TRANSLATIONS, ensure_ascii=False).replace("</", "<\\/")
    return f'''<style>#global-language{{position:fixed;z-index:50;left:18px;bottom:18px;border:1px solid var(--line,#dfe5ee);border-radius:999px;padding:9px 13px;background:var(--surface,#fff);color:var(--ink,#17243a);font:700 11px Vazirmatn,Tahoma,sans-serif;box-shadow:0 10px 30px #17243a20;cursor:pointer}}html[dir=ltr] #global-language{{left:auto;right:18px}}</style><button id="global-language" type="button" aria-label="Change language">English</button><script>(()=>{{
const translations={translations},originalText=new WeakMap(),originalAttrs=new WeakMap();let language=localStorage.getItem('jbook-language')||'fa';
function translateText(node){{if(!originalText.has(node))originalText.set(node,node.nodeValue);const original=originalText.get(node),trimmed=original.trim();if(language==='fa'){{node.nodeValue=original;return}}const translated=translations[trimmed];if(translated)node.nodeValue=original.replace(trimmed,translated)}}
function translateElement(element){{if(!(element instanceof Element))return;const attrs=['placeholder','title','aria-label'];if(!originalAttrs.has(element))originalAttrs.set(element,Object.fromEntries(attrs.map(name=>[name,element.getAttribute(name)])));const originals=originalAttrs.get(element);for(const name of attrs){{const original=originals[name];if(original===null)continue;element.setAttribute(name,language==='fa'?original:(translations[original]||original))}}}}
function walk(root=document.body){{const walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);let node;while(node=walker.nextNode()){{if(!node.parentElement?.closest('script,style,code,pre'))translateText(node)}}root.querySelectorAll?.('*').forEach(translateElement)}}
function apply(){{document.documentElement.lang=language;document.documentElement.dir=language==='fa'?'rtl':'ltr';walk();const button=document.getElementById('global-language');if(button)button.textContent=language==='fa'?'English':'فارسی';localStorage.setItem('jbook-language',language)}}
document.getElementById('global-language').onclick=()=>{{language=language==='fa'?'en':'fa';apply()}};new MutationObserver(records=>{{for(const record of records)for(const node of record.addedNodes){{if(node.nodeType===Node.TEXT_NODE)translateText(node);else if(node.nodeType===Node.ELEMENT_NODE)walk(node)}}}}).observe(document.body,{{childList:true,subtree:true}});apply();
}})();</script>'''


def inject_language_switcher(page: str) -> str:
    return page.replace("</body>", language_switcher() + "</body>", 1)
