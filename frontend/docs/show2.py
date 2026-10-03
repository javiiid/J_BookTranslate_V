import json, sys
sys.stdout.reconfigure(encoding="utf-8")
d = json.load(open(r"D:\J_BookTranslate_V\frontend\docs\inventory\phase3\shapes.json", encoding="utf-8"))
for k in ["/api/account/portal", "/api/provider-config", "/api/analytics/overview", "/api/languages"]:
    print("=" * 60); print(k, "  status", d.get(k, {}).get("status"))
    print(json.dumps(d.get(k, {}).get("shape"), ensure_ascii=False, indent=1)[:900])
