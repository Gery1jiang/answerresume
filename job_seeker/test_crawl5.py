"""Analyze new 51job search page card structure."""
import asyncio, json
from playwright.async_api import async_playwright

async def main():
    log = []
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0]
    
    # Go to new search page directly (it loads fine from CDP Chrome)
    await page.goto("https://we.51job.com/pc/search?keyword=%E4%BA%A7%E5%93%81%E7%BB%8F%E7%90%86&jobArea=080200&searchType=2", 
                    wait_until="domcontentloaded")
    await asyncio.sleep(5)
    
    log.append(f"URL: {page.url}")
    log.append(f"Title: '{await page.title()}'")
    
    # Try various card selectors
    for sel in [".joblist-item-job-wrapper", ".joblist-item", ".el", 
                "[class*=joblist]", ".job-card", ".card-item"]:
        cards = await page.query_selector_all(sel)
        log.append(f"Selector '{sel}': {len(cards)} cards")
    
    # Get details from the first card
    cards = await page.query_selector_all(".joblist-item-job-wrapper")
    if cards:
        html = await cards[0].inner_html()
        log.append(f"\n--- Full first card HTML ---\n{html[:2000]}")
        
        # Also try evaluate to extract structured fields
        fields = await cards[0].evaluate("""
            el => {
                const html = el.outerHTML;
                // Try different patterns
                const sensorsMatch = html.match(/jobId[=:"]+(\d+)/);
                const titleEl = el.querySelector('.job-name, [class*=title], h3, a');
                const salaryEl = el.querySelector('.job-salary, [class*=salary], .sal');
                const companyEl = el.querySelector('.job-company, [class*=company], .cname');
                const areaEl = el.querySelector('.job-area, [class*=area], .area');
                const urlEl = el.querySelector('a[href*=jobs]');
                return {
                    sensorsJobId: sensorsMatch ? sensorsMatch[1] : '',
                    title: titleEl ? titleEl.textContent.trim() : '',
                    salary: salaryEl ? salaryEl.textContent.trim() : '',
                    company: companyEl ? companyEl.textContent.trim() : '',
                    area: areaEl ? areaEl.textContent.trim() : '',
                    href: urlEl ? urlEl.getAttribute('href') : '',
                    allLinks: Array.from(el.querySelectorAll('a')).map(a => a.href).join(' | '),
                };
            }
        """)
        log.append(f"\n--- Parsed fields ---")
        for k, v in fields.items():
            log.append(f"{k}: {v}")
    
    with open(r"D:\trae\projects\answerresume\job_seeker\crawl_debug5.log", "w", encoding="utf-8") as f:
        f.write("\n".join(log))

if __name__ == "__main__":
    asyncio.run(main())
