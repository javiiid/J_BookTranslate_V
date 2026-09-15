"""Library terminology editor."""


def glossary_panel():
    return '''
<style>
#glossary-dialog{width:min(960px,96vw);max-height:90vh;border:1px solid var(--line);border-radius:16px;background:var(--surface);color:var(--ink);font-family:Vazirmatn,Tahoma,sans-serif}
#glossary-dialog::backdrop{background:#0008}#glossary-dialog input,#glossary-dialog button{font:inherit;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--surface);color:var(--ink)}
.glossary-row{display:grid;grid-template-columns:1fr 1fr .6fr 1.3fr auto;gap:8px;margin:8px 0}.glossary-controls{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}#glossary-error{color:#d84444}#glossary-rows{max-height:45vh;overflow:auto}@media(max-width:650px){.glossary-row{grid-template-columns:1fr 1fr}}
.glossary-row[hidden]{display:none}
</style>
<dialog id="glossary-dialog" dir="rtl" aria-labelledby="glossary-title">
<button id="glossary-close" style="float:left">بستن</button><h2 id="glossary-title">واژه‌نامهٔ کتاب</h2>
<p>تغییرات برای ترجمهٔ جدید استفاده می‌شوند. ادامهٔ ترجمهٔ قبلی، نسخهٔ قبلی واژه‌نامه را حفظ می‌کند.</p>
<label><input type="checkbox" id="glossary-auto" checked> ساخت خودکار واژه‌نامه حین ترجمه</label>
<p>اسم‌ها و اصطلاحات از هر قطعهٔ ترجمه‌شده استخراج و در قطعه‌های بعدی استفاده می‌شوند. این گزینه برای هر قطعه یک درخواست API اضافی دارد. برای دیدن اصطلاحات جدید هنگام ترجمه، «بارگذاری» را بزنید.</p>
<div class="glossary-controls"><label>زبان مبدأ <input id="glossary-from" value="EN" size="5" dir="ltr"></label><label>زبان مقصد <input id="glossary-to" value="FA" size="5" dir="ltr"></label><button id="glossary-load">بارگذاری</button></div>
<input id="glossary-search" placeholder="جست‌وجوی اصطلاح" aria-label="جست‌وجوی اصطلاح">
<p id="glossary-version"></p><div id="glossary-rows"></div><p id="glossary-error" role="status"></p>
<div class="glossary-controls"><button id="glossary-add">افزودن اصطلاح</button><button id="glossary-save">ذخیرهٔ واژه‌نامه</button></div>
<div class="glossary-controls"><label>مدل <input id="glossary-model" dir="ltr" placeholder="مدل پیش‌فرض"></label><button id="glossary-translate">ذخیره و شروع ترجمهٔ جدید</button></div>
</dialog>
<script>
(()=>{
const dialog=document.getElementById('glossary-dialog'), rows=document.getElementById('glossary-rows'), error=document.getElementById('glossary-error');
let bookId=null,current=null,dirty=false;
const element=id=>document.getElementById('glossary-'+id);
async function request(path,options){const response=await fetch(path,options);const data=await response.json();if(!response.ok)throw Error(data.error||'خطای درخواست');return data}
function report(action){return async()=>{error.textContent='';try{await action()}catch(exc){error.textContent=exc.message}}}
function add(term={}){const row=document.createElement('div');row.className='glossary-row';row.dataset.origin=term.origin||'manual';row.title=term.origin==='automatic'?'استخراج خودکار؛ قابل ویرایش':'ثبت دستی';for(const [key,label] of [['source_term','عبارت اصلی'],['target_term','معادل ثابت'],['kind','نوع: شخصیت، مکان…'],['notes','توضیح']]){const input=document.createElement('input');input.dataset.key=key;input.value=term[key]||'';input.placeholder=label;input.setAttribute('aria-label',label);input.maxLength=key==='notes'?500:key==='kind'?30:200;input.oninput=()=>{dirty=true;row.dataset.origin='manual'};row.append(input)}const remove=document.createElement('button');remove.textContent=term.origin==='automatic'?'حذف (خودکار)':'حذف';remove.onclick=()=>{row.remove();dirty=true};row.append(remove);rows.append(row)}
async function load(){if(dirty&&!confirm('تغییرات ذخیره‌نشده کنار گذاشته شوند؟'))return;current=null;element('save').disabled=true;element('translate').disabled=true;const data=await request('/api/library/'+bookId+'/glossary?from='+encodeURIComponent(element('from').value)+'&to='+encodeURIComponent(element('to').value));current=data;rows.replaceChildren();data.terms.forEach(add);dirty=false;element('version').textContent='نسخهٔ '+data.version;element('save').disabled=false;element('translate').disabled=false;element('search').value=''}
async function save(){if(!current)throw Error('ابتدا واژه‌نامه را بارگذاری کنید.');if(element('from').value.toUpperCase()!==current.source_language||element('to').value.toUpperCase()!==current.target_language)throw Error('پس از تغییر زبان، بارگذاری را بزنید.');const terms=[...rows.children].map(row=>({...Object.fromEntries([...row.querySelectorAll('input')].map(input=>[input.dataset.key,input.value])),origin:row.dataset.origin}));current=await request('/api/library/'+bookId+'/glossary',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({...current,terms})});dirty=false;element('version').textContent='ذخیره شد؛ نسخهٔ '+current.version}
document.addEventListener('click',async event=>{const button=event.target.closest('[data-glossary]');if(!button)return;bookId=Number(button.dataset.glossary);dirty=false;dialog.showModal();await report(load)()});
element('load').onclick=report(load);element('save').onclick=report(save);element('add').onclick=()=>{add();dirty=true};
element('close').onclick=()=>{if(!dirty||confirm('بدون ذخیره بسته شود؟')){dirty=false;dialog.close()}};
dialog.addEventListener('cancel',event=>{if(dirty&&!confirm('بدون ذخیره بسته شود؟'))event.preventDefault()});
element('search').oninput=()=>{const query=element('search').value.toLocaleLowerCase();for(const row of rows.children)row.hidden=![...row.querySelectorAll('input')].some(input=>input.value.toLocaleLowerCase().includes(query))};
element('translate').onclick=report(async()=>{if(!confirm('ترجمهٔ جدید با مصرف اعتبار API شروع شود؟'))return;element('translate').disabled=true;try{await save();const body={from_lang:current.source_language,to_lang:current.target_language,auto_glossary:element('auto').checked};if(element('model').value.trim())body.model=element('model').value.trim();await request('/api/library/'+bookId+'/translate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});dirty=false;location.href='/'}finally{element('translate').disabled=false}});
})();
</script>'''
