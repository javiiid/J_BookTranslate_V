# J Book Translate

یک ابزار محلی برای ترجمهٔ کتاب‌های EPUB و PDF با APIهای سازگار با OpenAI است. برنامه ترجمه را به بخش‌های کوچک تقسیم می‌کند، پیشرفت را روی دیسک نگه می‌دارد و پس از توقف یا راه‌اندازی مجدد می‌تواند کار را ادامه دهد.

## امکانات

- ترجمهٔ EPUB و PDF در حالت سریع یا Batch
- توقف امن، ادامهٔ ترجمه و بازیابی Jobها بعد از راه‌اندازی مجدد
- داشبورد وب برای مشاهدهٔ کارهای فعال و اخیر
- کتابخانهٔ محلی، Reader داخلی و تنظیمات مطالعه
- واژه‌نامهٔ دستی و ساخت خودکار واژه‌نامه برای هر کتاب
- حفظ نام شخصیت‌ها و اصطلاحات در طول ترجمه
- خروجی PDF دوزبانه
- فونت محلی Vazirmatn و رابط فارسی بدون وابستگی به CDN

> ساخت خودکار واژه‌نامه ممکن است درخواست‌های اضافه به API ارسال کند و هزینهٔ مصرف مدل را افزایش دهد.

## نصب

پروژه برای Windows و Python 3.11 یا جدیدتر طراحی شده است.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

فایل `config/config.yaml` را ایجاد کنید:

```yaml
openai:
  api_key: "YOUR_API_KEY"
  base_url: "https://api.example.com/v1"

translation:
  default_model: "gpt-5.6-luna"
  default_from_lang: "EN"
  default_to_lang: "FA"
  temperature: 0.2
  max_retries: 5
  retry_delay: 5
  max_retry_delay: 60
```

کلید API و فایل‌های تنظیمات خصوصی را commit نکنید.

## اجرای رابط وب

```powershell
python -m app.web
```

سپس آدرس `http://127.0.0.1:8765` را باز کنید. بخش «کارهای من» وضعیت Jobهای فعال و اخیر را نگه می‌دارد؛ بنابراین با جابه‌جایی بین صفحات، روند ترجمه گم نمی‌شود.

## اجرای خط فرمان

ترجمهٔ معمولی:

```powershell
python -m app.main --input ".\books\source.epub" --from-lang EN --to-lang FA
```

ادامهٔ یک ترجمه:

```powershell
python -m app.main --input ".\books\source.epub" --from-lang EN --to-lang FA --mode resume
```

ترجمهٔ Batch یا PDF دوزبانه:

```powershell
python -m app.main --input ".\books\source.epub" --mode batch
python -m app.main --input ".\books\source.pdf" --mode pdfbilingual
```

برای مشاهدهٔ همهٔ گزینه‌ها از `python -m app.main --help` استفاده کنید.

## واژه‌نامه

واژه‌نامه به هر کتاب متصل است و شامل اصطلاح مبدأ، ترجمهٔ ثابت، نوع و توضیحات می‌شود. هنگام شروع ترجمه از کتابخانه می‌توانید ساخت خودکار واژه‌نامه را فعال یا غیرفعال کنید. Snapshot واژه‌نامه داخل پوشهٔ Job ذخیره می‌شود تا ادامهٔ ترجمه با همان اصطلاحات انجام شود.

## ساختار پروژه

```text
app/core/         تنظیمات، مدل‌ها، retry و ابزارهای مشترک
app/pipeline/     پردازش EPUB و PDF
app/translation/ موتور ترجمه و Batch
app/jobs/         Jobها، state، داشبورد و بازیابی
app/library/      کتابخانه و فایل‌های فونت
app/glossary/     واژه‌نامهٔ دستی و خودکار
app/reader/       Reader کتاب‌های ترجمه‌شده
app/storage/      دیتابیس محلی
tests/            تست‌های pytest
data/             داده‌ها و metadata محلی
temp/             state قابل‌بازیابی Jobها
output/           خروجی کتاب‌ها
```

## تست

```powershell
python -m pytest -q
```

برای اجرای یک بخش مشخص:

```powershell
python -m pytest tests/test_jobs_dashboard.py -q
python -m pytest tests/test_reader.py tests/test_reader_bilingual.py -q
```

در محیط‌هایی که پوشهٔ موقت سیستم محدود است:

```powershell
python -m pytest -q -p no:cacheprovider --basetemp .test-tmp\full
```

## توسعه

راهنمای ساختار، نام‌گذاری، تست و Pull Request در `AGENTS.md` قرار دارد. تغییرات باید کوچک، قابل‌بازیابی و همراه با تست باشند. فایل‌های `data/`، `temp/`، `output/`، کلیدهای API و خروجی‌های تولیدشده نباید وارد Git شوند.

## وضعیت پروژه

هستهٔ ترجمه، ادامهٔ Job، کتابخانه، واژه‌نامه، Reader و داشبورد فعال‌اند. پروژه همچنان در حال توسعه است و پیش از انتشار عمومی باید مجوز نرم‌افزار، تست مرورگر و بسته‌بندی نهایی تکمیل شود.
