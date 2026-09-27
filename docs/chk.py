import xml.etree.ElementTree as ET, sys, pathlib
sys.stdout.reconfigure(encoding="utf-8")
for f in [r"D:\J_Translate_Ui\ui\public\brand\kalima-mark-light.svg",
          r"D:\J_Translate_Ui\ui\public\brand\kalima-mark-dark.svg",
          r"D:\J_Translate_Ui\ui\public\favicon.svg"]:
    p = pathlib.Path(f)
    text = p.read_text(encoding="utf-8")
    print("=" * 60)
    print(p.name, len(text), "chars")
    try:
        ET.parse(p); print("  parses OK")
    except ET.ParseError as e:
        print("  ERROR:", e)
        line = e.position[0]
        for i in range(max(1, line-3), min(len(text.splitlines()), line+3)+1):
            print(f"   {i:3}| {text.splitlines()[i-1][:90]}")
