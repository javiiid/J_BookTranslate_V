// Prints the key() output for the cases in docs/check_normalisation.py.
// Kept as a file so the input survives as UTF-8.
import { key } from '../src/lib/terms.ts'

const CASES = ["واژه‌نامه", "می‌رود", "نمی‌شود", "book", "Ann", "ANN", "ＡＢＣ", "café", "café", "soft­hyphen", "a​b", "a‍b", "a‫b", "Dagger Society", "dagger society", "", "   ", "۱۲۳", "١٢٣"]
process.stdout.write(JSON.stringify(CASES.map(key)))
