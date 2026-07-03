"""Check actual page content from 51job."""
import asyncio, sys
from playwright.async_api import async_playwright

async def main():
    log_lines = []
    
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0]
    
    url = "https://search.51job.com/list/000000,000000,0000,00,9,99,%E4%BA%A7%E5%93%81%E7%BB%8F%E7%90%86,2,1.html?lang=c"
    await page.goto(url, wait_until="domcontentloaded")
    await asyncio.sleep(5)
    
    log_lines.append(f"URL: {page.url}")
    log_lines.append(f"Title: '{await page.title()}'")
    
    body_text = await page.inner_text("body")
    log_lines.append(f"Body length: {len(body_text)}")
    log_lines.append(f"Body preview: {body_text[:2000]}")
    
    html = await page.content()
    log_lines.append(f"HTML length: {len(html)}")
    log_lines.append(f"HTML preview: {html[:2000]}")
    
    with open(r"D:\trae\projects\answerresume\job_seeker\crawl_debug3.log", "w", encoding="utf-8") as f:
        f.write("\n".join(log_lines))

if __name__ == "__main__":
    asyncio.run(main())
