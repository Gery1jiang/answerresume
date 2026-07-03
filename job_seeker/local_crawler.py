"""
Local Chrome crawler: connects to your already-logged-in Chrome via CDP.
No Docker, no stealth tricks - just your real browser.

Usage:
  1. Start Chrome with remote debugging:
     google-chrome --remote-debugging-port=9222
     (Windows: "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222)

  2. Run this script:
     python3 job_seeker/local_crawler.py "Python后端" "北京"

  3. Results will be saved to the system via API.
"""
import asyncio
import json
import sys
import httpx
from playwright.async_api import async_playwright

BACKEND_URL = "http://localhost:51666"
ADMIN_TOKEN = ""


async def connect_chrome():
    """Connect to user's already-running Chrome via CDP."""
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    return p, browser


async def extract_jobs(page) -> list:
    """Extract job cards from BOSS直聘 search results page."""
    jobs = []
    try:
        await page.wait_for_selector(".job-card-wrapper", timeout=10000)
        cards = await page.query_selector_all(".job-card-wrapper")
        for card in cards[:30]:
            try:
                title = await card.query_selector_eval(".job-name", "el => el.textContent.trim()")
                company = await card.query_selector_eval(".company-name", "el => el.textContent.trim()")
                salary = await card.query_selector_eval(".salary", "el => el.textContent.trim()")
                city = await card.query_selector_eval(".job-area", "el => el.textContent.trim()")
                link_el = await card.query_selector("a.job-card-link")
                link = await link_el.get_attribute("href") if link_el else ""
                jobs.append({
                    "platform": "boss",
                    "title": title.strip(),
                    "company": company.strip(),
                    "city": city.strip(),
                    "salary": salary.strip(),
                    "jd_url": f"https://www.zhipin.com{link}" if link else "",
                    "jd_text": f"{title.strip()} {company.strip()} {salary.strip()}",
                })
            except Exception:
                continue
    except Exception as e:
        print(f"  ⚠ 提取岗位失败: {e}")
    return jobs


async def crawl(keywords: str, city: str = ""):
    """Main crawl flow: connect Chrome → search → extract → submit."""
    print(f"🔍 正在抓取: {keywords} {city}")
    print(f"   连接到本地 Chrome (localhost:9222)...")

    p, browser = await connect_chrome()
    context = browser.contexts[0]
    page = await context.new_page()

    try:
        city_param = f"&city={city}" if city else ""
        url = f"https://www.zhipin.com/web/geek/job?query={keywords}{city_param}"
        print(f"   打开 BOSS直聘: {url}")
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)

        # Check if login is needed
        page_text = await page.inner_text("body")
        if "登录" in page_text and len(page_text) < 200:
            print("   ⚠ 未登录，请在打开的浏览器中扫码登录...")
            await asyncio.sleep(5)

        jobs = await extract_jobs(page)
        print(f"   ✅ 提取到 {len(jobs)} 个岗位")

        # Submit to backend
        if jobs:
            token = await _get_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{BACKEND_URL}/admin/jobs/crawl-submit",
                    headers={"Authorization": f"Bearer {token}"},
                    json={"jobs": jobs},
                    timeout=30,
                )
                if resp.status_code == 200:
                    print(f"   ✅ 已保存 {len(jobs)} 个岗位到系统")
                else:
                    print(f"   ⚠ 保存失败: {resp.text}")
        else:
            print("   ⚠ 未提取到岗位")

    finally:
        await page.close()
        await p.stop()


async def _get_token() -> str:
    """Login to backend and get admin token."""
    global ADMIN_TOKEN
    if ADMIN_TOKEN:
        return ADMIN_TOKEN
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BACKEND_URL}/admin/login",
            json={"username": "admin", "password": "admin123"},
        )
        if resp.status_code == 200:
            ADMIN_TOKEN = resp.json()["access_token"]
            return ADMIN_TOKEN
        print(f"   ⚠ 登录后端失败: {resp.text}")
        return ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("用法: python3 local_crawler.py <关键词> [城市]")
        print("示例: python3 local_crawler.py Python后端 北京")
        sys.exit(1)

    keywords = sys.argv[1]
    city = sys.argv[2] if len(sys.argv) > 2 else ""
    asyncio.run(crawl(keywords, city))
