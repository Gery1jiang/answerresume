"""
Windows-native crawler: launches Chrome + scrapes BOSS直聘 in one go.
  python D:\trae\projects\answerresume\job_seeker\win_crawler.py "Python后端" 北京
"""
import asyncio, sys, os, subprocess, json, time
os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
from playwright.async_api import async_playwright
import httpx

BACKEND = "http://localhost:51666"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
USER_DATA_DIR = r"C:\temp\chrome-debug"
CDP_PORT = 9222


def ensure_chrome():
    """Start Chrome with CDP if not already running."""
    try:
        r = httpx.get(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=3)
        if r.status_code == 200:
            return
    except:
        pass
    print("启动 Chrome (远程调试模式)...")
    subprocess.Popen([
        CHROME_PATH,
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={USER_DATA_DIR}",
        "--new-window", "about:blank",
    ], shell=False)
    for i in range(15):
        try:
            r = httpx.get(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=2)
            if r.status_code == 200:
                print("  Chrome 已就绪")
                return
        except:
            pass
        time.sleep(1)
    print("  Chrome 启动超时")


async def crawl(keywords: str, city: str = ""):
    print(f"搜索: {keywords} {city}")
    ensure_chrome()
    token = await get_token()

    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://localhost:{CDP_PORT}")
        ctx = browser.contexts[0]
        page = await ctx.new_page()

        city_code = {"北京": "101010100", "上海": "101020100", "深圳": "101280600",
                     "杭州": "101210100", "广州": "101280100", "成都": "101270100"}.get(city, "")
        params = f"query={keywords}"
        if city_code:
            params += f"&city={city_code}"
        search_url = f"https://www.zhipin.com/web/geek/job?{params}"

        # Navigate + handle login redirects
        for attempt in range(3):
            print(f"  导航 ({attempt+1})...")
            try:
                resp = await page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
                print(f"  goto: HTTP {resp.status if resp else '?'}, url={page.url[:60]}")
            except Exception as e:
                print(f"  goto failed: {e}")
            if "about:" in page.url:
                print(f"  page URL stuck on about:blank, using evaluate navigation")
                await page.evaluate(f"window.location.replace('{search_url}')")
                await asyncio.sleep(5)
            await asyncio.sleep(3)

            curr = page.url
            title = (await page.title() or "")[:60]
            print(f"  尝试 {attempt+1}: {title}")

            if "/geek/job" not in curr:
                print("  BOSS直聘需登录，请在打开的 Chrome 中扫码...")
                for i in range(30):
                    await asyncio.sleep(3)
                    curr = page.url
                    if "/geek/job" in curr:
                        print("  登录成功")
                        break
                    if i % 5 == 4:
                        print(f"  等待 { (i+1)*3 } 秒...")
                else:
                    print("  登录超时")
                    await page.close()
                    return
            else:
                break

        # Wait for job list to render
        await asyncio.sleep(5)
        print(f"  URL: {page.url}")

        # Try multiple selectors for job cards
        cards = []
        for sel in [".job-card-wrapper", "[class*=job-card]", ".job-list-box",
                     "[data-jobid]", "[class*=position]", "li[class*=job]"]:
            cards = await page.query_selector_all(sel)
            if cards:
                print(f"  选择器 '{sel}': {len(cards)} 个岗位")
                break

        if not cards:
            body = (await page.inner_text("body"))[:300].replace("\n", " ")
            print(f"  未找到岗位卡片. 页面内容: {body}...")
            await page.close()
            return

        # Extract job info
        jobs = []
        for card in cards[:30]:
            try:
                info = await card.inner_text()
                lines = [l.strip() for l in info.split("\n") if l.strip()]
                title = lines[0] if lines else ""
                jobs.append({
                    "platform": "boss",
                    "title": title,
                    "company": lines[1] if len(lines) > 1 else "",
                    "city": lines[3] if len(lines) > 3 else city,
                    "salary": lines[2] if len(lines) > 2 else "",
                    "jd_text": info[:200],
                })
            except:
                pass

        await page.close()
        print(f"  提取 {len(jobs)} 个岗位")

        if jobs:
            r = httpx.post(f"{BACKEND}/admin/jobs/crawl-submit",
                headers={"Authorization": f"Bearer {token}"},
                json={"jobs": jobs}, timeout=30)
            print(f"  已保存: {r.json()['message']}")

        print(f"\n  http://localhost:51668/jobs 刷新查看")


async def get_token():
    r = httpx.post(f"{BACKEND}/admin/login",
                   json={"username": "admin", "password": "admin123"}, timeout=10)
    return r.json()["access_token"]


if __name__ == "__main__":
    kw = sys.argv[1] if len(sys.argv) > 1 else "Python"
    city = sys.argv[2] if len(sys.argv) > 2 else ""
    asyncio.run(crawl(kw, city))
