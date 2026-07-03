"""Check 51job city codes - simplified."""
import asyncio
from playwright.async_api import async_playwright

async def main():
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0]
    
    log = []
    
    # Try different city codes on we.51job.com
    for city_name, code in [("北京", "010000"), ("上海", "020000"), ("深圳", "040000"), ("杭州", "080200")]:
        test_url = f"https://we.51job.com/pc/search?keyword=产品经理&jobArea={code}&searchType=2"
        await page.goto(test_url, wait_until="domcontentloaded")
        await asyncio.sleep(3)
        title = await page.title()
        
        # Get job count if possible
        cards = await page.query_selector_all(".joblist-item-job-wrapper")
        log.append(f"{city_name} (jobArea={code}): {len(cards)} cards, title: {title[:60]}")
    
    for line in log:
        print(line)
    
    with open(r"D:\trae\projects\answerresume\job_seeker\city_test.log", "w", encoding="utf-8") as f:
        f.write("\n".join(log))
    
    await p.stop()

if __name__ == "__main__":
    asyncio.run(main())
