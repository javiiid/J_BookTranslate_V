"""Reorder the audit script: imports and the shell must come first.

`AppShell` was used by `renderWithShell` before it was imported, and the render
helper was defined before the QueryClient it closes over. Both are ordering
mistakes rather than logic errors, so this moves blocks rather than rewriting
them, and reports the resulting order so the next read is not a puzzle.
"""
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

path = Path(r"D:\J_Translate_Ui\ui\scripts\audit-contrast.mjs")
text = path.read_text(encoding="utf-8")

# 1. Make sure AppShell is in the destructured import from the built bundle.
text = text.replace(
    "const { ReaderPage, AccountPage, DashboardPage, WorkspacePage, LibraryPage } = await import(pagesUrl)",
    "const { ReaderPage, AccountPage, DashboardPage, WorkspacePage, LibraryPage, AppShell } =\n  await import(pagesUrl)",
)

# 2. Drop the stray second import that was appended after renderWithShell.
text = re.sub(
    r"\n/\* queryClient is declared above renderWithShell.*?\)\.then\(async \(pages\) => pages\)\n",
    "\n",
    text,
    flags=re.S,
)

# 3. Move renderWithShell to just after the SEED block, so queryClient and
#    AppShell both exist above it.
helper = re.search(
    r"/\*\*\n \* Render the page inside the app shell.*?\n\}\n", text, re.S
)
if helper:
    block = helper.group(0)
    text = text.replace(block, "")
    anchor = "console.log(`  seeded ${SEED.length} quer(ies) so the pages render with data`)\n"
    if anchor in text:
        text = text.replace(anchor, anchor + "\n" + block)
    else:
        print("  could not find the SEED anchor")
        raise SystemExit(1)
    print("  moved renderWithShell below the client and the seed")

# 4. Use renderWithShell in the route loop.
text = re.sub(
    r"    const html = renderToStaticMarkup\(\n      createElement\(\n        MemoryRouter,\n        \{ initialEntries: \[entry\] \},\n        createElement\(\n          QueryClientProvider,\n          \{ client: queryClient \},\n          createElement\(\n            Routes,\n            null,\n            createElement\(Route, \{ path: pattern, element: createElement\(Component\) \}\),\n            createElement\(Route, \{ path: '\*', element: createElement\(Component\) \}\),\n          \),\n        \),\n      \),\n    \)",
    "    const html = renderWithShell(Component, pattern, entry)",
    text,
)

path.write_text(text, encoding="utf-8")

print()
print("=== resulting order ===")
for index, line in enumerate(text.splitlines(), 1):
    if re.match(r"^(const|function|async function|await build|for \(|measurements)", line):
        print(f"  {index:4}  {line[:88]}")
