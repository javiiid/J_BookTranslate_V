import json, sys
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(r"D:\J_Translate_Ui\docs\inventory\phase3\shapes.json", encoding="utf-8"))
for k in ["/api/library?page=1&limit=5", "/api/library/359", "/api/reader/040061b0658b/chapters", "/api/reader/040061b0658b/chapters/1/blocks", "/api/languages", "/api/reader/settings", "/api/account/portal"]:
    print("=" * 66)
    print(k)
    print(json.dumps(d.get(k, {}).get("shape"), ensure_ascii=False, indent=2)[:1200])
