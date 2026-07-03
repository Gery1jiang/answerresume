"""Step-by-step debug of do_crawl."""
import asyncio, sys, json
from playwright.async_api import async_playwright

async def main():
    log = []
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0]
    
    keywords = "产品经理"
    max_count = 3
    
    # Step 1: Homepage search
    log.append("=== Step 1: Homepage search ===")
    await page.goto("https://www.51job.com/", wait_until="domcontentloaded")
    await asyncio.sleep(3)
    search = await page.query_selector("#search-input")
    log.append(f"Search input found: {search is not None}")
    
    if search:
        await search.click()
        await asyncio.sleep(0.3)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Delete")
        for ch in keywords:
            await page.keyboard.type(ch, delay=50)
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.5)
        await page.keyboard.press("Enter")
        await asyncio.sleep(6)
    log.append(f"After search URL: {page.url}")
    
    # Step 2: Scroll
    log.append("\n=== Step 2: Scroll ===")
    for i in range(5):
        await page.evaluate(f"window.scrollTo(0, {i * 800})")
        await asyncio.sleep(1)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(2)
    
    # Step 3: Extract cards
    log.append("\n=== Step 3: Extract cards ===")
    all_cards = []
    for i in range(min(max_count * 3, 60)):
        cards = await page.query_selector_all(".joblist-item-job-wrapper, .joblist-item, .el")
        if i >= len(cards):
            break
        card = cards[i]
        fields = await card.evaluate("""
            el => {
                const html = el.outerHTML;
                let jobId = '';
                const sd = el.getAttribute('sensorsdata');
                if (sd) {
                    try {
                        const parsed = JSON.parse(sd);
                        jobId = parsed.jobId || '';
                    } catch(e) {}
                }
                if (!jobId) {
                    const idMatch = html.match(/job[Ii][Dd][=:"]+(\\d{6,})/);
                    jobId = idMatch ? idMatch[1] : '';
                }
                const g = s => { const e = el.querySelector(s); return e ? (e.textContent || '').trim() : ''; };
                return {
                    id: jobId,
                    title: g('.jname'),
                    salary: g('.sal'),
                    city: g('.area'),
                    company: g('.cname'),
                };
            }
        """)
        all_cards.append(fields)
    
    log.append(f"Total cards found: {len(all_cards)}")
    valid = [c for c in all_cards if c and c.get("id")]
    log.append(f"Valid (with ID): {len(valid)}")
    for c in valid[:5]:
        log.append(f"  ID={c['id']} {c.get('title','')} @ {c.get('company','')}")
    for c in all_cards[:5]:
        if not c or not c.get("id"):
            log.append(f"  INVALID: {c}")
    
    # Step 4: Visit detail pages
    log.append("\n=== Step 4: Detail page ===")
    
    # Dedup
    seen_ids = set()
    unique = []
    for c in valid:
        if c["id"] not in seen_ids:
            seen_ids.add(c["id"])
            unique.append(c)
    valid = unique
    
    for i, card in enumerate(valid[:max_count]):
        city_prefix = "hangzhou"
        if "余杭" in (card.get("city") or ""):
            city_prefix = "hangzhou-yhq"
        elif "滨江" in (card.get("city") or ""):
            city_prefix = "hangzhou-bjq"
        elif "西湖" in (card.get("city") or ""):
            city_prefix = "hangzhou-xhq"
        elif "上城" in (card.get("city") or ""):
            city_prefix = "hangzhou-scq"
        elif "拱墅" in (card.get("city") or ""):
            city_prefix = "hangzhou-gsq"
        elif "萧山" in (card.get("city") or ""):
            city_prefix = "hangzhou-xsq"
        
        jd_url = f"https://jobs.51job.com/{city_prefix}/{card['id']}.html"
        log.append(f"\nVisiting {jd_url}")
        await page.goto(jd_url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        
        page_title = await page.title()
        log.append(f"  Page title: '{page_title}'")
        
        body_text = await page.inner_text("body")
        log.append(f"  Body length: {len(body_text)}")
        
        # Check stop keywords
        has_stop_kw = any(kw in body_text for kw in [
            "已停止招聘", "该职位已停止", "职位已关闭", "已下线",
            "停止招聘", "职位过期", "不再招聘",
            "暂不招聘", "该岗位已关闭", "招聘已结束",
            "该职位已暂停", "职位已失效", "已经暂停招聘"
        ])
        log.append(f"  Has stop keyword: {has_stop_kw}")
        
        # Try JD extraction
        jd_el = await page.query_selector(".tCompany_main .tBorderTop_box")
        if jd_el:
            jd_text = await jd_el.inner_text()
            log.append(f"  JD found via .tCompany_main .tBorderTop_box: {len(jd_text)} chars")
        else:
            jd_el = await page.query_selector(".tBorderTop_box")
            if jd_el:
                jd_text = await jd_el.inner_text()
                log.append(f"  JD found via .tBorderTop_box: {len(jd_text)} chars")
            else:
                log.append(f"  No JD selector matched")
                log.append(f"  Body preview: {body_text[:300]}")
    
    with open(r"D:\trae\projects\answerresume\job_seeker\crawl_debug7.log", "w", encoding="utf-8") as f:
        f.write("\n".join(log))

if __name__ == "__main__":
    asyncio.run(main())
