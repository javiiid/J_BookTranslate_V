"""Local dashboard for J Book Translate; run with ``python -m app.web``."""
from __future__ import annotations

import io
import json
import shutil
import threading
import traceback
import uuid
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email import policy
from email.parser import BytesParser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from openai import OpenAI
from app.core.config import read_config
from app.core.models import DEFAULT_MODEL
from app.core.paths import ensure_dir
from app.pipeline.pipeline import translate
from app.translation.prompts import get_default_prompt

UTC = timezone.utc
UPLOAD_DIR = ensure_dir("data") / "uploads"
WEB_OUTPUT_DIR = ensure_dir("output") / "web"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
WEB_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class Job:
    id: str
    filename: str
    input_path: Path
    filetype: str
    file_size: int
    options: dict[str, str]
    status: str = "queued"
    created_at: str = field(default_factory=now)
    started_at: str | None = None
    last_activity: str = field(default_factory=now)
    pipeline_job_id: str | None = None
    paths: dict | None = None
    log: io.StringIO = field(default_factory=io.StringIO)
    stop_event: threading.Event = field(default_factory=threading.Event)
    output_path: Path | None = None
    error: str | None = None
    progress: dict[str, int] = field(default_factory=lambda: {"completed": 0, "total": 0})


JOBS: dict[str, Job] = {}
JOBS_LOCK = threading.RLock()
RUN_LOCK = threading.Lock()


def _safe_filename(name: str) -> str:
    return "".join(char if char.isalnum() or char in "._- " else "_" for char in Path(name).name)


def _friendly_error(error: Exception) -> str:
    text = str(error).lower()
    if "api configuration" in text or "api_key" in text or "api key" in text:
        return "کلید API یا آدرس سرویس در config/config.yaml تنظیم نشده یا معتبر نیست."
    if "401" in text or "unauthorized" in text:
        return "دسترسی API تأیید نشد؛ کلید API را بررسی کنید."
    if "429" in text or "rate limit" in text:
        return "سقف درخواست‌های API پر شده است؛ کمی بعد دوباره ادامه دهید."
    if "timeout" in text or "connection" in text or "network" in text:
        return "ارتباط با سرویس API برقرار نشد. اینترنت و base URL را بررسی کنید."
    return "ترجمه متوقف شد. جزئیات فنی در لاگ در دسترس است."


def _update_progress(job: Job) -> None:
    if not job.paths:
        return
    try:
        chunks = Path(job.paths["chunks_file"])
        translations = Path(job.paths["translations_file"])
        if chunks.exists():
            with chunks.open(encoding="utf-8") as file:
                job.progress["total"] = len(json.load(file).get("chunks", []))
        if translations.exists():
            with translations.open(encoding="utf-8") as file:
                job.progress["completed"] = len(json.load(file))
        job.last_activity = now()
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        pass


def _on_pipeline_started(job: Job, pipeline_job_id: str, paths: dict) -> None:
    with JOBS_LOCK:
        job.pipeline_job_id = pipeline_job_id
        job.paths = {key: str(value) for key, value in paths.items()}
        job.started_at = job.started_at or now()
        job.last_activity = now()


def _run_job(job: Job, *, resume: bool = False) -> None:
    """Run one job; the lock makes simultaneous translations impossible."""
    with RUN_LOCK, redirect_stdout(job.log), redirect_stderr(job.log):
        try:
            job.status = "running"
            job.started_at = job.started_at or now()
            config = read_config().get("openai", {})
            api_key, base_url = config.get("api_key"), config.get("base_url")
            if not api_key or not base_url:
                raise ValueError("API configuration is missing.")
            client = OpenAI(api_key=api_key, base_url=base_url)
            output_name = f"{job.input_path.stem}_{job.options['to_lang'].lower()}_{job.options['model']}.{job.filetype}"
            job.output_path = WEB_OUTPUT_DIR / f"{job.id}_{output_name}"
            prompt = job.options["prompt"] or get_default_prompt(job.options["from_lang"], job.options["to_lang"], job.filetype)
            mode = "resume" if resume else (job.options["mode"] or None)
            print(f"Starting web job {job.id}")
            translate(client=client, input_path=job.input_path, output_path=job.output_path,
                from_lang=job.options["from_lang"], to_lang=job.options["to_lang"], mode=mode,
                model=job.options["model"], fast=mode not in {"batch", "batchcheck", "resumebatch"},
                resume_job_id=job.pipeline_job_id if resume else None, debug=True, filetype=job.filetype,
                translation_prompt=prompt, stop_event=job.stop_event,
                on_job_started=lambda pipeline_id, paths: _on_pipeline_started(job, pipeline_id, paths))
            _update_progress(job)
            job.status = "stopped" if job.stop_event.is_set() else ("completed" if job.output_path.exists() else "finished")
            job.last_activity = now()
            if job.status == "stopped":
                print("Job stopped safely. Use Resume to continue from saved progress.")
        except Exception as exc:
            job.status, job.error, job.last_activity = "failed", _friendly_error(exc), now()
            traceback.print_exc()


def _job_payload(job: Job) -> dict:
    _update_progress(job)
    total, completed = job.progress["total"], job.progress["completed"]
    result = {"id": job.id, "filename": job.filename, "filetype": job.filetype.upper(), "file_size": job.file_size,
        "status": job.status, "created_at": job.created_at, "started_at": job.started_at, "last_activity": job.last_activity,
        "progress": {"completed": completed, "total": total, "percent": round(completed * 100 / total) if total else 0},
        "log": job.log.getvalue(), "error": job.error,
        "can_stop": job.status == "running" and job.options.get("mode") != "batch",
        "can_resume": job.status in {"stopped", "failed", "finished"} and bool(job.pipeline_job_id) and job.filetype == "epub"}
    if job.status == "completed" and job.output_path:
        result["download"] = f"/downloads/{job.id}"
    return result


PAGE = r'''<!doctype html><html lang="fa" dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>J Book Translate</title><style>
@import url('https://fonts.googleapis.com/css2?family=Vazirmatn:wght@400;500;600;700;800&display=swap');:root{--bg:#f4f7fb;--surface:#fff;--ink:#142033;--muted:#6d7a90;--line:#e3e9f2;--blue:#356df6;--purple:#7257e8;--cyan:#0ca6a6;--green:#08966c;--red:#e24a4a;--shadow:0 18px 55px rgba(38,57,93,.08)}*{box-sizing:border-box}body{margin:0;min-height:100vh;background:radial-gradient(circle at 8% 0,#e6efff 0,transparent 32%),radial-gradient(circle at 96% 11%,#eee9ff 0,transparent 27%),var(--bg);font:15px Vazirmatn,Segoe UI,Tahoma,sans-serif;color:var(--ink)}.shell{max-width:1180px;margin:auto;padding:34px 22px 62px}.top{display:flex;align-items:center;justify-content:space-between;gap:18px;margin-bottom:26px}.brand{display:flex;align-items:center;gap:14px}.logo{width:49px;height:49px;border-radius:15px;display:grid;place-items:center;background:linear-gradient(140deg,var(--blue),var(--purple));color:#fff;font-size:25px;box-shadow:0 9px 24px #506ff466}.brand h1{font-size:22px;margin:0;font-weight:800}.brand p{margin:3px 0 0;color:var(--muted);font-size:13px}.api-pill{display:flex;align-items:center;gap:8px;background:#fff;border:1px solid var(--line);border-radius:999px;padding:8px 12px;color:var(--muted);font-size:12px;box-shadow:0 4px 16px #26395a0a}.dot{width:8px;height:8px;border-radius:50%;background:#aeb8c7}.dot.ready{background:var(--green);box-shadow:0 0 0 4px #12b9811b}.dot.error{background:var(--red)}.dashboard{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:20px}.card{background:rgba(255,255,255,.92);border:1px solid rgba(224,230,240,.9);border-radius:20px;box-shadow:var(--shadow)}.form-card{padding:27px}.side{display:grid;gap:20px;align-content:start}.side .card{padding:21px}.section-title{display:flex;justify-content:space-between;align-items:center;margin-bottom:23px}.section-title h2{font-size:18px;margin:0}.step{font-size:12px;color:var(--blue);background:#edf3ff;padding:5px 10px;border-radius:999px}.drop{position:relative;border:1.5px dashed #9ab4eb;background:linear-gradient(135deg,#f8faff,#f0f5ff);border-radius:15px;min-height:136px;display:grid;place-items:center;text-align:center;padding:18px;transition:.2s}.drop.drag{border-color:var(--blue);background:#eaf1ff}.drop input{position:absolute;inset:0;width:100%;opacity:0;cursor:pointer}.upload-icon{font-size:28px;color:var(--blue)}.drop strong{display:block;margin:5px 0 3px}.drop small{color:var(--muted)}.file-info{display:none;margin-top:12px;padding:10px 12px;background:#eff8f5;border-radius:9px;color:#166b55;font-size:13px}.grid2{display:grid;grid-template-columns:1fr 1fr;gap:13px}label{display:block;font-size:13px;font-weight:700;margin:18px 0 7px}input,select,textarea{width:100%;font:inherit;border:1px solid #d9e1ed;border-radius:10px;padding:10px 12px;background:#fff;color:var(--ink)}input:focus,select:focus,textarea:focus{outline:0;border-color:var(--blue);box-shadow:0 0 0 3px #356df61a}textarea{resize:vertical;min-height:100px}.optional{font-weight:400;color:var(--muted)}.advanced{margin-top:17px}.advanced summary{cursor:pointer;color:var(--blue);font-weight:700;font-size:13px}.check{display:flex;align-items:center;gap:8px;color:var(--muted);font-size:13px;margin-top:14px}.check input{width:auto;accent-color:var(--blue)}button{border:0;font:700 14px Vazirmatn,Segoe UI,sans-serif;cursor:pointer;border-radius:10px;padding:12px 15px;transition:.15s}button:hover:not(:disabled){filter:brightness(.97);transform:translateY(-1px)}button:disabled{cursor:not-allowed;opacity:.55}.primary{width:100%;margin-top:21px;color:#fff;background:linear-gradient(135deg,var(--blue),#5a62e8);box-shadow:0 10px 20px #4268d338}.secondary{background:#eef3ff;color:#2d5ed4}.danger{background:#fff0f0;color:#ca3636}.intro{display:flex;gap:11px;line-height:1.8;color:#506078;font-size:13px}.intro i{font-style:normal;display:grid;place-items:center;min-width:34px;height:34px;border-radius:10px;background:#eaf1ff;color:var(--blue)}.fact{display:flex;justify-content:space-between;padding:12px 0;border-bottom:1px solid var(--line);font-size:13px}.fact span{color:var(--muted)}.job{display:none;margin-top:20px;padding:23px}.job-head{display:flex;justify-content:space-between;align-items:flex-start;gap:15px}.job-name{font-weight:800;font-size:16px;word-break:break-word}.job-meta{margin-top:4px;color:var(--muted);font-size:12px}.chip{white-space:nowrap;font-size:12px;font-weight:700;border-radius:999px;padding:6px 10px;background:#f0f3f7;color:#687587}.chip.running{background:#eaf1ff;color:#2b62df}.chip.completed{background:#e6f8f1;color:#087d5c}.chip.stopped,.chip.finished{background:#fff5df;color:#a96b00}.chip.failed{background:#fff0f0;color:#c03636}.progress-row{display:flex;justify-content:space-between;margin:21px 0 8px;font-size:13px;font-weight:700}.progress-track{height:10px;background:#e9eef7;border-radius:99px;overflow:hidden}.progress-value{height:100%;width:0;border-radius:inherit;background:linear-gradient(90deg,var(--blue),var(--cyan));transition:width .45s}.stats{display:grid;grid-template-columns:repeat(3,1fr);gap:9px;margin-top:16px}.stat{background:#f8faff;border:1px solid #edf1f7;border-radius:11px;padding:10px}.stat span{display:block;color:var(--muted);font-size:11px;margin-bottom:3px}.stat strong{font-size:13px}.job-actions{display:flex;flex-wrap:wrap;gap:9px;margin-top:18px}.job-actions button,.download{padding:9px 12px;text-decoration:none;display:inline-block}.download{border-radius:10px;background:var(--green);color:#fff;font-size:13px;font-weight:700}.error{display:none;margin-top:14px;background:#fff2f2;color:#a93434;border:1px solid #ffd9d9;border-radius:10px;padding:11px;font-size:13px}.logs{margin-top:19px}.logs summary{cursor:pointer;color:var(--muted);font-weight:700;font-size:13px}.logs pre{direction:ltr;text-align:left;white-space:pre-wrap;max-height:280px;overflow:auto;background:#101827;color:#c9f8df;border-radius:11px;padding:13px;font:12px ui-monospace,Consolas,monospace}.small{font-size:12px;color:var(--muted)}@media(max-width:850px){.dashboard{grid-template-columns:1fr}.side{grid-template-columns:1fr 1fr}.top{align-items:flex-start}}@media(max-width:570px){.shell{padding:22px 13px}.top{display:block}.api-pill{display:inline-flex;margin-top:14px}.form-card{padding:19px}.grid2,.side,.stats{grid-template-columns:1fr}.job-head{display:block}.chip{display:inline-block;margin-top:10px}}
</style></head><body><main class="shell"><header class="top"><div class="brand"><div class="logo">文</div><div><h1>J Book Translate</h1><p>داشبورد ترجمهٔ امن EPUB و PDF</p></div></div><div class="api-pill"><i class="dot" id="api-dot"></i><span id="api-status">در حال بررسی تنظیمات API…</span><button class="secondary" id="verify-api" style="padding:5px 9px;font-size:11px">بررسی اتصال</button></div></header><div class="dashboard"><section><div class="card form-card"><div class="section-title"><h2>ترجمهٔ جدید</h2><span class="step">گام ۱ از ۱</span></div><form id="translate-form"><div class="drop" id="drop"><input required type="file" id="book" name="book" accept=".epub,.pdf"><div><div class="upload-icon">⇧</div><strong>کتاب را اینجا رها کنید یا انتخاب کنید</strong><small>فرمت‌های EPUB و PDF تا حداکثر ۱ گیگابایت</small></div></div><div class="file-info" id="file-info"></div><div class="grid2"><div><label>زبان مبدأ</label><input name="from_lang" value="EN" maxlength="12"></div><div><label>زبان مقصد</label><input name="to_lang" value="FA" maxlength="12"></div></div><div class="grid2"><div><label>مدل ترجمه</label><input name="model" value="__DEFAULT_MODEL__"></div><div><label>حالت اجرا</label><select name="mode"><option value="">سریع (پیشنهادی)</option><option value="batch">Batch</option><option value="pdfbilingual">PDF دوزبانه</option></select></div></div><details class="advanced"><summary>تنظیمات پیشرفته و دستور ترجمه</summary><label>دستور ترجمه <span class="optional">(اختیاری)</span></label><textarea name="prompt" placeholder="خالی بگذارید تا دستور استاندارد برنامه استفاده شود."></textarea><label class="check"><input type="checkbox" name="debug" value="true" checked>نگهداری فایل‌های موقت برای ادامهٔ امن کار</label></details><button class="primary" id="submit" type="submit">شروع ترجمه</button></form></div><section class="card job" id="job"><div class="job-head"><div><div class="job-name" id="job-name"></div><div class="job-meta" id="job-meta"></div></div><span class="chip" id="chip">در انتظار</span></div><div class="progress-row"><span id="progress-label">در حال آماده‌سازی…</span><span id="percent">۰٪</span></div><div class="progress-track"><div class="progress-value" id="progress"></div></div><div class="stats"><div class="stat"><span>Chunk تکمیل‌شده</span><strong id="completed">۰</strong></div><div class="stat"><span>زمان شروع</span><strong id="started">—</strong></div><div class="stat"><span>آخرین فعالیت</span><strong id="activity">—</strong></div></div><div class="error" id="error"></div><div class="job-actions"><button class="danger" hidden id="stop">توقف امن</button><button class="secondary" hidden id="resume">ادامهٔ ترجمه</button><a class="download" hidden id="download">دریافت خروجی</a></div><details class="logs"><summary>نمایش لاگ فنی</summary><pre id="log"></pre></details></section></section><aside class="side"><div class="card"><div class="section-title"><h2>پیش از شروع</h2></div><div class="intro"><i>✓</i><div>کلید API هرگز به مرورگر ارسال یا در صفحه نمایش داده نمی‌شود. فایل‌ها فقط روی همین دستگاه پردازش می‌شوند.</div></div></div><div class="card"><div class="section-title"><h2>تنظیمات فعال</h2></div><div class="fact"><span>محدودهٔ اجرا</span><strong>فقط محلی</strong></div><div class="fact"><span>ذخیرهٔ پیشرفت</span><strong>بعد از هر chunk</strong></div><div class="fact"><span>ادامهٔ کار</span><strong>برای EPUB</strong></div><p class="small">برای توقف امن، درخواست در حال اجرا تمام و ذخیره می‌شود؛ سپس ترجمه پیش از chunk بعدی متوقف خواهد شد.</p></div></aside></div></main><script>
const $=s=>document.querySelector(s),form=$('#translate-form'),submit=$('#submit'),jobBox=$('#job'),drop=$('#drop'),book=$('#book'),fileInfo=$('#file-info'),apiDot=$('#api-dot'),apiStatus=$('#api-status');let jobId,timer;const fa=n=>new Intl.NumberFormat('fa-IR').format(n||0),date=v=>v?new Intl.DateTimeFormat('fa-IR',{hour:'2-digit',minute:'2-digit',year:'numeric',month:'short',day:'numeric'}).format(new Date(v)):'—',size=n=>n<1024*1024?(n/1024).toFixed(0)+' KB':(n/1024/1024).toFixed(1)+' MB';function fileChanged(){const f=book.files[0];if(!f){fileInfo.style.display='none';return}fileInfo.textContent=`${f.name} · ${f.name.split('.').pop().toUpperCase()} · ${size(f.size)}`;fileInfo.style.display='block'}book.addEventListener('change',fileChanged);['dragenter','dragover'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.add('drag')}));['dragleave','drop'].forEach(e=>drop.addEventListener(e,x=>{x.preventDefault();drop.classList.remove('drag')}));async function health(verify=false){try{const r=await fetch('/api/health'+(verify?'?verify=1':'')),d=await r.json();apiStatus.textContent=d.message;apiDot.className='dot '+(d.status==='ready'?'ready':'error')}catch{apiStatus.textContent='وضعیت API نامشخص است';apiDot.className='dot error'}}$('#verify-api').onclick=()=>health(true);health();form.addEventListener('submit',async e=>{e.preventDefault();if(!book.files[0])return;submit.disabled=true;submit.textContent='در حال ایجاد کار…';try{const r=await fetch('/api/jobs',{method:'POST',body:new FormData(form)}),d=await r.json();if(!r.ok)throw Error(d.error||'ایجاد job ناموفق بود');jobId=d.id;jobBox.style.display='block';$('#error').style.display='none';watch()}catch(err){alert(err.message);submit.disabled=false;submit.textContent='شروع ترجمه'}});async function action(name){if(!jobId)return;const r=await fetch(`/api/jobs/${jobId}/${name}`,{method:'POST'}),d=await r.json();if(!r.ok)alert(d.error||'عملیات انجام نشد');watch()}$('#stop').onclick=()=>action('stop');$('#resume').onclick=()=>action('resume');function render(d){const p=d.progress;$('#job-name').textContent=d.filename;$('#job-meta').textContent=`${d.filetype} · ${size(d.file_size)} · ${d.id}`;$('#chip').textContent={queued:'در صف',running:'در حال ترجمه',stopping:'در حال توقف',stopped:'متوقف شده',completed:'تکمیل شد',finished:'پایان یافت',failed:'خطا'}[d.status]||d.status;$('#chip').className='chip '+d.status;$('#progress').style.width=p.percent+'%';$('#percent').textContent=fa(p.percent)+'٪';$('#progress-label').textContent=p.total?`${fa(p.completed)} از ${fa(p.total)} chunk`:'در حال آماده‌سازی chunkها…';$('#completed').textContent=p.total?`${fa(p.completed)} / ${fa(p.total)}`:fa(p.completed);$('#started').textContent=date(d.started_at);$('#activity').textContent=date(d.last_activity);$('#log').textContent=d.log||'در انتظار شروع…';const error=$('#error');error.textContent=d.error||'';error.style.display=d.error?'block':'none';$('#stop').hidden=!d.can_stop;$('#resume').hidden=!d.can_resume;const dl=$('#download');dl.hidden=!d.download;if(d.download)dl.href=d.download;const active=['queued','running','stopping'].includes(d.status);if(!active){clearInterval(timer);submit.disabled=false;submit.textContent='شروع ترجمه'}}function watch(){clearInterval(timer);const tick=async()=>{try{const r=await fetch('/api/jobs/'+jobId),d=await r.json();if(!r.ok)throw Error();render(d)}catch{clearInterval(timer)}};tick();timer=setInterval(tick,1000)}
</script></body></html>'''.replace("__DEFAULT_MODEL__", DEFAULT_MODEL)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None: return
    def _json(self, payload: dict, status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data)
    def _job(self, job_id: str) -> Job | None:
        with JOBS_LOCK: return JOBS.get(job_id)
    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            data = PAGE.encode("utf-8"); self.send_response(HTTPStatus.OK); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(data))); self.end_headers(); self.wfile.write(data); return
        if parsed.path == "/api/health":
            try:
                config = read_config().get("openai", {})
                if not config.get("api_key") or not config.get("base_url"): raise ValueError("API configuration is missing.")
                if "verify=1" in parsed.query: OpenAI(api_key=config["api_key"], base_url=config["base_url"]).models.list(); message = "اتصال API برقرار است"
                else: message = "تنظیمات API آماده است"
                self._json({"status":"ready","message":message}); return
            except Exception as exc: self._json({"status":"error","message":_friendly_error(exc)}); return
        if parsed.path.startswith("/api/jobs/") and parsed.path.count("/") == 3:
            job=self._job(parsed.path.rsplit("/",1)[-1])
            if not job: self._json({"error":"کار موردنظر پیدا نشد."},404); return
            self._json(_job_payload(job)); return
        if parsed.path.startswith("/downloads/"):
            job=self._job(parsed.path.rsplit("/",1)[-1])
            if not job or not job.output_path or not job.output_path.is_file(): self.send_error(404); return
            self.send_response(200); self.send_header("Content-Type","application/octet-stream"); self.send_header("Content-Disposition",f'attachment; filename="{job.output_path.name}"'); self.send_header("Content-Length",str(job.output_path.stat().st_size)); self.end_headers()
            with job.output_path.open("rb") as output: shutil.copyfileobj(output,self.wfile)
            return
        self.send_error(404)
    def do_POST(self) -> None:
        path=urlparse(self.path).path
        if path.startswith("/api/jobs/") and path.endswith("/stop"):
            job=self._job(path.split("/")[-2])
            if not job or job.status!="running": self._json({"error":"این کار قابل توقف نیست."},400); return
            if job.options.get("mode")=="batch": self._json({"error":"Batch پس از ارسال به سرویس متوقف نمی‌شود."},400); return
            job.status="stopping"; job.stop_event.set(); job.last_activity=now(); self._json({"ok":True}); return
        if path.startswith("/api/jobs/") and path.endswith("/resume"):
            job=self._job(path.split("/")[-2])
            if not job or job.filetype!="epub" or not job.pipeline_job_id or job.status not in {"stopped","failed","finished"}: self._json({"error":"این کار قابل ادامه نیست."},400); return
            if RUN_LOCK.locked(): self._json({"error":"یک ترجمهٔ دیگر در حال اجراست."},409); return
            job.stop_event=threading.Event(); job.status="queued"; job.error=None; job.last_activity=now(); threading.Thread(target=_run_job,args=(job,),kwargs={"resume":True},daemon=True).start(); self._json({"ok":True},202); return
        if path!="/api/jobs": self.send_error(404); return
        with JOBS_LOCK:
            if any(item.status in {"queued","running","stopping"} for item in JOBS.values()): self._json({"error":"تا پایان یا توقف ترجمهٔ فعلی، شروع هم‌زمان غیرفعال است."},409); return
        content_type=self.headers.get("Content-Type","")
        if "multipart/form-data" not in content_type: self._json({"error":"فرم آپلود نامعتبر است."},400); return
        try:
            size=int(self.headers.get("Content-Length","0"))
            if not 0<size<=1024*1024*1024: raise ValueError("فایل خالی است یا بیش از ۱ گیگابایت حجم دارد.")
            message=BytesParser(policy=policy.default).parsebytes(f"Content-Type: {content_type}\r\nMIME-Version: 1.0\r\n\r\n".encode()+self.rfile.read(size)); fields,upload_name,upload_data={},"",b""
            for part in message.iter_parts():
                name=part.get_param("name",header="content-disposition")
                if not name: continue
                payload=part.get_payload(decode=True) or b""
                if part.get_filename(): upload_name,upload_data=part.get_filename(),payload
                else: fields[name]=payload.decode("utf-8",errors="replace")
        except (ValueError,OSError) as exc: self._json({"error":str(exc)},400); return
        filename=_safe_filename(upload_name); suffix=Path(filename).suffix.lower()
        if not filename or suffix not in {".epub",".pdf"}: self._json({"error":"فقط فایل EPUB یا PDF قابل پذیرش است."},400); return
        job_id=uuid.uuid4().hex[:12]; input_path=UPLOAD_DIR/f"{job_id}_{filename}"; input_path.write_bytes(upload_data)
        options={key:fields.get(key,"").strip() for key in ("from_lang","to_lang","model","mode","prompt","debug")}; options["from_lang"]=options["from_lang"] or "EN"; options["to_lang"]=options["to_lang"] or "FA"; options["model"]=options["model"] or DEFAULT_MODEL
        job=Job(job_id,filename,input_path,suffix.lstrip("."),len(upload_data),options)
        with JOBS_LOCK: JOBS[job_id]=job
        threading.Thread(target=_run_job,args=(job,),daemon=True).start(); self._json({"id":job_id},201)


def main() -> None:
    print("J Book Translate UI: http://127.0.0.1:8765")
    ThreadingHTTPServer(("127.0.0.1",8765),Handler).serve_forever()


if __name__ == "__main__": main()
