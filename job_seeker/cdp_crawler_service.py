"""
CDP-based crawler service — runs in Docker, connects to Windows Chrome via CDP.
Falls back to standalone browser if CDP is unavailable.

The backend calls us at http://cdp-crawler:8000/crawl when you click "抓取".
"""
import asyncio, json, os, sys, random, re, logging
from fastapi import FastAPI
from pydantic import BaseModel
from contextlib import asynccontextmanager
from playwright.async_api import async_playwright

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("cdp-crawler")

CDP_URL = os.environ.get("CDP_URL", "http://host.docker.internal:9222")

CITY_PREFIXES = {
    "余杭": "hangzhou-yhq", "滨江": "hangzhou-bjq",
    "西湖": "hangzhou-xhq", "上城": "hangzhou-scq",
    "拱墅": "hangzhou-gsq", "萧山": "hangzhou-xsq",
}


def _clean(text: str) -> str:
    return text.replace("\xa0", " ")


async def extract_card(page, idx):
    cards = await page.query_selector_all(".joblist-item, .el")
    if idx >= len(cards):
        return None
    card = cards[idx]
    fields = await card.evaluate("""
        el => {
            const html = el.innerHTML;
            const idMatch = html.match(/171\\d{6,}/);
            const g = s => { const e = el.querySelector(s); return e ? (e.textContent || '').trim() : ''; };
            return {
                id: idMatch ? idMatch[0] : '',
                title: g('.jname'),
                salary: g('.sal'),
                city: g('.area'),
                company: g('.cname'),
            };
        }
    """)
    if not fields:
        return None
    if not fields.get("id"):
        return {"id": "", "title": fields.get("title", ""), "company": "", "city": "", "salary": "", "jd_url": "", "platform": ""}
    city_prefix = "hangzhou"
    for name, prefix in CITY_PREFIXES.items():
        if name in (fields.get("city") or ""):
            city_prefix = prefix
            break
    fields["jd_url"] = f"https://jobs.51job.com/{city_prefix}/{fields['id']}.html"
    fields["platform"] = "51job"
    return fields


def parse_header(header_text: str) -> dict:
    import re
    header_text = _clean(header_text)
    lines = [l.strip() for l in header_text.split("\n") if l.strip()]
    result = {"education": "", "experience_required": ""}
    for line in lines:
        m = re.search(r'(无需经验|经验不限|应届生|(\d+)年(以上)?经验)', line)
        if m:
            result["experience_required"] = m.group(1)
        for seg in line.split("|"):
            seg = seg.strip()
            for kw in ["博士", "硕士", "本科", "大专", "专科", "不限"]:
                if kw in seg:
                    result["education"] = kw
                    break
    return result


async def clean_jd(body_text):
    body_text = _clean(body_text)
    lines = [l.strip() for l in body_text.split("\n") if l.strip()]
    start_kw = ["职位信息", "岗位职责", "任职要求", "工作内容", "岗位要求", "职位描述"]
    end_kw = ["公司信息", "公司介绍", "工作地址", "上班地址", "职能类别", "51Job安全提醒", "公司优势"]
    start = -1
    for i, line in enumerate(lines):
        if any(kw in line for kw in start_kw):
            start = i
            break
    if start < 0:
        for i, line in enumerate(lines):
            if any(kw in line for kw in ["岗位", "职责", "要求", "工作内容", "职位"]):
                if len(line) > 5 and len(line) < 50:
                    start = i
                    break
    if start < 0:
        skip = max(len(lines) // 4, 10)
        return "\n".join(lines[skip:skip+60])[:3000]
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if any(kw in line for kw in end_kw):
            end = i
            break
    result = "\n".join(lines[start:end])[:3000]
    if len(result) < 50:
        skip = max(len(lines) // 4, 10)
        result = "\n".join(lines[skip:skip+60])[:3000]
    return result


async def do_crawl_51job(page, keywords: str, city: str = "", sort: str = "time", max_count: int = 5):
    """Crawl 51job using the given CDP-connected page."""
    import re
    sort_param = "&sort=time" if sort == "time" else ""
    search_url = f"https://search.51job.com/list/000000,000000,0000,00,9,99,{keywords},2,1.html?lang=c{sort_param}"
    logger.info(f"Navigating to 51job: {search_url}")
    await page.goto(search_url, wait_until="domcontentloaded")
    await asyncio.sleep(2)
    search = await page.query_selector("#search-input")
    if search:
        await search.click()
        await asyncio.sleep(0.3)
        for ch in keywords:
            await page.keyboard.type(ch, delay=random.randint(60, 180))
            await asyncio.sleep(random.uniform(0.01, 0.05))
    await page.keyboard.press("Enter")
    await asyncio.sleep(5)
    for i in range(5):
        await page.evaluate(f"window.scrollTo(0, {i * 800})")
        await asyncio.sleep(1)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(2)

    all_cards = []
    for i in range(min(max_count * 3, 60)):
        card = await extract_card(page, i)
        if not card:
            break
        all_cards.append(card)

    valid = [c for c in all_cards if c and c.get("id")]
    results = []
    if valid:
        for i, card in enumerate(valid[:max_count]):
            if i > 0:
                delay = random.randint(1, 4)
                await asyncio.sleep(delay)
            await page.goto(card["jd_url"], wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            header_parsed = {}
            header_selectors = [
                ".tHeader.tHjob", ".tHeader", ".cn", ".in",
                ".job_detail_header", ".job_msg", "#job_detail",
            ]
            header_text = ""
            header_el = None
            for sel in header_selectors:
                header_el = await page.query_selector(sel)
                if header_el:
                    header_text = _clean(await header_el.inner_text())
                    break
            if header_el:
                header_parsed = parse_header(header_text)
            body_el = await page.query_selector(".job_msg")
            if not body_el:
                body_el = await page.query_selector(".bmsg")
            if not body_el:
                body_el = await page.query_selector("#job_detail")
            jd_text = ""
            if body_el:
                jd_text = _clean(await body_el.inner_text())
            if not jd_text or len(jd_text) < 50:
                jd_text = await clean_jd(await page.inner_text("body"))
            results.append({
                "platform": "51job",
                "title": card.get("title", ""),
                "company": card.get("company", ""),
                "city": card.get("city", ""),
                "salary": card.get("salary", ""),
                "jd_text": jd_text,
                "jd_url": card.get("jd_url", ""),
                "work_address": "",
                "education": header_parsed.get("education", ""),
                "experience_required": header_parsed.get("experience_required", ""),
            })
    return results


async def do_crawl(page, keywords: str, city: str = "", sort: str = "time", max_count: int = 5):
    """
    Main crawl function.
    Tries 51job first, returns whatever we find.
    """
    try:
        return await do_crawl_51job(page, keywords, city, sort, max_count)
    except Exception as e:
        logger.error(f"51job crawl failed: {e}")
        raise


app = FastAPI(title="CDP Crawler Service")


class CrawlRequest(BaseModel):
    keywords: str
    city: str = ""
    platform: str = "51job"
    max_count: int = 5
    sort: str = "time"


class CrawlResponse(BaseModel):
    success: bool
    message: str
    jobs: list = []


@app.post("/crawl")
async def crawl(req: CrawlRequest):
    logger.info(f"Crawl request: keywords={req.keywords}, city={req.city}, platform={req.platform}")
    p = None
    browser = None
    try:
        p = await async_playwright().start()
        logger.info("Launching standalone Chromium browser (no CDP)...")
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage"],
        )
        context = await browser.new_context(
            locale="zh-CN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        jobs = await do_crawl(page, req.keywords, req.city, req.sort, req.max_count)
        if not jobs:
            return CrawlResponse(success=False, message="未抓取到岗位数据", jobs=[])
        return CrawlResponse(success=True, message=f"找到 {len(jobs)} 个岗位", jobs=jobs)
    except Exception as e:
        logger.error(f"Crawl failed: {e}")
        return CrawlResponse(success=False, message=f"抓取失败: {str(e)}")
    finally:
        if browser:
            await browser.close()
        if p:
            await p.stop()


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
