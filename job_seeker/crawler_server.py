"""
Crawler HTTP server - runs on Windows, called by backend when you click "抓取".
Start this in the background, then use the Job Radar page normally.

Usage:
  python crawler_server.py
  # Server starts on http://localhost:8800
  # Backend will auto-detect and use it
"""
import asyncio, json, os, sys, random, re, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from playwright.async_api import async_playwright


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle multiple requests concurrently — crawls can't block health checks."""
    daemon_threads = True

# Fix GBK encoding on Windows — scraped HTML often contains \xa0 (non-breaking space)
# which causes UnicodeEncodeError when Python tries to print/encode with GBK.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stdout, "reconfigure") else None
    sys.stderr.reconfigure(encoding="utf-8", errors="replace") if hasattr(sys.stderr, "reconfigure") else None

def _clean(text: str) -> str:
    return text.replace("\xa0", " ")

from boss_parser import (
    intercept_job_detail_via_cdp,
    build_jd_text_from_api,
    extract_header_from_json,
    parse_boss_header_text,
    CITY_CODES as BOSS_CITY_CODES,
)

# 51job 城市编码（we.51job.com/pc/search?jobArea=CODE）
JOBAREA_CODES = {
    "北京": "010000", "上海": "020000", "深圳": "040000",
    "杭州": "080200", "广州": "030200", "成都": "090200",
    "武汉": "170200", "南京": "070000", "西安": "200200",
    "苏州": "150200", "天津": "050000", "重庆": "060000",
}

CITY_PREFIXES = {
    "余杭": "hangzhou-yhq", "滨江": "hangzhou-bjq",
    "西湖": "hangzhou-xhq", "上城": "hangzhou-scq",
    "拱墅": "hangzhou-gsq", "萧山": "hangzhou-xsq",
}

# 智联招聘 城市编码（fe-api.zhaopin.com/c/i/city 返回）
ZHAOPIN_CITY_CODES = {
    "北京": "530", "上海": "538", "广州": "763", "深圳": "765",
    "杭州": "653", "成都": "801", "武汉": "736", "南京": "635",
    "西安": "854", "苏州": "639", "天津": "531", "重庆": "551",
}


async def extract_card(page, idx):
    """Extract structured fields from a job card."""
    cards = await page.query_selector_all(".joblist-item-job-wrapper, .joblist-item, .el")
    if idx >= len(cards):
        return None
    card = cards[idx]

    fields = await card.evaluate("""
        el => {
            const html = el.outerHTML;
            // Extract job ID from card link URL first
            let jobId = '';
            const link = el.querySelector('a[href*="jobs.51job.com"]');
            if (link) {
                const href = link.getAttribute('href') || '';
                const m = href.match(/(\\d+)\\.html/);
                if (m) jobId = m[1];
            }
            if (!jobId) {
                const sdEl = el.querySelector('[sensorsdata]');
                if (sdEl) {
                    const sd = sdEl.getAttribute('sensorsdata');
                    if (sd) {
                        try {
                            const parsed = JSON.parse(sd);
                            jobId = parsed.jobId || '';
                        } catch(e) {}
                    }
                }
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
    if not fields:
        return None  # No more cards

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
        # Check for "X年经验", "无需经验", "经验不限"
        m = re.search(r'(无需经验|经验不限|应届生|(\d+)年(以上)?经验)', line)
        if m:
            result["experience_required"] = m.group(1)

        # Check for education at end of pipe-delimited segment
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
    start_kw = ["职位信息", "岗位职责", "任职要求", "工作内容", "岗位要求", "职位描述", "职位描述"]
    end_kw = ["公司信息", "公司介绍", "工作地址", "上班地址", "职能类别", "51Job安全提醒", "公司优势"]

    # Try to find start keywords
    start = -1
    for i, line in enumerate(lines):
        if any(kw in line for kw in start_kw):
            start = i
            break

    if start < 0:
        # Fallback: find content after job title keywords
        for i, line in enumerate(lines):
            if any(kw in line for kw in ["岗位", "职责", "要求", "工作内容", "职位"]):
                if len(line) > 5 and len(line) < 50:
                    start = i
                    break

    if start < 0:
        # Last resort: take the middle 100 lines (skip navigation/footer)
        skip = max(len(lines) // 4, 10)
        return "\n".join(lines[skip:skip+60])[:3000]

    end = len(lines)
    for i in range(start + 1, len(lines)):
        if any(kw in line for kw in end_kw):
            end = i
            break

    result = "\n".join(lines[start:end])[:3000]
    if len(result) < 50:
        # Too short, use fallback
        skip = max(len(lines) // 4, 10)
        result = "\n".join(lines[skip:skip+60])[:3000]
    return result


async def do_crawl(keywords: str, city: str = "", sort: str = "time", max_count: int = 5):
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0]

    import re
    import urllib.parse

    # Build search URL with city code if specified
    city_code = JOBAREA_CODES.get(city, "") if city else ""
    if city_code:
        search_url = f"https://we.51job.com/pc/search?keyword={urllib.parse.quote(keywords)}&jobArea={city_code}&searchType=2"
    else:
        search_url = f"https://we.51job.com/pc/search?keyword={urllib.parse.quote(keywords)}&searchType=2"
    if sort == "time":
        search_url += "&sort=time"
    await page.goto(search_url, wait_until="domcontentloaded")
    await asyncio.sleep(5)

    for i in range(5):
        await page.evaluate(f"window.scrollTo(0, {i * 800})")
        await asyncio.sleep(1)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(2)

    # Extract all valid cards (up to max_count * 2 to find enough passing jobs)
    all_cards = []
    for i in range(min(max_count * 3, 60)):
        card = await extract_card(page, i)
        if not card:
            break
        all_cards.append(card)

    valid = [c for c in all_cards if c and c.get("id")]
    # 按 job id 去重（51job 列表页会重复展示同一岗位）
    seen_ids = set()
    unique = []
    for c in valid:
        if c["id"] not in seen_ids:
            seen_ids.add(c["id"])
            unique.append(c)
    valid = unique
    results = []

    if valid:
        for i, card in enumerate(valid[:max_count]):
            if i > 0:
                delay = random.randint(1, 4)
                print(f"[CrawlerServer] 等待 {delay} 秒后抓取下一个...")
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
                    print(f"[CrawlerServer] Header matched selector '{sel}': {header_text[:200]}")
                    break
            if header_el:
                header_parsed = parse_header(header_text)
            else:
                body_text = _clean(await page.inner_text("body"))
                for line in body_text.split("\n"):
                    line = line.strip()
                    if re.search(r'(无需经验|经验不限|应届生|\d+年.*经验|大专|本科|硕士|博士)', line) and len(line) < 200:
                        header_text = line
                        break
                if header_text:
                    header_parsed = parse_header(header_text)
                else:
                    print(f"[CrawlerServer] WARNING: no header found on {card['jd_url']}")

            jd_el = await page.query_selector(".tCompany_main .tBorderTop_box")
            if jd_el:
                jd_clean = _clean((await jd_el.inner_text()).strip()[:3000])
            else:
                jd_el = await page.query_selector(".tBorderTop_box")
                if jd_el:
                    jd_clean = _clean((await jd_el.inner_text()).strip()[:3000])
                else:
                    body = _clean(await page.inner_text("body"))
                    jd_clean = await clean_jd(body)

            # 检测是否已停招
            body_text = _clean(await page.inner_text("body"))
            if any(kw in body_text for kw in ["已停止招聘", "该职位已停止", "职位已关闭", "已下线",
                                                "停止招聘", "职位过期", "不再招聘",
                                                "暂不招聘", "该岗位已关闭", "招聘已结束",
                                                "该职位已暂停", "职位已失效", "已经暂停招聘"]):
                print(f"[CrawlerServer] 跳过已停招岗位: {card.get('title', '')}")
                continue

            work_addr = ""
            addr_re = re.search(r'(?:上班地址|工作地址|工作地点)[：:]\s*([^\n]{2,60})', jd_clean)
            if addr_re:
                work_addr = addr_re.group(1).strip()

            results.append({
                "title": _clean(str(card.get("title", ""))[:100]),
                "company": _clean(str(card.get("company", ""))),
                "city": _clean(str(card.get("city", ""))),
                "salary": _clean(str(card.get("salary", ""))),
                "jd_url": str(card.get("jd_url", "")),
                "platform": str(card.get("platform", "51job")),
                "jd_text": str(jd_clean)[:3000],
                "jd_parsed": json.dumps(header_parsed, ensure_ascii=False),
                "work_address": work_addr,
            })

    await p.stop()
    return results


async def do_crawl_boss(keywords: str, city: str = "", sort: str = "time", max_count: int = 5):
    """Crawl BOSS直聘 job listings via Chrome CDP + API interception.

    BOSS直聘 uses a React SPA — job cards and details load via XHR API calls.
    This function intercepts those calls to extract structured data.
    """
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0]

    search_url = "https://www.zhipin.com/web/geek/job"
    params = [f"query={keywords}"]
    if city and city in BOSS_CITY_CODES:
        params.append(f"city={BOSS_CITY_CODES[city]}")
    # BOSS排序: 默认=综合, time=最新
    if sort == "time":
        params.append("scene=1")  # 最新发布
    search_url += "?" + "&".join(params)

    await page.goto(search_url, wait_until="domcontentloaded")
    await asyncio.sleep(4)

    for i in range(5):
        await page.evaluate(f"window.scrollTo(0, {i * 600})")
        await asyncio.sleep(0.5)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(2)

    job_list_response = None
    async def capture_job_list(response):
        nonlocal job_list_response
        if "/wapi/zpgeek/search/joblist.json" in response.url or "/wapi/zpjob/search/joblist" in response.url:
            try:
                data = await response.json()
                job_list_response = data
            except Exception:
                pass

    page.on("response", capture_job_list)
    await asyncio.sleep(3)

    cards_data = []

    if job_list_response:
        zp_data = job_list_response.get("zpData", job_list_response)
        job_list = zp_data.get("jobList", [])
        for item in job_list:
            job_id = item.get("jobId", "")
            if not job_id:
                continue
            cards_data.append({
                "id": str(job_id),
                "title": item.get("jobName", ""),
                "salary": item.get("salaryDesc", ""),
                "city": " ".join(p for p in [item.get("cityName", ""), item.get("areaDistrict", "")] if p),
                "company": item.get("brandName", ""),
                "jd_url": f"https://www.zhipin.com/job_detail/{job_id}.html",
                "platform": "boss",
            })
        print(f"[CrawlerServer] BOSS直聘: extracted {len(cards_data)} jobs from API response")
    else:
        print("[CrawlerServer] BOSS直聘: API interception failed, trying DOM extraction")
        cards = await page.query_selector_all(".job-card-wrapper, .job-list-box > div")
        for i, card in enumerate(cards[:30]):
            fields = await card.evaluate("""
                el => {
                    const html = el.innerHTML;
                    const idMatch = html.match(/job_detail[\\/](\\d+)/);
                    const g = s => { const e = el.querySelector(s); return e ? (e.textContent || '').trim() : ''; };
                    return {
                        id: idMatch ? idMatch[1] : '',
                        title: g('.job-name, .job-title, .job-card-title'),
                        salary: g('.salary'),
                        city: g('.job-area, .city'),
                        company: g('.company-name, .brand-name'),
                    };
                }
            """)
            if fields and fields.get("id"):
                fields["jd_url"] = f"https://www.zhipin.com/job_detail/{fields['id']}.html"
                fields["platform"] = "boss"
                cards_data.append(fields)

    valid = [c for c in cards_data if c and c.get("id")]

    results = []
    if valid:
        for i, card in enumerate(valid[:max_count]):
            if i > 0:
                delay = random.randint(1, 4)
                print(f"[CrawlerServer] BOSS等待 {delay} 秒后抓取下一个...")
                await asyncio.sleep(delay)

            job_data = None
            try:
                result = await intercept_job_detail_via_cdp(
                    "http://localhost:9222",
                    card["id"],
                    timeout=30,
                )
                jd_text = _clean(str(result.get("jd_text", ""))[:3000])

                # 检测是否已停招
                if any(kw in jd_text for kw in ["已停止招聘", "该职位已停止", "职位已关闭", "已下线",
                                                  "停止招聘", "职位过期", "不再招聘"]):
                    print(f"[CrawlerServer] BOSS跳过已停招: {card.get('title', '')}")
                    continue

                job_data = {
                    "title": str(card.get("title", ""))[:100],
                    "company": str(card.get("company", "")),
                    "city": str(card.get("city", "")),
                    "salary": str(card.get("salary", "")),
                    "jd_url": str(card.get("jd_url", "")),
                    "platform": "boss",
                    "jd_text": jd_text,
                    "jd_parsed": result.get("jd_parsed", "{}"),
                    "work_address": _clean(result.get("work_address", "")),
                }
            except Exception as e:
                print(f"[CrawlerServer] BOSS detail page failed for {card.get('id')}: {e}")
                job_data = {
                    "title": str(card.get("title", ""))[:100],
                    "company": str(card.get("company", "")),
                    "city": str(card.get("city", "")),
                    "salary": str(card.get("salary", "")),
                    "jd_url": str(card.get("jd_url", "")),
                    "platform": "boss",
                    "jd_text": "",
                    "jd_parsed": "{}",
                    "work_address": "",
                }
            if job_data:
                results.append(job_data)

    await p.stop()
    return results


async def do_crawl_zhaopin(keywords: str, city: str = "", sort: str = "time", max_count: int = 5):
    """Crawl 智联招聘 job listings via Chrome CDP.

    智联招聘 uses SPA with Tencent EdgeOne protection.
    This navigates in the user's real Chrome (already logged in, captcha solved)
    and extracts job cards from the page.
    """
    p = await async_playwright().start()
    browser = await p.chromium.connect_over_cdp("http://localhost:9222")
    ctx = browser.contexts[0]
    page = ctx.pages[0]

    # Build search URL
    city_code = ZHAOPIN_CITY_CODES.get(city, "489") if city else "489"  # 489=全国
    search_url = f"https://www.zhaopin.com/sou/?kw={keywords}&city={city_code}&sortType=1"
    await page.goto(search_url, wait_until="domcontentloaded")
    await asyncio.sleep(5)

    for i in range(5):
        await page.evaluate(f"window.scrollTo(0, {i * 600})")
        await asyncio.sleep(0.5)
    await page.evaluate("window.scrollTo(0, 0)")
    await asyncio.sleep(2)

    # Extract job cards via multiple selector strategies
    cards_data = []
    selectors = [
        ".job-card-container", ".positionlist-item", ".job-list-item",
        ".job-card-wrapper", "[class*='job-card']", "[class*='position']",
        ".sou-s-result", ".result-list", ".job-list-box > div",
    ]

    job_cards = []
    for sel in selectors:
        job_cards = await page.query_selector_all(sel)
        if job_cards:
            print(f"[CrawlerServer] 智联招聘: found {len(job_cards)} cards with selector '{sel}'")
            break

    if job_cards:
        for i, card in enumerate(job_cards[:min(max_count * 3, 30)]):
            try:
                fields = await card.evaluate("""
                    el => {
                        const html = el.innerHTML;
                        const text = el.textContent || '';
                        const g = s => { const e = el.querySelector(s); return e ? (e.textContent||'').trim() : ''; };

                        // Extract job ID from href or data attributes
                        let jobId = '';
                        const links = el.querySelectorAll('a[href]');
                        for (const a of links) {
                            const href = a.getAttribute('href') || '';
                            const m = href.match(/position\\/detail\\/(\\d+)/);
                            if (m) { jobId = m[1]; break; }
                            const m2 = href.match(/job_detail[\\/](\\d+)/);
                            if (m2) { jobId = m2[1]; break; }
                            const m3 = href.match(/job\\/(\\d+)/);
                            if (m3) { jobId = m3[1]; break; }
                        }
                        if (!jobId) {
                            const match = html.match(/data-id[=\"\\s]+(\\d+)/);
                            if (match) jobId = match[1];
                        }

                        return {
                            id: jobId,
                            title: g('.job-name, .job-title, .position-name, .job-name-text, h2, h3'),
                            salary: g('.salary, .salary-range, .job-salary'),
                            city: g('.city, .job-area, .job-city, .location, .address'),
                            company: g('.company-name, .brand-name, .company-title, .company'),
                            html_preview: html.substring(0, 200),
                        };
                    }
                """)
                if fields and fields.get("id"):
                    jd_url = f"https://www.zhaopin.com/position/detail/{fields['id']}"
                    fields["jd_url"] = jd_url
                    fields["platform"] = "zhaopin"
                    cards_data.append(fields)
            except Exception as e:
                print(f"[CrawlerServer] 智联招聘 card extract error: {e}")
                continue

    if not cards_data:
        # Fallback: try to find any job-like data in the page
        print("[CrawlerServer] 智联招聘: selector extraction failed, trying text-based extraction")
        body_text = await page.inner_text("body")
        if body_text:
            print(f"[CrawlerServer] 智联招聘: page text (first 500): {body_text[:500]}")

    valid = [c for c in cards_data if c and c.get("id")]
    print(f"[CrawlerServer] 智联招聘: extracted {len(valid)} valid job cards")

    results = []
    if valid:
        for i, card in enumerate(valid[:max_count]):
            if i > 0:
                delay = random.randint(1, 4)
                print(f"[CrawlerServer] 智联招聘等待 {delay} 秒后抓取下一个...")
                await asyncio.sleep(delay)

            # Navigate to job detail page
            try:
                await page.goto(card["jd_url"], wait_until="domcontentloaded", timeout=30000)
                await asyncio.sleep(3)
            except Exception as e:
                print(f"[CrawlerServer] 智联招聘 detail page goto failed: {e}")
                results.append({
                    "title": str(card.get("title", ""))[:100],
                    "company": str(card.get("company", "")),
                    "city": str(card.get("city", "")),
                    "salary": str(card.get("salary", "")),
                    "jd_url": str(card.get("jd_url", "")),
                    "platform": "zhaopin",
                    "jd_text": "",
                    "jd_parsed": "{}",
                    "work_address": "",
                })
                continue

            # Extract JD text from detail page
            jd_text = ""
            work_address = ""
            try:
                jd_selectors = [
                    ".job-description", ".position-detail", ".job-detail",
                    ".job-require", ".description-content", ".detail-content",
                    ".job-sec", ".tab-inner", "#job_detail", ".job-content",
                    ".detail-wrap", ".job-box",
                ]
                for sel in jd_selectors:
                    el = await page.query_selector(sel)
                    if el:
                        jd_text = _clean(await el.inner_text())
                        if len(jd_text) > 50:
                            print(f"[CrawlerServer] 智联招聘 JD matched selector '{sel}': {len(jd_text)} chars")
                            break

                if not jd_text or len(jd_text) < 50:
                    jd_text = _clean(await page.inner_text("body"))
                    # Truncate to reasonable length
                    lines = [l.strip() for l in jd_text.split("\n") if l.strip()]
                    # Try to find meaningful content (skip header/footer)
                    start = 0
                    for j, line in enumerate(lines):
                        if any(kw in line for kw in ["职位描述", "岗位职责", "任职要求", "工作内容", "岗位要求", "职位信息"]):
                            start = j
                            break
                    if start > 0:
                        jd_text = "\n".join(lines[start:start+80])[:3000]
                    else:
                        mid = max(len(lines) // 3, 5)
                        jd_text = "\n".join(lines[mid:mid+60])[:3000]

                # Extract work address
                addr_m = re.search(r'(?:上班地址|工作地址|工作地点|办公地址)[：:]\s*([^\n]{2,60})', jd_text)
                if addr_m:
                    work_address = addr_m.group(1).strip()

            except Exception as e:
                print(f"[CrawlerServer] 智联招聘 JD text extraction failed: {e}")

            results.append({
                "title": str(card.get("title", ""))[:100],
                "company": str(card.get("company", "")),
                "city": str(card.get("city", "")),
                "salary": str(card.get("salary", "")),
                "jd_url": str(card.get("jd_url", "")),
                "platform": "zhaopin",
                "jd_text": str(jd_text)[:3000],
                "jd_parsed": "{}",
                "work_address": work_address,
            })

    await p.stop()
    return results


class CrawlerHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path == "/crawl":
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length)) if length else {}
            keywords = body.get("keywords", "Python")
            city = body.get("city", "")
            platform = body.get("platform", "51job")
            sort = body.get("sort", "time")
            max_count = min(int(body.get("max_count", 5)), 10)
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if platform == "boss":
                    results = loop.run_until_complete(
                        asyncio.wait_for(do_crawl_boss(keywords, city, sort, max_count), timeout=180))
                elif platform == "zhaopin":
                    results = loop.run_until_complete(
                        asyncio.wait_for(do_crawl_zhaopin(keywords, city, sort, max_count), timeout=180))
                else:
                    results = loop.run_until_complete(
                        asyncio.wait_for(do_crawl(keywords, city, sort, max_count), timeout=180))
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"success": True, "count": len(results), "jobs": results}).encode())
            except Exception as e:
                self.send_response(500)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                err_type = type(e).__name__
                err_msg = str(e)[:200]
                self.wfile.write(json.dumps({"success": False, "error": f"[{err_type}] {err_msg}"}).encode())
            finally:
                loop.close()
        else:
            self.send_response(404)
            self.end_headers()
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ready"}).encode())
    def log_message(self, format, *args):
        print(f"[CrawlerServer] {args[0]} {args[1]} {args[2]}")


if __name__ == "__main__":
    port = 8800
    print(f"Crawler Server starting on http://localhost:{port}")
    print("Keep this window open. Use the Job Radar page to trigger crawls.")
    server = ThreadingHTTPServer(("0.0.0.0", port), CrawlerHandler)
    server.serve_forever()
