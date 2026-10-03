"""Install the KALIMA mark into the Python project.

The mark is authored in the React project, which is the single source of truth
for brand assets. The Python side needs a copy because `app/web.py` serves no
static files and the README needs a path that resolves on GitHub.

Copying rather than symlinking or referencing: the two repositories must each
build and run on their own, and a dangling relative path out of `D:\\` would
break the moment either folder is moved.

Re-run after changing the artwork:

    python D:\\J_Translate_Ui\\docs\\install_brand.py
"""
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SOURCE = Path(r"D:\J_Translate_Ui\ui\public\brand")
TARGET = Path(r"D:\J_BookTranslate_V\app\brand")

FILES = ["kalima-mark-light.svg", "kalima-mark-dark.svg"]

if not SOURCE.is_dir():
    print(f"  source missing: {SOURCE}")
    raise SystemExit(1)

TARGET.mkdir(parents=True, exist_ok=True)

for name in FILES:
    source = SOURCE / name
    if not source.is_file():
        print(f"  missing in source: {name}")
        raise SystemExit(1)
    destination = TARGET / name
    shutil.copyfile(source, destination)
    print(f"  {name}  ({destination.stat().st_size / 1024:.1f} KB)")

# A note next to the files, so nobody edits them here and wonders why the React
# build disagrees.
(TARGET / "README.md").write_text(
    """# Brand assets

Copied from `D:\\J_Translate_Ui\\ui\\public\\brand` by
`D:\\J_Translate_Ui\\docs\\install_brand.py`.

**These are not the source.** The React project owns the artwork; edit there and
re-run the installer. Editing here means the two UIs drift, and the drift is
invisible until someone notices the sidebar logos differ.

`app/core/brand.py` reads them from here.
""",
    encoding="utf-8",
)
print("  README.md written")
