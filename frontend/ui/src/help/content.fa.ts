/**
 * Persian help content. The default language; `content.en.ts` mirrors the
 * same slugs so switching language never breaks a link.
 *
 * Button names and route paths below are quoted character-for-character
 * from the UI and `App.tsx`. If the UI renames something, update the
 * article in the same change -- `tests/help.test.ts` holds the slugs,
 * not the prose.
 */
import type { HelpArticle, HelpFaq, HelpVideo } from '../lib/help.ts'

/** The day this text was written and reviewed against the real UI. */
const REVIEWED_AT = '2026-10-09'

export const helpArticlesFa: HelpArticle[] = [
  {
    id: 'first-translation',
    slug: 'first-translation',
    title: 'نخستین ترجمه، قدم‌به‌قدم',
    summary: 'از انتخاب فایل تا شروع ترجمهٔ کامل: چهار قدم که پیش از خرج کردن چیزی می‌بینید.',
    category: 'getting-started',
    keywords: ['شروع', 'اولین', 'آپلود', 'کارگاه', 'کالیبراسیون', 'start', 'upload'],
    sections: [
      {
        id: 'steps',
        heading: 'مراحل',
        blocks: [
          {
            kind: 'steps',
            items: [
              'در صفحهٔ «افزودن کتاب» فایل EPUB یا PDF را انتخاب کنید. انتخاب فایل هزینه‌ای ندارد.',
              'برنامه کتاب را می‌خواند و یک کارگاه کالیبراسیون باز می‌کند؛ لحن، مدل و واژه‌نامه را روی ۱ تا ۳ نمونهٔ واقعی همان کتاب می‌سنجید.',
              'نمونه‌ها را تولید و تأیید کنید و پروفایل را قفل کنید؛ بخش‌های تأییدشده با همان تنظیمات دوباره هزینه نمی‌شوند.',
              'ترجمهٔ کامل را شروع کنید و پیشرفت را در صفحهٔ «پایش ترجمه» ببینید؛ هر بخش که آماده شد روی دیسک ثبت می‌شود.',
            ],
          },
        ],
      },
      {
        id: 'expect',
        heading: 'نتیجهٔ مورد انتظار',
        blocks: [
          {
            kind: 'paragraph',
            text: 'پیش از شروع، برآورد هزینه و زمان را با بازهٔ تقریبی می‌بینید. پس از پایان، خروجی اصلی در تب «فایل‌ها» و کتاب دوزبانه در «کتابخانه» آمادهٔ مطالعه است.',
          },
        ],
      },
      {
        id: 'stuck',
        heading: 'اگر به مشکل خوردید',
        blocks: [
          {
            kind: 'paragraph',
            text: 'اگر کارگاه باز نشد، مقالهٔ «فایل من پذیرفته نشد» را ببینید. اگر خطای سرویس ترجمه گرفتید، مقالهٔ «خطای اتصال و کندی» را بخوانید؛ پیشرفت ذخیره‌شده از بین نمی‌رود.',
          },
        ],
      },
    ],
    relatedSlugs: ['provider-setup', 'calibration-samples', 'stop-resume'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'provider-setup',
    slug: 'provider-setup',
    title: 'تنظیم سرویس ترجمه',
    summary: 'کلید و آدرس سرویس سازگار با OpenAI را کجا وارد کنید و چطور از کارکردنش مطمئن شوید.',
    category: 'getting-started',
    keywords: ['کلید', 'api', 'base_url', 'سرویس', 'provider', 'اتصال', 'تست'],
    sections: [
      {
        id: 'where',
        heading: 'کلید کجا زندگی می‌کند',
        blocks: [
          {
            kind: 'paragraph',
            text: 'کلید فقط در فایل config/config.yaml است و هرگز در گیت ثبت نمی‌شود. در رابط وب، بخش «تنظیمات سرویس ترجمه» در «پنل کاربری» همان مقادیر را نشان می‌دهد و دکمهٔ تست، اتصال واقعی به سرویس را بررسی می‌کند.',
          },
          {
            kind: 'note',
            text: 'آدرس سازگار معمولاً باید به ‎/v1‎ ختم شود. تست موفق یعنی کلید پذیرفته شده و مدل انتخابی در فهرست خود سرویس هم هست.',
          },
        ],
      },
      {
        id: 'fix401',
        heading: 'اگر تست ناموفق بود',
        blocks: [
          {
            kind: 'steps',
            items: [
              'خطای ۴۰۱ یعنی کلید پذیرفته نشد؛ کلید را دوباره از سرویس بگیرید و جای‌گذاری کنید.',
              'خطای ۴۰۴ یعنی آدرس یا مدل پیدا نشد؛ ‎/v1‎ انتهای آدرس و نام دقیق مدل را بررسی کنید.',
              'اگر روی ویندوز خطای دسترسی شبکه گرفتید، برنامه را در فایروال مجاز کنید.',
            ],
          },
        ],
      },
    ],
    relatedSlugs: ['first-translation', 'models-languages', 'connection-errors'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'file-formats',
    slug: 'file-formats',
    title: 'فایل من پذیرفته نشد',
    summary: 'کدام ورودی‌ها پذیرفته می‌شوند و محدودیت‌های صادقانهٔ هر کدام چیست.',
    category: 'getting-started',
    keywords: ['فرمت', 'epub', 'pdf', 'txt', 'zip', 'نجات', 'rescue', 'ocr', 'اسکن'],
    sections: [
      {
        id: 'accepted',
        heading: 'ورودی‌های پذیرفته‌شده',
        blocks: [
          {
            kind: 'paragraph',
            text: 'برای ترجمه: EPUB و PDF و TXT. برای ادامهٔ کار نیمه‌تمام: فایل ZIP نسخهٔ نجات. برای تبدیل بدون ترجمه: EPUB، PDF متنی، SRT، TXT و Markdown.',
          },
        ],
      },
      {
        id: 'limits',
        heading: 'محدودیت‌های واقعی',
        blocks: [
          {
            kind: 'warning',
            text: 'PDF اسکن‌شده به OCR نیاز دارد و OCR در این نسخه فعال نیست؛ هر PDF به‌صورت تصویر پردازش می‌شود. فصل‌های EPUB با کدگذاری غیر UTF-8 فعلاً بی‌صدا رد می‌شوند.',
          },
          {
            kind: 'paragraph',
            text: 'اگر فایل شما از این جنس است، آن را به EPUB با متن تمیز تبدیل کنید یا نسخهٔ متنی PDF را بدهید و نتیجه را در کارگاه روی نمونه‌ها بررسی کنید.',
          },
        ],
      },
    ],
    relatedSlugs: ['first-translation', 'convert-export'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'models-languages',
    slug: 'models-languages',
    title: 'انتخاب مدل و زبان',
    summary: 'مدل پیش‌فرض از کجا می‌آید، مدل ناشناخته چه می‌شود و کدام زبان‌ها پشتیبانی می‌شوند.',
    category: 'translation-jobs',
    keywords: ['مدل', 'model', 'زبان', 'language', 'luna', 'terra', 'gemini'],
    sections: [
      {
        id: 'default',
        heading: 'مدل پیش‌فرض',
        blocks: [
          {
            kind: 'paragraph',
            text: 'مدل پیش‌فرض فقط از فایل config/config.yaml خوانده می‌شود. اگر فیلد مدل را خالی بگذارید، همان مقدار پیکربندی استفاده می‌شود؛ نیازی به حفظ کردن نام مدل نیست.',
          },
          {
            kind: 'note',
            text: 'مدل ناشناخته خطای ۴۰۰ می‌گیرد و ترجمه شروع نمی‌شود؛ یعنی به‌جای صورت‌حساب غافلگیرکننده، همان اول مطلع می‌شوید.',
          },
        ],
      },
      {
        id: 'langs',
        heading: 'زبان‌ها',
        blocks: [
          {
            kind: 'paragraph',
            text: 'انگلیسی، فارسی، عربی، فرانسوی، آلمانی، اسپانیایی، ایتالیایی، روسی، ترکی، چینی، ژاپنی و کره‌ای — در هر دو جهت مبدأ و مقصد.',
          },
        ],
      },
    ],
    relatedSlugs: ['provider-setup', 'calibration-samples'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'job-statuses',
    slug: 'job-statuses',
    title: 'مشاهدهٔ پیشرفت و معنای وضعیت‌ها',
    summary: 'هشت وضعیت کار یعنی چه و پنج تب صفحهٔ پایش هر کدام چه نشان می‌دهند.',
    category: 'translation-jobs',
    keywords: ['وضعیت', 'status', 'پایش', 'monitor', 'پیشرفت', 'progress', 'queued', 'running'],
    sections: [
      {
        id: 'statuses',
        heading: 'وضعیت‌ها',
        blocks: [
          {
            kind: 'paragraph',
            text: '«در صف» یعنی نوبت شروع نرسیده؛ «در حال ترجمه» یعنی بخش‌ها در حال ارسال‌اند؛ «در حال توقف» یعنی توقف خواسته شده و در نقطهٔ امن بعدی می‌ایستد؛ «متوقف‌شده» یعنی می‌توانید ادامه دهید؛ «تکمیل‌شده» یعنی همهٔ بخش‌ها ثبت شده‌اند؛ «خطادار» و «لغوشده» نیازمند بررسی‌اند.',
          },
        ],
      },
      {
        id: 'tabs',
        heading: 'پنج تب پایش',
        blocks: [
          {
            kind: 'paragraph',
            text: 'صفحهٔ هر کار پنج تب دارد: «خلاصه» برای اعداد کلی و خروجی‌ها، «بخش‌ها» برای جست‌وجو در chunkها، «کیفیت» برای بخش‌های پرچم‌دار، «لاگ» برای رویدادهای فنی و «فایل‌ها» برای دانلود.',
          },
        ],
      },
    ],
    relatedSlugs: ['stop-resume', 'first-translation'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'stop-resume',
    slug: 'stop-resume',
    title: 'توقف، لغو و ادامهٔ ترجمه',
    summary: 'تفاوت توقف و لغو، ادامه از آخرین نقطهٔ سالم و تنها معاوضه‌ای که باید بدانید.',
    category: 'translation-jobs',
    keywords: ['توقف', 'stop', 'ادامه', 'resume', 'لغو', 'cancel', 'نجات', 'rescue'],
    sections: [
      {
        id: 'prereq',
        heading: 'پیش‌نیاز',
        blocks: [
          {
            kind: 'paragraph',
            text: 'کافی است کار شما در فهرست «پایش ترجمه» باشد؛ شناسهٔ کار لازم نیست، از همان ردیف اقدام کنید.',
          },
        ],
      },
      {
        id: 'actions',
        heading: 'سه اقدام و معنای هر کدام',
        blocks: [
          {
            kind: 'steps',
            items: [
              '«توقف»: ترجمه در نقطهٔ امن بعدی می‌ایستد و بعداً با «ادامه» از همان‌جا جلو می‌رود.',
              '«ادامه»: ترجمه از آخرین بخش سالمِ ثبت‌شده روی دیسک ادامه پیدا می‌کند؛ حتی بعد از خاموش‌شدن کامپیوتر.',
              '«لغو»: کل کار لغو می‌شود و پیشرفت نادیده گرفته می‌شود. پیش از آن نسخهٔ نجات (ZIP) بگیرید اگر ممکن است به آن نیاز داشته باشید.',
            ],
          },
          {
            kind: 'warning',
            text: 'در بالاترین هم‌روندی، توقف دستی ممکن است تا ۱۲ درخواستِ ارسال‌شده را بی‌نتیجه بگذارد؛ اما هیچ بخشی اشتباه «کامل» علامت نمی‌خورد و ادامه همیشه امن است.',
          },
        ],
      },
      {
        id: 'stuck',
        heading: 'اگر ادامه کار نکرد',
        blocks: [
          {
            kind: 'paragraph',
            text: 'اول کلید سرویس ترجمه را در «پنل کاربری» تست کنید؛ بیشتر ادامه‌های ناموفق از اعتبار کلید است. اگر خطا ماند، مقالهٔ «خطای اتصال و کندی» را بخوانید.',
          },
        ],
      },
    ],
    relatedSlugs: ['job-statuses', 'connection-errors'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'glossary-workflow',
    slug: 'glossary-workflow',
    title: 'واژه‌نامهٔ کتاب و اصطلاحات یکسان',
    summary: 'پیشنهاد، بازبینی شما، تأیید و قفل: چرا هیچ اصطلاحی وسط کار اضافه نمی‌شود.',
    category: 'glossary',
    keywords: ['واژه‌نامه', 'glossary', 'اصطلاح', 'term', 'تأیید', 'پیشنهاد', 'قفل'],
    sections: [
      {
        id: 'flow',
        heading: 'گردش کار',
        blocks: [
          {
            kind: 'steps',
            items: [
              'دکمهٔ «پیشنهاد اصطلاحات» را بزنید: ۱۲ بخش از سراسر کتاب با فقط ۱ درخواست مدل خوانده می‌شود.',
              'در جدول بازبینی هر ردیف را تیک بزنید، معادل را اصلاح کنید یا رد کنید؛ بعد «تأیید انتخاب‌شده‌ها» را بزنید.',
              'با شروع ترجمه، واژه‌نامه قفل (snapshot) می‌شود؛ پس بخش اول و بخش سیصدم با یک نسخه ترجمه می‌شوند.',
            ],
          },
        ],
      },
      {
        id: 'guarantees',
        heading: 'دو تضمین',
        blocks: [
          {
            kind: 'paragraph',
            text: 'اول: هر پیشنهادی باید عیناً در متن نمونه باشد، وگرنه سمت سرور دور ریخته می‌شود؛ واژه‌نامهٔ توهمی وارد ترجمه نمی‌شود. دوم: حالت پیش‌فرض «بدون یادگیری خودکار» است؛ حین ترجمه چیزی اضافه نمی‌شود.',
          },
        ],
      },
    ],
    relatedSlugs: ['calibration-samples', 'first-translation'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'calibration-samples',
    slug: 'calibration-samples',
    title: 'کارگاه کالیبراسیون و لحن ترجمه',
    summary: '۱ تا ۳ نمونهٔ واقعی، چهار لحن، مدل پیشنویس و نهایی، و معنای قفل پروفایل.',
    category: 'translation-jobs',
    keywords: ['کالیبراسیون', 'calibration', 'کارگاه', 'لحن', 'tone', 'نمونه', 'پروفایل', 'قفل'],
    sections: [
      {
        id: 'tones',
        heading: 'چهار لحن',
        blocks: [
          {
            kind: 'paragraph',
            text: '«روان و امروزی»، «ادبی و تمثیلی»، «آکادمیک و تخصصی» و «وفادار و نزدیک به متن». تغییر لحن، نمونهٔ باز را با مدل نهایی بازتولید می‌کند تا همان چیزی را ببینید که کتاب با آن ترجمه می‌شود.',
          },
        ],
      },
      {
        id: 'models',
        heading: 'مدل پیشنویس و نهایی',
        blocks: [
          {
            kind: 'paragraph',
            text: 'پیشنویس برای مقایسهٔ ارزان است؛ ترجمهٔ کامل کتاب همیشه با مدل نهایی انجام می‌شود. پیش از قفل پروفایل، همهٔ نمونه‌ها باید با مدل نهایی تولید و تأیید شده باشند.',
          },
          {
            kind: 'warning',
            text: 'تأیید چند نمونه تضمین کیفیت همهٔ کتاب نیست؛ خروجی نهایی را بازبینی کنید.',
          },
        ],
      },
    ],
    relatedSlugs: ['glossary-workflow', 'models-languages', 'first-translation'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'library-reader',
    slug: 'library-reader',
    title: 'کتابخانه و مطالعهٔ دوزبانه',
    summary: 'جست‌وجو در کتاب‌ها، ادامه از آخرین بخش و خواندن کنار متن اصلی با حالت شب.',
    category: 'library-reading',
    keywords: ['کتابخانه', 'library', 'مطالعه', 'reader', 'خواندن', 'شب', 'جست‌وجو'],
    sections: [
      {
        id: 'library',
        heading: 'کتابخانه',
        blocks: [
          {
            kind: 'paragraph',
            text: '«کتابخانه» همهٔ کتاب‌ها را با پیشرفت هر کدام نشان می‌دهد؛ با جست‌وجوی نام، نویسنده یا مدل. کارت «ادامه از آخرین بخش» نزدیک‌ترین کتاب ناتمام را جلو می‌آورد.',
          },
        ],
      },
      {
        id: 'reader',
        heading: 'مطالعه',
        blocks: [
          {
            kind: 'paragraph',
            text: 'دکمهٔ «مطالعهٔ دوزبانه» متن اصلی و ترجمه را کنار هم باز می‌کند؛ حالت مطالعهٔ شب برای خواندن طولانی مناسب است. اندازهٔ قلم و تنظیمات خواندن در همان صفحهٔ مطالعه است.',
          },
        ],
      },
    ],
    relatedSlugs: ['convert-export', 'persian-display'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'convert-export',
    slug: 'convert-export',
    title: 'تبدیل فایل و دریافت خروجی‌ها',
    summary: '۹ قالب خروجی، تبدیل بدون ترجمه و چیزهایی که این نسخه ندارد.',
    category: 'convert-export',
    keywords: ['تبدیل', 'convert', 'خروجی', 'output', 'دانلود', 'download', 'docx', 'srt', 'markdown'],
    sections: [
      {
        id: 'formats',
        heading: 'قالب‌ها',
        blocks: [
          {
            kind: 'paragraph',
            text: 'EPUB ترجمه‌شده، PDF ترجمه‌شده، PDF دوزبانه، Word، Markdown، متن دوزبانه، قطعات JSON، زیرنویس SRT و گزارش کیفیت. صفحهٔ «تبدیل فایل» همین‌ها را بدون مصرف مدل ترجمه می‌سازد؛ تا رسیدن نتیجه زبانه را نبندید.',
          },
        ],
      },
      {
        id: 'limits',
        heading: 'محدودیت‌های واقعی',
        blocks: [
          {
            kind: 'warning',
            text: 'محتوای کامل SRT هنوز در مسیر تکمیل است؛ تبدیل گروهی، OCR، خروجی EPUB، انتخاب بازهٔ صفحات و تاریخچهٔ دائمی در این نسخه ارائه نمی‌شوند. خروجی تولیدنشده در نتیجه جداگانه مشخص می‌شود.',
          },
        ],
      },
      {
        id: 'stuck',
        heading: 'اگر خروجی پیدا نشد',
        blocks: [
          {
            kind: 'paragraph',
            text: 'اول تب «فایل‌ها» در صفحهٔ همان کار را ببینید؛ اگر خالی بود وضعیت کار را بررسی کنید: کار ناتمام هنوز خروجی نهایی ندارد. فایل‌های دانلودشده را هم در پوشهٔ خروجی برنامه جست‌وجو کنید.',
          },
        ],
      },
    ],
    relatedSlugs: ['file-formats', 'library-reader'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'persian-display',
    slug: 'persian-display',
    title: 'مشکل نمایش فارسی و متن ترکیبی',
    summary: 'فونت، اعداد و کد، جدول‌ها و خواندن متن دوزبانه بدون به‌هم‌ریختگی.',
    category: 'troubleshooting',
    keywords: ['فارسی', 'فونت', 'font', 'نمایش', 'جدول', 'کد', 'rtl', 'به‌هم‌ریختگی'],
    sections: [
      {
        id: 'facts',
        heading: 'آنچه برنامه خودش رعایت می‌کند',
        blocks: [
          {
            kind: 'paragraph',
            text: 'فونت فارسی از همین برنامه می‌آید و به اینترنت وابسته نیست؛ اگر حروف جدا یا ناخوانا دیدید، اول کش مرورگر را بازآوری کنید. اعداد، مسیرها و کد همیشه چپ‌به‌راست نمایش داده می‌شوند تا ترتیبشان به‌هم نریزد.',
          },
        ],
      },
      {
        id: 'font',
        heading: 'اگر فونت ناخوانا شد',
        blocks: [
          {
            kind: 'steps',
            items: [
              'کش مرورگر را با بازآوری سخت پاک کنید؛ فونت از همین برنامه می‌آید و نسخهٔ قدیمی کش‌شده حروف را جدا نشان می‌دهد.',
              'اندازهٔ قلم را در صفحهٔ مطالعه بزرگ‌تر کنید.',
              'برای خواندن طولانی، حالت مطالعهٔ شب را امتحان کنید.',
            ],
          },
        ],
      },
      {
        id: 'tables',
        heading: 'جدول‌ها و متن ترکیبی',
        blocks: [
          {
            kind: 'steps',
            items: [
              'جدول به‌هم‌ریخته را در خروجی Word بررسی کنید؛ ساختار جدول در Word حفظ می‌شود ولی چیدمان صفحهٔ PDF بازسازی نمی‌شود.',
              'بخش مشکل‌دار را در تب «بخش‌ها» پیدا کنید و متن مبدأ و ترجمه را کنار هم بخوانید.',
              'اگر فقط یک بخش خراب است، همان را گزارش کنید؛ نیازی به ترجمهٔ دوبارهٔ کل کتاب نیست.',
            ],
          },
        ],
      },
    ],
    relatedSlugs: ['library-reader', 'convert-export'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'connection-errors',
    slug: 'connection-errors',
    title: 'خطای اتصال، کندی و بازیابی کار',
    summary: '۴۲۹، timeout، فایل نامعتبر و خروجی گمشده؛ با ترتیب درست و بدون حذف چیزی.',
    category: 'troubleshooting',
    keywords: ['خطا', 'error', 'اتصال', '429', 'کندی', 'timeout', 'نامعتبر', 'بازیابی', '401', '404'],
    sections: [
      {
        id: 'prereq',
        heading: 'پیش از هر کاری',
        blocks: [
          {
            kind: 'paragraph',
            text: 'پیشرفت هر بخش روی دیسک است؛ پس اول مطمئن شوید چیزی برای از دست دادن ندارید و سراغ حذف فایل‌های وضعیت یا شروع دوباره نروید.',
          },
        ],
      },
      {
        id: 'cases',
        heading: 'سناریوها',
        blocks: [
          {
            kind: 'steps',
            items: [
              'خطای ۴۲۹ (سقف درخواست): محدودکنندهٔ برنامه خودش سقف را نصف می‌کند و ادامه می‌دهد؛ کمی صبر کنید و «ادامه» را بزنید.',
              'timeout و کندی: اینترنت و وضعیت سرویس را بررسی کنید؛ ادامه از آخرین بخش سالم است.',
              '۴۰۱ و ۴۰۴: مقالهٔ «تنظیم سرویس ترجمه» را قدم‌به‌قدم انجام دهید.',
              'فایل نامعتبر: پسوند و متن‌دار بودن فایل را بررسی کنید (مقالهٔ فرمت‌ها) و نسخهٔ نجات ZIP را فقط از همین برنامه گرفته باشید.',
              'خروجی پیدا نشد: تب «فایل‌ها» و وضعیت کار را ببینید؛ کار ناتمام خروجی نهایی ندارد.',
              'بازیابی نیمه‌تمام: «ادامه» در صفحهٔ پایش، یا وارد کردن ZIP نجات از «افزودن کتاب».',
            ],
          },
        ],
      },
      {
        id: 'stuck',
        heading: 'اگر مشکل حل نشد',
        blocks: [
          {
            kind: 'paragraph',
            text: 'متن خطا را از تب «لاگ» همان کار کپی کنید و نگه دارید؛ همین متن کوتاه‌ترین راه رسیدن به علت است. حذف دیتابیس یا فایل‌های وضعیت راه‌حل نیست و بازیابی را سخت می‌کند.',
          },
        ],
      },
    ],
    relatedSlugs: ['stop-resume', 'provider-setup', 'file-formats'],
    reviewedAt: REVIEWED_AT,
  },
  {
    id: 'account-settings',
    slug: 'account-settings',
    title: 'حساب، تم و زبان',
    summary: 'حساب محلی، تست اتصال، تم تاریک و تعویض زبان؛ همه‌چیز روی همین دستگاه می‌ماند.',
    category: 'account-settings',
    keywords: ['حساب', 'account', 'تنظیمات', 'settings', 'تم', 'theme', 'تاریک', 'زبان', 'کلید'],
    sections: [
      {
        id: 'panels',
        heading: 'بخش‌های پنل کاربری',
        blocks: [
          {
            kind: 'paragraph',
            text: '«پنل کاربری» سه سؤال را جواب می‌دهد: راه‌اندازی درست است؟ (تست اتصال واقعی به سرویس)، تا حالا چه کرده‌ام؟ (کارهای من) و چه چیزی پیکربندی شده؟ (کلیدها و بسته‌های واژه‌نامه). گذرواژه فقط به‌صورت هش‌شده روی همین دستگاه ذخیره می‌شود.',
          },
        ],
      },
      {
        id: 'prefs',
        heading: 'تم و زبان',
        blocks: [
          {
            kind: 'paragraph',
            text: 'تم تاریک از دکمهٔ کنار ریل (یا نوار پایین در موبایل) و زبان رابط از دکمهٔ کرهٔ زمین عوض می‌شود. انتخاب شما ذخیره می‌ماند؛ حالت پیش‌فرض تم، دنبال‌کردن سیستم‌عامل است.',
          },
        ],
      },
    ],
    relatedSlugs: ['provider-setup', 'library-reader'],
    reviewedAt: REVIEWED_AT,
  },
]

export const helpFaqsFa: HelpFaq[] = [
  {
    id: 'start-cost',
    question: 'شروع ترجمه هزینه دارد؟',
    answer: 'انتخاب فایل و باز کردن کارگاه هیچ هزینه‌ای ندارد. اولین تماس با مدل وقتی است که خودتان دکمهٔ ترجمهٔ یک نمونه را می‌زنید؛ پیش از شروع کامل هم برآورد را می‌بینید.',
    category: 'getting-started',
    articleSlug: 'first-translation',
  },
  {
    id: 'model-default',
    question: 'کدام مدل استفاده می‌شود اگر چیزی انتخاب نکنم؟',
    answer: 'مدل پیش‌فرض فایل config/config.yaml. فیلد خالی یعنی همان مقدار پیکربندی؛ لازم نیست نام مدل را حفظ باشید.',
    category: 'translation-jobs',
    articleSlug: 'models-languages',
  },
  {
    id: 'model-unknown',
    question: 'نام مدل را اشتباه بنویسم چه می‌شود؟',
    answer: 'آپلود با مدل ناشناخته خطای ۴۰۰ می‌گیرد و ترجمه شروع نمی‌شود؛ یعنی به‌جای صورت‌حساب غافلگیرکننده همان اول مطلع می‌شوید.',
    category: 'translation-jobs',
    articleSlug: 'models-languages',
  },
  {
    id: 'glossary-auto',
    question: 'آیا برنامه خودش وسط کار به واژه‌نامه اضافه می‌کند؟',
    answer: 'نه. حالت پیش‌فرض «بدون یادگیری خودکار» است و فقط اصطلاح‌هایی که خودتان تأیید کرده‌اید وارد ترجمه می‌شوند.',
    category: 'glossary',
    articleSlug: 'glossary-workflow',
  },
  {
    id: 'stop-vs-cancel',
    question: 'فرق توقف با لغو چیست؟',
    answer: 'توقف در نقطهٔ امن می‌ایستد و با «ادامه» از همان‌جا جلو می‌رود؛ لغو کل کار را کنار می‌گذارد. اگر مردد هستید، متوقف کنید نه لغو.',
    category: 'translation-jobs',
    articleSlug: 'stop-resume',
  },
  {
    id: 'resume-after-shutdown',
    question: 'اگر کامپیوتر خاموش شود، کار از دست می‌رود؟',
    answer: 'نه. نتیجهٔ هر بخش روی دیسک ثبت می‌شود و ادامه دقیقاً از آخرین نقطهٔ سالم است؛ حتی بعد از خاموش‌شدن.',
    category: 'translation-jobs',
    articleSlug: 'stop-resume',
  },
  {
    id: 'download-where',
    question: 'فایل ترجمه‌شده را از کجا دانلود کنم؟',
    answer: 'از تب «فایل‌ها» در صفحهٔ همان کار، یا از منوی هر کتاب در «کتابخانه». کار ناتمام هنوز خروجی نهایی ندارد.',
    category: 'convert-export',
    articleSlug: 'convert-export',
  },
  {
    id: 'bad-file',
    question: 'چرا فایل من پذیرفته نشد؟',
    answer: 'فقط EPUB و PDF و TXT برای ترجمه پذیرفته می‌شوند (و ZIP نجات برای ادامه). PDF اسکن‌شده بدون OCR خوانده نمی‌شود و فصل‌های غیر UTF-8 رد می‌شوند.',
    category: 'getting-started',
    articleSlug: 'file-formats',
  },
  {
    id: 'srt-output',
    question: 'خروجی SRT دقیقاً چیست؟',
    answer: 'قالب زیرنویس با حفظ زمان‌بندی تولید می‌شود، ولی اتصال کامل محتوای آن هنوز در مسیر تکمیل است؛ برای متن کامل کتاب روی EPUB یا Word حساب کنید.',
    category: 'convert-export',
    articleSlug: 'convert-export',
  },
  {
    id: 'ocr-support',
    question: 'PDF اسکن‌شده ترجمه می‌شود؟',
    answer: 'در این نسخه نه؛ OCR فعال نیست و هر PDF به‌صورت تصویر پردازش می‌شود. نسخهٔ متنی PDF یا EPUB تمیز بدهید.',
    category: 'troubleshooting',
    articleSlug: 'file-formats',
  },
  {
    id: 'cost-estimate',
    question: 'هزینهٔ ترجمه از کجا معلوم می‌شود؟',
    answer: 'پیش از شروع، برآورد هزینه و زمان را با بازهٔ تقریبی می‌بینید. پلن‌های حساب جدا از هزینهٔ مصرف مدل‌اند.',
    category: 'account-settings',
    articleSlug: 'first-translation',
  },
  {
    id: 'reader-night',
    question: 'مطالعه در شب چشم را اذیت نمی‌کند؟',
    answer: 'حالت مطالعهٔ شب در صفحهٔ مطالعه هست و اندازهٔ قلم هم همان‌جا تنظیم می‌شود؛ کتاب دوزبانه از «کتابخانه» باز می‌شود.',
    category: 'library-reading',
    articleSlug: 'library-reader',
  },
]

/**
 * No real video exists in the repo or its docs (checked: no video file,
 * no hosted link anywhere), so this stays empty on purpose. The videos
 * section renders its honest empty state, and search never invents a
 * video result. Adding one later is appending an object here.
 */
export const helpVideosFa: HelpVideo[] = []
