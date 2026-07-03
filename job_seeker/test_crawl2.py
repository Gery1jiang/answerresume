"""Debug crawler step by step."""
import asyncio, sys, json
from playwright.async_api import async_playwright

async def main():
    log = []
    def debug(msg):
        log.append(msg)
        print(msg)
    
    p = await async_playwright().start()
    debug("Connected to playwright")
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    debug("Connected to CDP")
    debug(f"Contexts: {len(browser.contexts)}")
    ctx = browser.contexts[0]
    debug(f"Pages in ctx[0]: {len(ctx.pages)}")
    page = ctx.pages[0]
    
    url = "https://search.51job.com/list/000000,000000,0000,00,9,99,%E4%BA%A7%E5%93%81%E7%BB%8F%E7%90%86,2,1.html?lang=c"
    debug(f"Navigating to {url}")
    await page.goto(url, wait_until="domcontentloaded")
    debug(f"Page title: {await page.title()}")
    debug(f"Page URL: {page.url}")
    
    await asyncio.sleep(3)
    
    cards = await page.query_selector_all(".joblist-item, .el")
    debug(f"Cards found: {len(cards)}")
    
    if cards:
        html = await cards[0].inner_html()
        debug(f"First card HTML (500 chars): {html[:500]}")
    
    with open(r"D:\trae\projects\answerresume\job_seeker\crawl_debug2.log", "w", encoding="utf-8") as f:
        f.write("\n".join(log))
    debug("Done")

if __name__ == "__main__":
    asyncio.run(main())
