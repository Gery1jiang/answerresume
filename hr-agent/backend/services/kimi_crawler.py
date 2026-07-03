"""Kimi WebBridge - 通过真实浏览器批量抓取招聘岗位"""

import json
import os
import re
import urllib.parse
import asyncio
import httpx
from typing import Optional

DAEMON_URL = os.environ.get(
    "KIMI_DAEMON_URL",
    "http://kimi-relay:10087/command"
)

SLEEP_AFTER_NAV = 5
SLEEP_BETWEEN_SCROLLS = 2
SLEEP_AFTER_CLICK = 3
SLEEP_BETWEEN_PAGES = 3
MAX_CARDS = 20


def _clean_work_address(raw: str) -> str:
    """清洗工作地址：去重、去地图垃圾、公司信息等"""
    if not raw:
        return ""
    # 去掉 "点击查看地图..." 及其后面的全部内容
    raw = re.split(r'点击查看地图|查看地图', raw)[0].strip()
    # 去掉 "公司信息" 及其后面的全部内容
    raw = re.split(r'公司信息', raw)[0].strip()
    # 去掉 "热门 " 及其后面的全部内容（找工作时间等）
    raw = re.split(r'热门\s', raw)[0].strip()
    # 去掉 "©" 版权信息
    raw = re.split(r'©', raw)[0].strip()
    # 去掉 "安全提醒" 及其后面的
    raw = re.split(r'安全提醒', raw)[0].strip()
    # 去掉地址重复：取第一个含省/市/区/县的较长句子
    # 如果包含空格分隔的重复（如 "A B" 且 B 是 A 的后缀），取第一个
    if '  ' in raw:
        raw = raw.split('  ')[0].strip()
    elif ' ' in raw:
        parts = raw.split(' ')
        if len(parts) >= 2 and len(parts[0]) > len(parts[1]) and parts[0].endswith(parts[1]):
            raw = parts[0]
    return raw.strip()

# City mapping for 51job search
CITY_MAP_51JOB = {
    "北京": "010000", "上海": "020000", "深圳": "040000", "杭州": "080200",
    "广州": "030200", "成都": "090200", "武汉": "170200", "南京": "070000",
    "苏州": "150200", "天津": "050000", "重庆": "110000", "西安": "200200",
}

CITY_PINYIN = {
    "北京": "beijing", "上海": "shanghai", "深圳": "shenzhen", "杭州": "hangzhou",
    "广州": "guangzhou", "成都": "chengdu", "武汉": "wuhan", "南京": "nanjing",
    "苏州": "suzhou", "天津": "tianjin", "重庆": "chongqing", "西安": "xian",
}


async def _cmd(action: str, args: dict, session: str = "job-crawl", timeout: float = 35) -> dict:
    print(f"[kimi_cmd] {action} session={session} args_keys={list(args.keys())}")
    _last_err = None
    for _attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=timeout) as cli:
                resp = await cli.post(DAEMON_URL, json={"action": action, "args": args, "session": session})
                if resp.status_code != 200:
                    return {"success": False, "error": f"HTTP {resp.status_code}"}
                body = resp.json()
                if not body.get("ok"):
                    err = body.get("error", {})
                    return {"success": False, "error": err.get("message", str(err))}
                return {"success": True, **(body.get("data", {}))}
        except (httpx.ConnectError, httpx.RemoteProtocolError, httpx.TimeoutException, ConnectionError) as e:
            _last_err = e
            print(f"[kimi_cmd] {action} attempt {_attempt+1} failed: {e}")
            await asyncio.sleep(2 ** _attempt)
        except Exception as e:
            print(f"[kimi_cmd] {action} fatal: {e}")
            return {"success": False, "error": str(e)}
    print(f"[kimi_cmd] {action} exhausted retries")
    return {"success": False, "error": str(_last_err)}


# ── 51job 搜索列表提取 ──

CARD_JS_51JOB = """(() => {
  const items = [];
  const seen = new Set();
  document.querySelectorAll('.joblist-item').forEach(el => {
    const sensorsRaw = el.querySelector('[sensorsdata]')?.getAttribute?.('sensorsdata') || '{}';
    let jobId = '';
    let rawTime = '';
    try { const s = JSON.parse(sensorsRaw); jobId = s.jobId || ''; rawTime = s.jobTime || ''; } catch(e) {}
    const title = (el.querySelector('.jname')?.textContent || '').trim();
    const company = (el.querySelector('.cname')?.textContent || '').trim();
    const key = title + '|' + company;
    if (!title || !company || seen.has(key)) return;
    seen.add(key);
    const salary = (el.querySelector('.sal')?.textContent || '').trim();
    const area = (el.querySelector('.area')?.textContent || '').trim();
    const desc = (el.querySelector('.bc')?.textContent || '').trim();
    const tags = Array.from(el.querySelectorAll('.joblist-item-tags .tag, .tags .tag')).map(t => t.textContent.trim()).join(' ');
    const city = area.split(/[·\\s]/)[0] || '';
    const pinyin = {'北京':'beijing','上海':'shanghai','深圳':'shenzhen','杭州':'hangzhou','广州':'guangzhou','成都':'chengdu','武汉':'wuhan','南京':'nanjing','苏州':'suzhou','天津':'tianjin','重庆':'chongqing','西安':'xian'};
    const cityPinyin = pinyin[city] || 'all';
    const jdUrl = jobId ? 'https://jobs.51job.com/' + cityPinyin + '/' + jobId + '.html' : '';
    const fullText = (title + ' ' + salary + ' ' + area + ' ' + company + ' ' + desc + ' ' + tags).substring(0, 600);
    items.push({jobId, title, company, salary, city, area, url: jdUrl, jd_text: fullText, postedAt: rawTime});
  });
  return JSON.stringify(items);
})()"""


async def _fetch_jd_text(url: str, session: str) -> dict:
    """Navigate to JD detail page, scroll, and extract full JD text, work address, company info."""
    r = await _cmd("navigate", {"url": url, "newTab": True, "group_title": "岗位雷达详情"}, session)
    if not r.get("success"):
        return {"jd_text": "", "work_address": "", "company_info": ""}
    await asyncio.sleep(SLEEP_AFTER_NAV)

    # Scroll down gradually to trigger lazy loading
    for _ in range(4):
        r = await _cmd("evaluate", {"code": "window.scrollBy(0, 600)"}, session)
        await asyncio.sleep(1)
    await asyncio.sleep(2)

    # Extract detail info
    r = await _cmd("evaluate", {"code": """
(() => {
  const txt = document.body.textContent || '';

  // JD text: prefer .job_msg or .bmsg
  let jdText = '';
  const jdEl = document.querySelector('.job_msg') || document.querySelector('.bmsg');
  if (jdEl) jdText = jdEl.textContent.trim();
  else {
    const markers = ['岗位职责', '职位描述', '任职要求', '工作内容', '职位信息'];
    for (const m of markers) {
      const idx = txt.indexOf(m);
      if (idx >= 0) { jdText = txt.substring(idx, idx + 3000).trim(); break; }
    }
  }
  if (!jdText) jdText = txt.substring(0, 3000).trim();

  // Work address: after "工作地址" until next section
  let workAddr = '';
  const addrIdx = txt.indexOf('工作地址');
  if (addrIdx >= 0) {
    const after = txt.substring(addrIdx + 4, addrIdx + 300);
    const m = after.match(/[\\u4e00-\\u9fa5]{2,8}[省市区县].*?(?=\\n\\s*\\n|公司信息|©|$)/s);
    if (m) workAddr = m[0].trim();
    else workAddr = after.split(/\\n/).find(l => l.includes('区') || l.includes('路') || l.includes('大道') || l.includes('街') || l.includes('号'))?.trim() || '';
  }

  // Company info from bottom section
  let companyInfo = '';
  const ciIdx = txt.indexOf('公司信息');
  if (ciIdx >= 0) {
    companyInfo = txt.substring(ciIdx + 4, ciIdx + 600).trim();
    const cut = companyInfo.search(/\\n\\s*\\n[\\u4e00-\\u9fa5]{2,6}[：:]/);
    if (cut > 0) companyInfo = companyInfo.substring(0, cut).trim();
  }

  return JSON.stringify({jdText, workAddr, companyInfo});
})();
"""}, session)
    result = {"jd_text": "", "work_address": "", "company_info": ""}
    if r.get("success"):
        raw = r.get("value", "{}")
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            result["jd_text"] = (parsed.get("jdText") or "").strip()
            result["work_address"] = _clean_work_address(parsed.get("workAddr") or "")
            result["company_info"] = (parsed.get("companyInfo") or "").strip()
        except json.JSONDecodeError:
            pass
    await _cmd("close_tab", {}, session)
    return result


async def crawl_51job(keywords: str, city: str = "", max_count: int = 3, start_page: int = 1,
                      skip_urls: set = None, skip_keys: set = None) -> list[dict]:
    """Kimi WebBridge 抓取 51job，含详情页 JD 文本"""
    if skip_urls is None: skip_urls = set()
    if skip_keys is None: skip_keys = set()
    params = urllib.parse.urlencode({"keyword": keywords, "searchType": "2"})
    if city:
        c = CITY_MAP_51JOB.get(city, "")
        if c:
            params += f"&jobArea={c}"
    search_url = f"https://we.51job.com/pc/search?{params}"
    session = f"51job-{int(asyncio.get_event_loop().time() * 1000) % 100000}"
    all_jobs = []

    r = await _cmd("navigate", {"url": search_url, "newTab": True, "group_title": "岗位雷达"}, session)
    if not r.get("success"):
        return []
    await asyncio.sleep(SLEEP_AFTER_NAV)

    # 选中「最新优先」排序
    r = await _cmd("evaluate", {"code": """
(() => {
  const btns = document.querySelectorAll('span.ss');
  for (const b of btns) {
    if (b.textContent.includes('最新优先')) {
      b.click();
      return true;
    }
  }
  return false;
})();
"""}, session)
    if r.get("value") == True:
        await asyncio.sleep(3)

    # 滚动加载更多
    for _ in range(3):
        await _cmd("evaluate", {"code": "window.scrollBy(0, 1000)"}, session)
        await asyncio.sleep(SLEEP_BETWEEN_SCROLLS)

    # 翻页，最多收集 max_count 个
    for page in range(start_page, start_page + 5):
        if len(all_jobs) >= max_count:
            break
        if page > start_page:
            clicked = await _cmd("evaluate", {"code": """
(() => {
  const nextBtn = document.querySelector('.btn-next');
  if (nextBtn && !nextBtn.classList.contains('disabled')) {
    nextBtn.click();
    return true;
  }
  return false;
})();
"""}, session)
            if not clicked.get("value"):
                break
            await asyncio.sleep(SLEEP_BETWEEN_PAGES)
            for _ in range(2):
                await _cmd("evaluate", {"code": "window.scrollBy(0, 800)"}, session)
                await asyncio.sleep(SLEEP_BETWEEN_SCROLLS)

        # 提取当前页卡片
        r = await _cmd("evaluate", {"code": CARD_JS_51JOB}, session)
        if not r.get("success"):
            continue
        raw = r.get("value", "[]")
        try:
            cards = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            continue

        # 去重（跳过已爬过的） + 取 JD 详情
        seen_keys = {f"{j['title']}|{j['company']}" for j in all_jobs}
        print(f"[51job] page {page}: found {len(cards)} cards, have {len(all_jobs)} jobs")
        for card in cards:
            if len(all_jobs) >= max_count:
                break
            card_key = f"{card.get('title','')}|{card.get('company','')}"
            if card_key in seen_keys:
                continue
            seen_keys.add(card_key)

            jd_url = card.get("url", "")
            title = card.get("title", "")
            company = card.get("company", "")
            key = f"{title}|{company}"

            # 跳过已存在的岗位（url 匹配 或 title+company 匹配）
            if (jd_url and jd_url in skip_urls) or (title and company and key in skip_keys):
                continue

            # 获取详情页 JD 文本
            detail = {"jd_text": "", "work_address": "", "company_info": ""}
            if jd_url:
                detail = await _fetch_jd_text(jd_url, session)

            all_jobs.append({
                "platform": "51job",
                "title": card.get("title", ""),
                "company": card.get("company", ""),
                "city": card.get("city", city),
                "salary": card.get("salary", ""),
                "jd_text": detail.get("jd_text") or card.get("jd_text", ""),
                "jd_url": jd_url,
                "jd_parsed": {"platform": "51job", "jobId": card.get("jobId", "")},
                "work_address": _clean_work_address(detail.get("work_address") or ""),
                "company_info": detail.get("company_info", ""),
            })

    await _cmd("close_tab", {}, session)
    return all_jobs[:max_count]


async def crawl_boss(keywords: str, city: str = "", max_count: int = 3,
                     skip_urls: set = None, skip_keys: set = None) -> list[dict]:
    """Kimi WebBridge 抓取 BOSS 直聘"""
    if skip_urls is None: skip_urls = set()
    if skip_keys is None: skip_keys = set()
    city_map = {"北京": "101010100", "上海": "101020100", "深圳": "101280600",
                "杭州": "101210100", "广州": "101280100", "成都": "101270100",
                "武汉": "101200101", "南京": "101190100", "西安": "101110101"}
    c = city_map.get(city, "")
    params = f"query={urllib.parse.quote(keywords)}" + (f"&city={c}" if c else "")
    search_url = f"https://www.zhipin.com/web/geek/job?{params}"
    session = f"boss-{int(asyncio.get_event_loop().time() * 1000) % 100000}"
    jobs = []

    r = await _cmd("navigate", {"url": search_url, "newTab": True, "group_title": "岗位雷达"}, session)
    if not r.get("success"):
        return []
    await asyncio.sleep(SLEEP_AFTER_NAV)

    for _ in range(2):
        await _cmd("evaluate", {"code": "window.scrollBy(0, 800)"}, session)
        await asyncio.sleep(SLEEP_BETWEEN_SCROLLS)

    r = await _cmd("evaluate", {"code": """
(() => {
  const items = [];
  const seen = new Set();
  document.querySelectorAll('.job-card-wrapper').forEach(el => {
    const title = el.querySelector('.job-name')?.textContent?.trim() || '';
    if (!title || seen.has(title)) return;
    seen.add(title);
    const salary = el.querySelector('.salary')?.textContent?.trim() || '';
    const company = el.querySelector('.company-name')?.textContent?.trim() || '';
    const area = el.querySelector('.job-area')?.textContent?.trim() || '';
    const link = el.querySelector('a');
    const jdUrl = link ? link.href : '';
    const jd = el.querySelector('.job-desc')?.textContent?.trim() || '';
    const fullText = title + ' ' + salary + ' ' + area + ' ' + company + ' ' + jd;
    items.push({title, company, salary, city: area.split(/[·\\s-/]/)[0] || '', url: jdUrl, jd_text: fullText.substring(0, 600)});
  });
  return JSON.stringify(items);
})();
"""}, session)
    if r.get("success"):
        raw = r.get("value", "[]")
        try:
            cards = json.loads(raw) if isinstance(raw, str) else raw
            for card in cards[:max_count]:
                jd_url = card.get("url", "")
                title = card.get("title", "")
                company = card.get("company", "")
                key = f"{title}|{company}"
                if (jd_url and jd_url in skip_urls) or (title and company and key in skip_keys):
                    continue
                detail = {"jd_text": "", "work_address": ""}
                if jd_url:
                    detail = await _fetch_jd_text(jd_url, session)
                jobs.append({
                    "platform": "boss", "title": card.get("title", ""),
                    "company": card.get("company", ""), "city": card.get("city", city),
                    "salary": card.get("salary", ""), "jd_text": detail.get("jd_text") or card.get("jd_text", ""),
                    "jd_url": jd_url, "jd_parsed": {"platform": "boss"},
                    "work_address": _clean_work_address(detail.get("work_address") or ""),
                    "company_info": detail.get("company_info", ""),
                })
        except json.JSONDecodeError:
            pass

    await _cmd("close_tab", {}, session)
    return jobs


async def crawl_zhaopin(keywords: str, city: str = "", max_count: int = 5,
                        skip_urls: set = None, skip_keys: set = None) -> list[dict]:
    """Kimi WebBridge 抓取 智联招聘"""
    if skip_urls is None: skip_urls = set()
    if skip_keys is None: skip_keys = set()
    search_url = f"https://sou.zhaopin.com/?jl=489&kw={urllib.parse.quote(keywords)}&p=1"
    session = f"zhaopin-{int(asyncio.get_event_loop().time() * 1000) % 100000}"
    jobs = []

    r = await _cmd("navigate", {"url": search_url, "newTab": True, "group_title": "岗位雷达"}, session)
    if not r.get("success"):
        return []
    await asyncio.sleep(SLEEP_AFTER_NAV)

    for _ in range(2):
        await _cmd("evaluate", {"code": "window.scrollBy(0, 800)"}, session)
        await asyncio.sleep(SLEEP_BETWEEN_SCROLLS)

    r = await _cmd("evaluate", {"code": """
(() => {
  const items = [];
  const seen = new Set();
  document.querySelectorAll('.positionlist-item, .job-item, [class*=\"position\"]>div').forEach(el => {
    const titleEl = el.querySelector('.job-name, .position-name, [class*=\"title\"]');
    const title = titleEl ? titleEl.textContent.trim() : '';
    if (!title || seen.has(title)) return;
    seen.add(title);
    const salary = el.querySelector('.salary, [class*=\"salary\"]')?.textContent?.trim() || '';
    const company = el.querySelector('.company-name, .company_title')?.textContent?.trim() || '';
    const area = el.querySelector('.city, .job-area, [class*=\"city\"]')?.textContent?.trim() || '';
    const link = el.querySelector('a');
    const jdUrl = link ? link.href : '';
    const jd = el.querySelector('.job-desc, [class*=\"desc\"]')?.textContent?.trim() || '';
    const fullText = title + ' ' + salary + ' ' + area + ' ' + company + ' ' + jd;
    items.push({title, company, salary, city: area.split(/[·\\s]/)[0] || '', url: jdUrl, jd_text: fullText.substring(0, 600)});
  });
  return JSON.stringify(items);
})();
"""}, session)
    if r.get("success"):
        raw = r.get("value", "[]")
        try:
            cards = json.loads(raw) if isinstance(raw, str) else raw
            for card in cards[:max_count]:
                jd_url = card.get("url", "")
                title = card.get("title", "")
                company = card.get("company", "")
                key = f"{title}|{company}"
                if (jd_url and jd_url in skip_urls) or (title and company and key in skip_keys):
                    continue
                detail = {"jd_text": "", "work_address": ""}
                if jd_url:
                    detail = await _fetch_jd_text(jd_url, session)
                jobs.append({
                    "platform": "zhaopin", "title": card.get("title", ""),
                    "company": card.get("company", ""), "city": card.get("city", city),
                    "salary": card.get("salary", ""), "jd_text": detail.get("jd_text") or card.get("jd_text", ""),
                    "jd_url": jd_url, "jd_parsed": {"platform": "zhaopin"},
                    "work_address": _clean_work_address(detail.get("work_address") or ""),
                    "company_info": detail.get("company_info", ""),
                })
        except json.JSONDecodeError:
            pass

    await _cmd("close_tab", {}, session)
    return jobs


async def crawl(keywords: str, city: str = "杭州", platform: str = "51job", max_count: int = 3,
                skip_urls: set = None, skip_keys: set = None) -> list[dict]:
    """统一入口"""
    if skip_urls is None: skip_urls = set()
    if skip_keys is None: skip_keys = set()
    if platform == "boss":
        return await crawl_boss(keywords, city, max_count, skip_urls, skip_keys)
    elif platform == "zhaopin":
        return await crawl_zhaopin(keywords, city, max_count, skip_urls, skip_keys)
    else:
        return await crawl_51job(keywords, city, max_count, skip_urls=skip_urls, skip_keys=skip_keys)
