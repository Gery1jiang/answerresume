import httpx
tabs = httpx.get("http://127.0.0.1:9222/json", timeout=5).json()
for i, t in enumerate(tabs[:3]):
    print(f"[{i}] {t.get('title','?')[:60]}")
