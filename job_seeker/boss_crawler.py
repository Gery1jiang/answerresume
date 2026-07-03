import json
import os
import asyncio
from playwright.async_api import async_playwright
from stealth import get_browser_config

COOKIE_FILE = "/data/boss_cookie.json"
SEARCH_URL_TEMPLATE = "https://www.zhipin.com/web/geek/job?query={keywords}&city={city_code}"
CITY_CODES = {
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280100",
    "深圳": "101280600",
    "杭州": "101210100",
    "成都": "101270100",
    "武汉": "101200100",
    "南京": "101190100",
    "西安": "101110100",
}


async def ensure_login(page):
    """Load saved cookies if available, otherwise prompt for QR scan."""
    if os.path.exists(COOKIE_FILE):
        with open(COOKIE_FILE, "r") as f:
            cookies = json.load(f)
        await page.context.add_cookies(cookies)
        return True
    return False


async def save_cookies(page):
    """Persist cookies after successful login."""
    cookies = await page.context.cookies()
    os.makedirs(os.path.dirname(COOKIE_FILE), exist_ok=True)
    with open(COOKIE_FILE, "w") as f:
        json.dump(cookies, f, ensure_ascii=False)


async def extract_jobs(page) -> list:
    """Extract job listings from the current search results page."""
    jobs = []
    try:
        # Wait for job cards to load
        await page.wait_for_selector(".job-card-wrapper", timeout=10000)
        cards = await page.query_selector_all(".job-card-wrapper")
        for card in cards[:20]:
            try:
                title_el = await card.query_selector(".job-name")
                company_el = await card.query_selector(".company-name")
                salary_el = await card.query_selector(".salary")
                city_el = await card.query_selector(".job-area")
                link_el = await card.query_selector("a.job-card-link")

                title = await title_el.inner_text() if title_el else ""
                company = await company_el.inner_text() if company_el else ""
                salary = await salary_el.inner_text() if salary_el else ""
                city = await city_el.inner_text() if city_el else ""
                link = await link_el.get_attribute("href") if link_el else ""

                # Click to open job detail in a new approach: extract from card text
                jd_text = title + " " + company + " " + salary

                jobs.append({
                    "platform": "boss",
                    "title": title.strip(),
                    "company": company.strip(),
                    "city": city.strip(),
                    "salary": salary.strip(),
                    "jd_url": f"https://www.zhipin.com{link}" if link else "",
                    "jd_text": jd_text,
                })
            except Exception:
                continue
    except Exception:
        pass
    return jobs


async def search_boss_jobs(keywords: str, city: str = "", pages: int = 1) -> list:
    """
    Search BOSS直聘 for jobs matching keywords.
    Returns a list of job dicts.
    """
    config = get_browser_config()
    all_jobs = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=config["launch_args"],
        )
        context = await browser.new_context(**config["context_args"])

        # Inject stealth script
        await context.add_init_script(config["stealth_script"])

        page = await context.new_page()

        # Load cookies
        logged_in = await ensure_login(page)

        city_code = CITY_CODES.get(city, "")
        url = SEARCH_URL_TEMPLATE.format(
            keywords=keywords,
            city_code=city_code or "100010000",
        )

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Check if login is required
            if not logged_in:
                page_text = await page.inner_text("body")
                if "登录" in page_text and len(page_text) < 500:
                    print("BOSS直聘需要登录，请在浏览器中扫码...")
                    # Save screenshot for user to scan QR code
                    await page.screenshot(path="/data/boss_login.png")
                    # Wait for login (poll every 5s, max 120s)
                    for _ in range(24):
                        await asyncio.sleep(5)
                        current = await page.inner_text("body")
                        if "登录" not in current or len(current) > 500:
                            await save_cookies(page)
                            print("登录成功")
                            break

            # Extract jobs from current page
            jobs = await extract_jobs(page)
            all_jobs.extend(jobs)

            # Navigate to more pages if requested
            for p in range(2, pages + 1):
                try:
                    next_btn = await page.query_selector(".next")
                    if next_btn:
                        await next_btn.click()
                        await asyncio.sleep(3)
                        more = await extract_jobs(page)
                        all_jobs.extend(more)
                except Exception:
                    break

        except Exception as e:
            print(f"Crawl error: {e}")
        finally:
            await browser.close()

    return all_jobs
