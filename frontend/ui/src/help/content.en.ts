/**
 * English help content. Same slugs, ids, categories and section ids as
 * `content.fa.ts`: switching language never breaks a link or an anchor.
 * Only the prose is translated.
 */
import type { HelpArticle, HelpFaq, HelpVideo } from '../lib/help.ts'

const REVIEWED_AT = '2026-10-09'

export const helpArticlesEn: HelpArticle[] = [
  {
    id: 'first-translation',
    slug: 'first-translation',
    title: 'Your first translation, step by step',
    summary: 'From picking a file to starting the full run: four steps before anything is spent.',
    category: 'getting-started',
    keywords: ['start', 'first', 'upload', 'workshop', 'calibration'],
    sections: [
      {
        id: 'steps',
        heading: 'Steps',
        blocks: [
          {
            kind: 'steps',
            items: [
              'On the "Add book" page, choose an EPUB or PDF file. Picking a file costs nothing.',
              'The app reads the book and opens a calibration workshop; you settle voice, model and glossary on 1 to 3 real samples of that book.',
              'Generate and approve the samples, then lock the profile; approved sections are never billed twice under the same settings.',
              'Start the full translation and watch it on the "Translation monitor" page; every finished section is committed to disk.',
            ],
          },
        ],
      },
      {
        id: 'expect',
        heading: 'What to expect',
        blocks: [
          {
            kind: 'paragraph',
            text: 'Before the run you see a cost and time estimate with an approximate band. When it finishes, the main output waits in the "Files" tab and the bilingual book opens from the "Library".',
          },
        ],
      },
      {
        id: 'stuck',
        heading: 'If you get stuck',
        blocks: [
          {
            kind: 'paragraph',
            text: 'If the workshop never opens, read "My file was rejected". For a translation-service error, read "Connection errors and slowness"; saved progress is not lost.',
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
    title: 'Setting up the translation service',
    summary: 'Where to enter the OpenAI-compatible key and address, and how to prove it works.',
    category: 'getting-started',
    keywords: ['key', 'api', 'base_url', 'service', 'provider', 'connection', 'test'],
    sections: [
      {
        id: 'where',
        heading: 'Where the key lives',
        blocks: [
          {
            kind: 'paragraph',
            text: 'The key lives only in config/config.yaml and is never committed to Git. In the web UI, "Translation service settings" under the "Account" panel shows the same values, and its test button checks the real connection to the service.',
          },
          {
            kind: 'note',
            text: 'A compatible address usually has to end with /v1. A passing test means the key was accepted and the selected model is on the provider\'s own list too.',
          },
        ],
      },
      {
        id: 'fix401',
        heading: 'If the test fails',
        blocks: [
          {
            kind: 'steps',
            items: [
              '401 means the key was rejected; copy a fresh key from the service and paste it again.',
              '404 means the address or model was not found; check the trailing /v1 and the exact model name.',
              'On Windows, a network-access error means allowing the app in the firewall.',
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
    title: 'My file was rejected',
    summary: 'Which inputs are accepted and the honest limits of each.',
    category: 'getting-started',
    keywords: ['format', 'epub', 'pdf', 'txt', 'zip', 'rescue', 'ocr', 'scanned'],
    sections: [
      {
        id: 'accepted',
        heading: 'Accepted inputs',
        blocks: [
          {
            kind: 'paragraph',
            text: 'For translation: EPUB, PDF and TXT. For resuming half-done work: the rescue ZIP snapshot. For conversion without translation: EPUB, textual PDF, SRT, TXT and Markdown.',
          },
        ],
      },
      {
        id: 'limits',
        heading: 'Real limits',
        blocks: [
          {
            kind: 'warning',
            text: 'Scanned PDFs need OCR, and OCR is not enabled in this version; every PDF is processed as images. Non-UTF-8 EPUB chapters are currently skipped silently.',
          },
          {
            kind: 'paragraph',
            text: 'If your file is one of these, convert it to an EPUB with clean text or hand over the textual PDF, and check the result on the workshop samples.',
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
    title: 'Choosing a model and languages',
    summary: 'Where the default model comes from, what an unknown model does, and which languages work.',
    category: 'translation-jobs',
    keywords: ['model', 'language', 'luna', 'terra', 'gemini'],
    sections: [
      {
        id: 'default',
        heading: 'The default model',
        blocks: [
          {
            kind: 'paragraph',
            text: 'The default model is read only from config/config.yaml. Leaving the model field empty uses the configured value; you never have to memorise a model name.',
          },
          {
            kind: 'note',
            text: 'An unknown model returns a 400 error and the translation never starts -- you learn it up front instead of on a surprise bill.',
          },
        ],
      },
      {
        id: 'langs',
        heading: 'Languages',
        blocks: [
          {
            kind: 'paragraph',
            text: 'English, Persian, Arabic, French, German, Spanish, Italian, Russian, Turkish, Chinese, Japanese and Korean -- in both directions, source and target.',
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
    title: 'Reading progress and what statuses mean',
    summary: 'The eight job statuses, and what each of the five monitor tabs shows.',
    category: 'translation-jobs',
    keywords: ['status', 'monitor', 'progress', 'queued', 'running'],
    sections: [
      {
        id: 'statuses',
        heading: 'Statuses',
        blocks: [
          {
            kind: 'paragraph',
            text: '"Queued" means the run has not started; "Translating" means chunks are being sent; "Stopping" means a stop was requested and it halts at the next safe point; "Paused" means you can resume; "Completed" means every chunk is committed; "Failed" and "Cancelled" need a look.',
          },
        ],
      },
      {
        id: 'tabs',
        heading: 'The five monitor tabs',
        blocks: [
          {
            kind: 'paragraph',
            text: 'Each job page has five tabs: "Summary" for totals and outputs, "Chunks" for searching chunks, "Quality" for flagged chunks, "Logs" for technical events and "Files" for downloads.',
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
    title: 'Stopping, cancelling and resuming a translation',
    summary: 'Stop vs cancel, resuming from the last healthy point, and the one trade-off to know.',
    category: 'translation-jobs',
    keywords: ['stop', 'resume', 'cancel', 'rescue'],
    sections: [
      {
        id: 'prereq',
        heading: 'Prerequisite',
        blocks: [
          {
            kind: 'paragraph',
            text: 'Your job just has to be listed on the "Translation monitor" page; act from that same row, no job id needed.',
          },
        ],
      },
      {
        id: 'actions',
        heading: 'The three actions and what each means',
        blocks: [
          {
            kind: 'steps',
            items: [
              '"Stop": the run halts at the next safe point and later continues from there with "Resume".',
              '"Resume": the run continues from the last healthy section committed to disk -- even after a shutdown.',
              '"Cancel": the whole job is dropped and progress is discarded. Take a rescue snapshot (ZIP) first if you might need it.',
            ],
          },
          {
            kind: 'warning',
            text: 'At top concurrency a manual stop may waste up to 12 already-sent requests; but nothing is ever wrongly marked "complete", and resuming is always safe.',
          },
        ],
      },
      {
        id: 'stuck',
        heading: 'If resuming does not work',
        blocks: [
          {
            kind: 'paragraph',
            text: 'Test the service key in the "Account" panel first; most failed resumes are key credentials. If the error persists, read "Connection errors and slowness".',
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
    title: 'The book glossary and consistent terms',
    summary: 'Propose, your review, approve, lock: why nothing joins mid-run.',
    category: 'glossary',
    keywords: ['glossary', 'term', 'approve', 'suggest', 'lock'],
    sections: [
      {
        id: 'flow',
        heading: 'The workflow',
        blocks: [
          {
            kind: 'steps',
            items: [
              'Press "Suggest terms": 12 chunks from across the book are read with just 1 model call.',
              'In the review table, tick each row, fix the equivalent or reject it; then press "Approve selected".',
              'When translation starts the glossary locks (snapshot); chunk one and chunk three hundred translate against the same version.',
            ],
          },
        ],
      },
      {
        id: 'guarantees',
        heading: 'Two guarantees',
        blocks: [
          {
            kind: 'paragraph',
            text: 'First: every proposal must literally appear in the sampled text, or the server discards it; a hallucinated glossary never enters a translation. Second: the default is "no automatic learning"; nothing joins mid-translation.',
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
    title: 'The calibration workshop and translation voice',
    summary: '1 to 3 real samples, four voices, draft and final models, and what locking means.',
    category: 'translation-jobs',
    keywords: ['calibration', 'workshop', 'tone', 'voice', 'sample', 'profile', 'lock'],
    sections: [
      {
        id: 'tones',
        heading: 'Four voices',
        blocks: [
          {
            kind: 'paragraph',
            text: '"Modern & flowing", "Literary & figurative", "Academic & technical" and "Faithful & close". Changing the voice regenerates the open sample with the final model, so you see exactly what the book will translate with.',
          },
        ],
      },
      {
        id: 'models',
        heading: 'Draft and final models',
        blocks: [
          {
            kind: 'paragraph',
            text: 'The draft is for cheap comparison; the full book always translates with the final model. Before locking, every sample must be generated and approved with the final model.',
          },
          {
            kind: 'warning',
            text: 'Approving a few samples does not guarantee the whole book; review the final output.',
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
    title: 'The library and bilingual reading',
    summary: 'Searching books, continuing the last section, and reading beside the original at night.',
    category: 'library-reading',
    keywords: ['library', 'reader', 'reading', 'night', 'search'],
    sections: [
      {
        id: 'library',
        heading: 'The library',
        blocks: [
          {
            kind: 'paragraph',
            text: 'The "Library" shows every book with its progress; search by name, author or model. The "continue from the last section" card surfaces the closest unfinished book.',
          },
        ],
      },
      {
        id: 'reader',
        heading: 'Reading',
        blocks: [
          {
            kind: 'paragraph',
            text: '"Read bilingual" opens source and translation side by side; night study mode suits long reads. Font size and reading settings live on that same reading page.',
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
    title: 'Converting files and getting outputs',
    summary: '9 output formats, translation-free conversion, and what this version lacks.',
    category: 'convert-export',
    keywords: ['convert', 'output', 'download', 'docx', 'srt', 'markdown'],
    sections: [
      {
        id: 'formats',
        heading: 'Formats',
        blocks: [
          {
            kind: 'paragraph',
            text: 'Translated EPUB, translated PDF, bilingual PDF, Word, Markdown, bilingual text, JSON chunks, SRT subtitles and the quality report. The "Convert file" page builds these with no model usage; keep the tab open until the result arrives.',
          },
        ],
      },
      {
        id: 'limits',
        heading: 'Real limits',
        blocks: [
          {
            kind: 'warning',
            text: 'Wiring the full SRT content is still in progress; batch conversion, OCR, EPUB output, page-range selection and permanent history are not in this version. Unproduced outputs are marked separately in the result.',
          },
        ],
      },
      {
        id: 'stuck',
        heading: 'If an output is missing',
        blocks: [
          {
            kind: 'paragraph',
            text: 'Check the "Files" tab of that job first; if it is empty, check the job status -- an unfinished job has no final output yet. Also search the app output folder for downloaded files.',
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
    title: 'Persian display and mixed text',
    summary: 'Fonts, numbers and code, tables, and reading bilingual text without breakage.',
    category: 'troubleshooting',
    keywords: ['persian', 'font', 'display', 'table', 'code', 'rtl'],
    sections: [
      {
        id: 'facts',
        heading: 'What the app already handles',
        blocks: [
          {
            kind: 'paragraph',
            text: 'The Persian font ships with the app and needs no internet; if letters look detached or unreadable, hard-refresh the browser cache first. Numbers, paths and code always render left-to-right so their order never breaks.',
          },
        ],
      },
      {
        id: 'font',
        heading: 'If the font looks off',
        blocks: [
          {
            kind: 'steps',
            items: [
              'Hard-refresh the browser cache; the font ships with the app, and a stale cached copy renders letters detached.',
              'Enlarge the font on the reading page.',
              'For long reads, try night study mode.',
            ],
          },
        ],
      },
      {
        id: 'tables',
        heading: 'Tables and mixed text',
        blocks: [
          {
            kind: 'steps',
            items: [
              'Check a broken table in the Word output; table structure survives there, though PDF page layout is not rebuilt.',
              'Find the bad section in the "Chunks" tab and read source beside translation.',
              'If only one section is broken, report just that one; the whole book needs no re-translation.',
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
    title: 'Connection errors, slowness and recovery',
    summary: '429s, timeouts, invalid files and missing outputs; in the right order, deleting nothing.',
    category: 'troubleshooting',
    keywords: ['error', 'connection', '429', 'slow', 'timeout', 'invalid', 'recovery', '401', '404'],
    sections: [
      {
        id: 'prereq',
        heading: 'Before anything else',
        blocks: [
          {
            kind: 'paragraph',
            text: 'Every chunk result is on disk, so there is nothing to lose -- do not reach for deleting state files or restarting from scratch first.',
          },
        ],
      },
      {
        id: 'cases',
        heading: 'Scenarios',
        blocks: [
          {
            kind: 'steps',
            items: [
              '429 (rate limit): the app halves its own ceiling and continues; wait a little and press "Resume".',
              'Timeouts and slowness: check the internet and the service status; resuming continues from the last healthy chunk.',
              '401 and 404: follow "Setting up the translation service" step by step.',
              'Invalid file: check the extension and that the file has real text ("My file was rejected"); take a rescue ZIP only from this app.',
              'Missing output: check the "Files" tab and the job status; an unfinished job has no final output.',
              'Recovering half-done work: "Resume" on the monitor page, or import the rescue ZIP from "Add book".',
            ],
          },
        ],
      },
      {
        id: 'stuck',
        heading: 'If it is still broken',
        blocks: [
          {
            kind: 'paragraph',
            text: 'Copy the error text from that job\'s "Logs" tab and keep it; it is the shortest path to the cause. Deleting the database or state files is not a fix and makes recovery harder.',
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
    title: 'Account, theme and language',
    summary: 'The local account, the connection test, dark mode and language; everything stays on this machine.',
    category: 'account-settings',
    keywords: ['account', 'settings', 'theme', 'dark', 'language', 'key'],
    sections: [
      {
        id: 'panels',
        heading: 'The account panel sections',
        blocks: [
          {
            kind: 'paragraph',
            text: 'The "Account" panel answers three questions: is the setup working? (a real connection test to the service), what have I done? (my work) and what is configured? (keys and glossary packs). The password is stored on this machine as a hash only.',
          },
        ],
      },
      {
        id: 'prefs',
        heading: 'Theme and language',
        blocks: [
          {
            kind: 'paragraph',
            text: 'Dark mode switches from the button beside the rail (or the bottom bar on phones), and the interface language from the globe button. Your choice persists; the default theme follows the operating system.',
          },
        ],
      },
    ],
    relatedSlugs: ['provider-setup', 'library-reader'],
    reviewedAt: REVIEWED_AT,
  },
]

export const helpFaqsEn: HelpFaq[] = [
  {
    id: 'start-cost',
    question: 'Does starting a translation cost anything?',
    answer: 'Picking a file and opening the workshop costs nothing. The first model call happens when you translate a sample yourself; before the full run you see the estimate.',
    category: 'getting-started',
    articleSlug: 'first-translation',
  },
  {
    id: 'model-default',
    question: 'Which model is used if I pick nothing?',
    answer: 'The default model from config/config.yaml. An empty field means the configured value; you never have to memorise a model name.',
    category: 'translation-jobs',
    articleSlug: 'models-languages',
  },
  {
    id: 'model-unknown',
    question: 'What if I mistype the model name?',
    answer: 'Uploading with an unknown model returns a 400 error and the translation never starts -- you learn it up front instead of on a surprise bill.',
    category: 'translation-jobs',
    articleSlug: 'models-languages',
  },
  {
    id: 'glossary-auto',
    question: 'Does the app add to the glossary on its own mid-run?',
    answer: 'No. The default is "no automatic learning", and only terms you approved enter the translation.',
    category: 'glossary',
    articleSlug: 'glossary-workflow',
  },
  {
    id: 'stop-vs-cancel',
    question: 'What is the difference between stop and cancel?',
    answer: 'Stop halts at a safe point and "Resume" continues from there; cancel drops the whole job. When in doubt, stop, do not cancel.',
    category: 'translation-jobs',
    articleSlug: 'stop-resume',
  },
  {
    id: 'resume-after-shutdown',
    question: 'Is work lost if the computer shuts down?',
    answer: 'No. Every chunk result is committed to disk, and resuming continues exactly from the last healthy point -- even after a shutdown.',
    category: 'translation-jobs',
    articleSlug: 'stop-resume',
  },
  {
    id: 'download-where',
    question: 'Where do I download the translated file?',
    answer: 'From the "Files" tab of that job page, or from each book\'s menu in the "Library". An unfinished job has no final output yet.',
    category: 'convert-export',
    articleSlug: 'convert-export',
  },
  {
    id: 'bad-file',
    question: 'Why was my file rejected?',
    answer: 'Only EPUB, PDF and TXT are accepted for translation (plus a rescue ZIP to resume). A scanned PDF without OCR cannot be read, and non-UTF-8 chapters are skipped.',
    category: 'getting-started',
    articleSlug: 'file-formats',
  },
  {
    id: 'srt-output',
    question: 'What exactly is the SRT output?',
    answer: 'Translated subtitles. For .srt uploads the original timing is preserved; for books the timing is estimated from the translated text at reading speed, in 42-char lines.',
    category: 'convert-export',
    articleSlug: 'convert-export',
  },
  {
    id: 'ocr-support',
    question: 'Are scanned PDFs translated?',
    answer: 'Not in this version; OCR is not enabled and every PDF is processed as images. Hand over the textual PDF or a clean EPUB.',
    category: 'troubleshooting',
    articleSlug: 'file-formats',
  },
  {
    id: 'cost-estimate',
    question: 'How is the translation cost known?',
    answer: 'Before the run you see a cost and time estimate with an approximate band. Account plans are separate from model usage cost.',
    category: 'account-settings',
    articleSlug: 'first-translation',
  },
  {
    id: 'reader-night',
    question: 'Is night reading easy on the eyes?',
    answer: 'Night study mode is on the reading page, and font size adjusts there too; the bilingual book opens from the "Library".',
    category: 'library-reading',
    articleSlug: 'library-reader',
  },
]

/** Mirrors `helpVideosFa`: no real video exists, so nothing is listed. */
export const helpVideosEn: HelpVideo[] = []
