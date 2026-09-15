# Book glossaries

Open Library, choose «واژه‌نامه» on a book, load the source/target language
pair, and add source terms, preferred translations, categories and notes.
Save, then choose «ذخیره و شروع ترجمهٔ جدید» to translate the stored original.
This creates a new job and retains the previous output.

The `book_glossaries` table stores a versioned term list per book and language
pair. Updates use optimistic version checking; stale edits must be reloaded.
Existing global glossaries remain separate from these book-owned lists.

Job metadata captures the glossary before the worker starts. The pipeline
copies it atomically to `glossary.json` in its job directory. Resume uses that
base plus this job's learned terms, not later library edits. Older jobs without
an automatic-extraction flag retain their previous behavior. New library
translations use fast mode; the batch request builder reads the fixed snapshot.

Only terms found at word boundaries in the chunk's visible text are included
in the translation request. Sequential translation logs missing equivalents
as review suggestions; it never replaces translated text automatically.
This is a heuristic, not a guarantee of translation quality.

## Automatic glossary

«ساخت خودکار واژه‌نامه حین ترجمه» is checked by default in the new-upload form
and the Library translation panel. Uncheck it to avoid the extra requests.
Sequential EPUB/PDF translations extract up to 20 names or specialized terms
after saving each translated chunk, with a maximum of 2,000 terms per glossary.
This adds an API request per chunk and therefore adds latency and provider cost.
Batch extraction is disabled: independently submitted chunks cannot use terms
learned from an earlier chunk's response. Existing jobs are not opted in.

The extractor receives the source/translation pair. Candidates must occur in
both texts, and must not conflict with an existing normalized source term.
The first accepted equivalent is reused by subsequent chunks. Literal checks
reject invented text but do not prove semantic correctness; generated entries
are marked automatic and can be edited in Library.

`glossary_learned.json` atomically records terms, processed chunk IDs, failures,
and publication progress. A resume recovers pending extraction even when the
translation was already saved, without translating that chunk again. Completed
extraction is skipped. Extraction errors are logged and retried on resume;
they do not discard successful translations. A stop skips further extraction.

Progress polling, opening the glossary, and job completion publish new terms
to the book's language-specific glossary. Publishing appends missing terms
without overwriting manual equivalents, and avoids republishing deleted terms.
Use «بارگذاری» in Library during translation to see the newly extracted entries.
Manual edits made during a job apply to future jobs, not its frozen base.

Alias grouping and a dedicated review screen remain outside this feature.
Spelling variants can be entered as separate rows.
