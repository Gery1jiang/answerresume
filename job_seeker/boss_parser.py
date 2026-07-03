"""Parse BOSS直聘 job detail pages using Chrome CDP + API interception.

BOSS直聘 is a React SPA — job details load via XHR API calls, not in initial HTML.
This module uses Playwright CDP to intercept the API response for detail data,
extracting structured fields directly from the JSON rather than parsing DOM.
"""

import json
import re
import asyncio
from playwright.async_api import async_playwright

API_JOB_DETAIL = "/wapi/zpgeek/job/detail.json"
API_JOB_DETAIL_V2 = "/wapi/zpjob/job/detail"

CITY_CODES = {
    "北京": "100010000", "上海": "100020000", "深圳": "100030000",
    "广州": "100040000", "杭州": "100210000", "成都": "100270000",
    "南京": "100190000", "武汉": "100170000", "西安": "100260000",
    "苏州": "200240000",
}

RE_EXPERIENCE = re.compile(r'(无需经验|经验不限|应届生|在校生|(\d+)[-~]?(\d+)?年(以上)?经验)')
RE_EDUCATION = re.compile(r'(博士|硕士|本科|大专|专科|中专|高中|不限)')
RE_SALARY = re.compile(r'(\d+[\.\d]*)[kK]?[-~](\d+[\.\d]*)[kK]')


def parse_boss_header_text(header_text: str) -> dict:
    """Parse BOSS直聘 job header text (from API or HTML) into structured fields.

    Typical formats handled:
      "20K-40K · 13薪"  or  "2万-4万"
      "杭州 经验不限 本科"
      "杭州·西湖区 经验3-5年 本科"
    """
    result = {
        "education": "",
        "experience_required": "",
        "experience_years": 0,
    }

    lines = [l.strip() for l in header_text.replace("·", "|").split("\n") if l.strip()]

    for line in lines:
        m = RE_EXPERIENCE.search(line)
        if m:
            result["experience_required"] = m.group(1)
            if m.group(2):
                try:
                    result["experience_years"] = int(m.group(2))
                except ValueError:
                    pass

        # `len(seg) < 20` avoids matching degree keywords inside a long company name
        for seg in line.replace("·", "|").split("|"):
            seg = seg.strip()
            edu_m = RE_EDUCATION.search(seg)
            if edu_m and len(seg) < 20:
                result["education"] = edu_m.group(1)
                break

    return result


def extract_header_from_json(job_detail: dict) -> dict:
    """Extract structured header fields from BOSS直聘 detail API JSON."""
    result = {"education": "", "experience_required": "", "experience_years": 0}

    info = job_detail.get("jobInfo") or job_detail.get("jobDetail") or job_detail

    experience_name = info.get("experienceName") or ""
    degree_name = info.get("degreeName") or ""
    salary_desc = info.get("salaryDesc") or ""

    if experience_name:
        result["experience_required"] = experience_name
        ym = re.search(r'(\d+)[-~](\d+)年', experience_name)
        if ym:
            try:
                result["experience_years"] = (int(ym.group(1)) + int(ym.group(2))) // 2
            except ValueError:
                pass
        elif "不限" in experience_name or "无需" in experience_name:
            result["experience_years"] = 0

    if degree_name:
        for kw in ["博士", "硕士", "本科", "大专", "专科", "不限"]:
            if kw in degree_name:
                result["education"] = kw
                break

    if salary_desc and not result.get("salary_min"):
        sm = RE_SALARY.search(salary_desc)
        if sm:
            try:
                result["salary_min"] = float(sm.group(1)) / 10  # K → 万
                result["salary_max"] = float(sm.group(2)) / 10
            except ValueError:
                pass

    return result


def clean_boss_jd_text(jd_html_or_text: str) -> str:
    """Clean BOSS直聘 JD description text.

    BOSS直聘 descriptions often come as HTML with rich formatting.
    Strip tags and normalize whitespace.
    """
    text = re.sub(r'<br\s*/?>', '\n', jd_html_or_text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = text.strip()
    return text[:3000]


async def intercept_job_detail_via_cdp(
    browser_ws_endpoint: str,
    job_id: str,
    timeout: int = 30,
) -> dict:
    """Navigate to a BOSS直聘 job detail page via CDP and intercept the API response.

    Args:
        browser_ws_endpoint: CDP WebSocket URL (e.g. http://localhost:9222)
        job_id: BOSS直聘 job ID
        timeout: Max wait seconds for API response

    Returns:
        Parsed job detail dict with raw API response merged.
    """
    p = await async_playwright().start()
    try:
        browser = await p.chromium.connect_over_cdp(browser_ws_endpoint)
        ctx = browser.contexts[0]
        page = ctx.pages[0]

        url = f"https://www.zhipin.com/job_detail/{job_id}.html"

        # Set up API response interception
        response_data = {}

        async def handle_response(response):
            if API_JOB_DETAIL in response.url or API_JOB_DETAIL_V2 in response.url:
                try:
                    data = await response.json()
                    response_data["raw"] = data
                except Exception:
                    pass

        page.on("response", handle_response)

        await page.goto(url, wait_until="domcontentloaded", timeout=timeout * 1000)
        await asyncio.sleep(3)  # Let SPA load and make API calls

        # If API interception worked, use it
        if response_data.get("raw"):
            raw = response_data["raw"]
            zp_data = raw.get("zpData", raw)
            job_detail = zp_data.get("jobDetail", zp_data)

            # Extract header info from JSON
            header = extract_header_from_json(job_detail)

            # Get JD text
            jd_text_raw = (
                job_detail.get("jobDetail", "") or
                job_detail.get("postDescription", "") or
                job_detail.get("description", "") or
                ""
            )
            jd_text = clean_boss_jd_text(jd_text_raw)

            # If JD text is too short, fall back to HTML extraction
            if len(jd_text) < 100:
                body_text = await page.inner_text("body")
                jd_text = clean_boss_jd_text(body_text)

            city_name = job_detail.get("cityName", "")
            area = job_detail.get("areaDistrict", "")
            biz = job_detail.get("businessDistrict", "")
            work_addr = " ".join(p for p in [city_name, area, biz] if p)

            return {
                "jd_text": jd_text,
                "jd_parsed": json.dumps(header, ensure_ascii=False),
                "work_address": work_addr,
                "header_parsed": header,
                "raw_api": True,
            }

        # Fallback: parse from page HTML
        body_text = await page.inner_text("body")
        jd_text = clean_boss_jd_text(body_text)

        # Try to extract header from page
        header_text = ""
        for sel in [".job-primary", ".job-banner", ".detail-header", ".job-detail-header"]:
            el = await page.query_selector(sel)
            if el:
                header_text = await el.inner_text()
                break

        header = parse_boss_header_text(header_text) if header_text else {}
        return {
            "jd_text": jd_text,
            "jd_parsed": json.dumps(header, ensure_ascii=False),
            "work_address": "",
            "header_parsed": header,
            "raw_api": False,
        }

    finally:
        await p.stop()


def build_jd_text_from_api(job_json: dict) -> str:
    """Build a JD text string from BOSS直聘 search API JSON.

    Used when we don't have detail page access but have search API results.
    """
    parts = []
    title = job_json.get("jobName", "")
    salary = job_json.get("salaryDesc", "")
    city = job_json.get("cityName", "")
    district = job_json.get("areaDistrict", "")
    exp = job_json.get("experienceName", "")
    degree = job_json.get("degreeName", "")
    skills = job_json.get("skills", [])
    detail = job_json.get("jobDetail", "")

    parts.append(f"岗位：{title}")
    if salary:
        parts.append(f"薪资：{salary}")
    location_parts = [p for p in [city, district] if p]
    if location_parts:
        parts.append(f"地点：{' '.join(location_parts)}")
    if exp:
        parts.append(f"经验：{exp}")
    if degree:
        parts.append(f"学历：{degree}")
    if skills:
        parts.append(f"技能要求：{', '.join(skills)}")
    if detail:
        parts.append(f"\n职位描述：\n{clean_boss_jd_text(detail)}")

    return "\n".join(parts)[:3000]
