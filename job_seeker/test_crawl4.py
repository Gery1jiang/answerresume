"""Debug crawler homepage flow."""
import asyncio, sys
from playwright.async_api import async_playwright

async def main():
    log = []
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0]
    
    log.append(f"Initial URL: {page.url}")
    log.append(f"Initial title: '{await page.title()}'")
    
    # Step 1: go to 51job homepage
    await page.goto("https://www.51job.com/", wait_until="domcontentloaded")
    await asyncio.sleep(4)
    log.append(f"After goto homepage - URL: {page.url}")
    log.append(f"After goto homepage - title: '{await page.title()}'")
    
    body = await page.inner_text("body")
    log.append(f"Body length: {len(body)}")
    log.append(f"Body preview: {body[:500]}")
    
    # Step 2: find search input
    search = await page.query_selector("#search-input")
    log.append(f"Search input found: {search is not None}")
    
    if search:
        placeholder = await search.get_attribute("placeholder")
        log.append(f"Placeholder: {placeholder}")
        await search.click()
        await asyncio.sleep(0.3)
        await page.keyboard.press("Control+A")
        await page.keyboard.press("Delete")
        for ch in "产品经理":
            await page.keyboard.type(ch, delay=50)
            await asyncio.sleep(0.02)
        await asyncio.sleep(0.5)
        await page.keyboard.press("Enter")
        await asyncio.sleep(6)
        log.append(f"After search - URL: {page.url}")
        log.append(f"After search - title: '{await page.title()}'")
        
        cards = await page.query_selector_all(".joblist-item, .el")
        log.append(f"Cards found: {len(cards)}")
        if cards:
            html = await cards[0].inner_html()
            log.append(f"First card: {html[:300]}")
    
    with open(r"D:\trae\projects\answerresume\job_seeker\crawl_debug4.log", "w", encoding="utf-8") as f:
        f.write("\n".join(log))

if __name__ == "__main__":
    asyncio.run(main())
