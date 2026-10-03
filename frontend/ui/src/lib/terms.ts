/**
 * Term normalisation.
 *
 * One function, one job: turn a source term into the key used to compare terms
 * across a proposal, an approved glossary and a user's tick list. It lives on
 * its own because the glossary review needs it and so does the chunk filter, and
 * importing it from `chunks.ts` would make the glossary depend on a module named
 * after a different feature.
 *
 * The Python side uses `unicodedata.normalize("NFKC", value).casefold()` in
 * `app/glossary/service.py`, and the two MUST agree or a term looks like two
 * different terms depending on which UI wrote it.
 *
 * WHAT WAS CHECKED, AND WHAT WAS WRONG
 * -----------------------------------
 * It seemed obvious that JavaScript's NFKC drops a zero-width non-joiner while
 * Python's does not, so a test asserting `key("واژه‌نامه") === key("واژهنامه")`
 * was written -- and it passed, because the TS side was stripping invisibles
 * while Python was not.
 *
 * Feeding the same strings through both implementations showed the opposite:
 * Python KEEPS the ZWNJ, the soft hyphen, ZWSP, ZWJ and the bidi controls, and
 * so does `String.prototype.normalize`. Both keep them. Stripping them here
 * would have been the bug, not the fix.
 *
 * Verified with docs/check_normalisation.py, which runs this function through
 * Node and the Python one through the interpreter and diffs the output.
 * `toLowerCase` stands in for `casefold`; the two agree on every case in that
 * list, and German ß is the known edge where they would not.
 */

/** Browser-safe: `String.prototype.normalize` is in the ECMAScript core. */
export function key(value: string): string {
  return value.normalize('NFKC').toLowerCase()
}
