import asyncio, os, sys, re, random, json
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from playwright.async_api import async_playwright
import httpx

BACKEND = "http://localhost:51666"
CITY_PREFIXES = {
    "余杭": "hangzhou-yhq", "滨江": "hangzhou-bjq",
    "西湖": "hangzhou-xhq", "上城": "hangzhou-scq",
    "拱墅": "hangzhou-gsq", "萧山": "hangzhou-xsq",
}

PLATFORM_KEYS = {
    "51job": {"card": ".joblist-item, .el", "id_pattern": r"171\d{6,}"},
}

SEARCH_CONFIGS = {
    "51job": {
        "search_url": "https://www.51job.com",
        "search_input": "#search-input",
        "result_wait": 5,
        "scroll_steps": 5,
    }
}


async def extract_card_fields(page, card_idx):
    """Extract structured fields from a job card on search results page."""
    cards = await page.query_selector_all(".joblist-item, .el")
    if card_idx >= len(cards):
        return None
    card = cards[card_idx]

    fields = await card.evaluate("""
        el => {
            const text = el.textContent || '';
            const html = el.innerHTML;
            const lines = text.split('\\n').map(l => l.trim()).filter(Boolean);

            // Find job ID
            const idMatch = html.match(/171\\d{6,}/);
            const jobId = idMatch ? idMatch[0] : '';

            // Find links
            const linkEl = el.querySelector('a[href*="jobs.51job.com"]');
            const companyLink = linkEl ? linkEl.getAttribute('href') || '' : '';
            const companyName = linkEl ? (linkEl.textContent || '').trim() : '';

            // Title: first line that's not empty and not a button
            const title = lines.find(l => l.length > 1 && l.length < 40 && !l.includes('去聊聊') && !l.includes('投递') && !l.includes('微信')) || lines[0] || '';

            // Salary: line with 万/千/K
            const salary = lines.find(l => /[万千K]/.test(l)) || '';

            // City: line with 杭州/·/
            const city = lines.find(l => /[·区县城市]/.test(l) && !/[万千K]/.test(l)) || '';

            return {
                id: jobId,
                title: title,
                company: companyName,
                salary: salary,
                city: city,
                company_url: companyLink,
            };
        }
    """)

    if fields and fields["id"]:
        city_prefix = "hangzhou"
        for name, prefix in CITY_PREFIXES.items():
            if name in (fields["city"] or ""):
                city_prefix = prefix
                break
        fields["jd_url"] = f"https://jobs.51job.com/{city_prefix}/{fields['id']}.html"
        fields["platform"] = "51job"

    return fields


async def clean_jd(body_text):
    """Extract only the job requirements section from the detail page."""
    lines = [l.strip() for l in body_text.split("\n") if l.strip()]
    start_kw = ["职位信息", "岗位职责", "任职要求", "工作内容", "岗位要求", "职位描述"]
    end_kw = ["公司信息", "公司介绍", "工作地址", "上班地址", "职能类别", "51Job安全提醒"]

    start_idx = -1
    for i, line in enumerate(lines):
        if any(kw in line for kw in start_kw):
            start_idx = i
            break

    if start_idx < 0:
        return "\n".join(lines[:50])[:2000]

    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        if any(kw in line for kw in end_kw):
            end_idx = i
            break

    return "\n".join(lines[start_idx:end_idx])[:3000]


async def main():
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0]

    # Search
    print("1. 搜索 Python 后端...")
    await page.goto("https://www.51job.com", wait_until="domcontentloaded")
    await asyncio.sleep(2)
    search = await page.query_selector("#search-input")
    if search:
        await search.click()
        await asyncio.sleep(0.3)
        for ch in "Python 后端":
            await page.keyboard.type(ch, delay=random.randint(60, 180))
            await asyncio.sleep(random.uniform(0.01, 0.05))
    await page.keyboard.press("Enter")
    await asyncio.sleep(5)

    # Scroll to load data
    for i in range(5):
        await page.evaluate(f"window.scrollTo(0, {i * 800})")
        await asyncio.sleep(1)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(2)

    all_results = []
    search_url = page.url

    for page_num in range(1, 3):
        print(f"\n第 {page_num} 页")

        # Click cards without IDs to trigger load
        cards_data = []
        for ci in range(30):
            fields = await extract_card_fields(page, ci)
            if not fields:
                break
            cards_data.append(fields)

        no_id_cards = [c for c in cards_data if not c["id"]]
        for c in no_id_cards[:5]:
            idx = cards_data.index(c)
            card_el = (await page.query_selector_all(".joblist-item, .el"))[idx]
            if card_el:
                await card_el.click()
                await asyncio.sleep(1.5)
                await page.keyboard.press("Escape")
                await asyncio.sleep(1)

        # Re-query
        cards_data = []
        for ci in range(30):
            fields = await extract_card_fields(page, ci)
            if not fields:
                break
            cards_data.append(fields)

        valid = [c for c in cards_data if c["id"]]
        print(f"  {len(valid)}/{len(cards_data)} 个有完整信息")

        # Process
        token = httpx.post(f"{BACKEND}/admin/login",
            json={"username": "admin", "password": "admin123"}, timeout=10).json()["access_token"]

        for idx, card in enumerate(valid[:10]):
            print(f"\n  [{idx+1}] {card['title']} @ {card['company']} - {card['salary']}")

            # Open detail
            await page.goto(card["jd_url"], wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            body = await page.inner_text("body")
            jd_clean = clean_jd(body)
            print(f"     JD: {len(jd_clean)} 字符")

            # Save to backend
            r = httpx.post(f"{BACKEND}/admin/jobs",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "title": card["title"][:100],
                    "company": card["company"],
                    "city": card["city"],
                    "salary": card["salary"],
                    "jd_url": card["jd_url"],
                    "platform": card["platform"],
                    "jd_text": jd_clean,
                }, timeout=10)
            job_db_id = r.json()["id"]

            # Match
            r2 = httpx.post(f"{BACKEND}/admin/jobs/{job_db_id}/match",
                headers={"Authorization": f"Bearer {token}"}, timeout=30)
            result = r2.json()
            dims = result.get("dimensions", {})
            dim_str = " | ".join([f"{k}:{d.get('score',0)}" for k,d in dims.items()])
            print(f"     总分: {result['score']}/100 [{dim_str}]")
            for m in result.get("missing_items", [])[:2]:
                print(f"     - {m['reason']}")

            all_results.append({
                "title": card["title"],
                "company": card["company"],
                "salary": card["salary"],
                "score": result["score"],
                "url": card["jd_url"],
            })

            # Back to search
            await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

        # Next page
        if page_num == 1:
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
            next_btn = await page.query_selector("a.next, .next, [class*=next]")
            if next_btn:
                disabled = await next_btn.get_attribute("disabled")
                cls = await next_btn.get_attribute("class") or ""
                if not disabled and "disabled" not in cls:
                    print(f"\n翻到第 2 页...")
                    await next_btn.click()
                    await asyncio.sleep(5)
                    search_url = page.url
                    continue
            break

    print(f"\n处理完成！共 {len(all_results)} 个岗位:")
    for r in sorted(all_results, key=lambda x: -x["score"]):
        tag = "HIGH" if r["score"] >= 70 else "MID" if r["score"] >= 40 else "LOW"
        print(f"  [{tag}] {r['score']:3}分 | {r['title'][:20]} @ {r['company'][:15]} | {r['salary']}")

    await p.stop()

asyncio.run(main())
