import asyncio
import json
import os

from playwright.async_api import async_playwright
from config import settings

CHROMIUM_PATH = settings.CHROMIUM_PATH

RESUME_HTML_TEMPLATE = """
<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:"Noto Sans CJK SC","Noto Sans SC",sans-serif;background:#fff;padding:0}
.page{max-width:800px;margin:0 auto;padding:48px 56px}
.header{text-align:center;margin-bottom:32px}
.header::after{content:"";display:block;width:60px;height:3px;background:#4f46e5;margin:20px auto 0}
.header h1{font-size:28px;color:#111827;font-weight:700;margin-bottom:6px}
.header .title{font-size:16px;color:#4f46e5;font-weight:500}
.header .contact{font-size:13px;color:#6b7280;margin-top:10px}
.section{margin-bottom:24px}
.section h2{font-size:15px;color:#111827;font-weight:600;border-left:3px solid #4f46e5;padding-left:10px;margin-bottom:14px}
.item{margin-bottom:16px}
.item-header{display:flex;justify-content:space-between;font-weight:600;font-size:14px;color:#111827}
.item-sub{font-size:13px;color:#6b7280;margin-top:2px}
.item li{font-size:13px;color:#374151;line-height:1.8;padding-left:14px}
.skills{display:flex;flex-wrap:wrap;gap:8px}
.skills span{background:#eef2ff;color:#4f46e5;padding:4px 12px;border-radius:14px;font-size:12px}
.summary{font-size:13px;color:#374151;line-height:1.8}
</style></head><body><div class="page">
"""


def render_resume_to_html(resume_json_str: str) -> str:
    """Convert resume JSON to formatted HTML string"""
    try:
        data = json.loads(resume_json_str)
    except Exception:
        return "<p>简历数据解析失败</p>"

    def esc(s):
        import html as _h
        return _h.escape(s or "")

    parts = [RESUME_HTML_TEMPLATE]

    p = data.get("personal", {})
    name = p.get("name", "")
    job_title = p.get("jobTitle", "")
    city = p.get("city", "")
    phone = p.get("phone", "")
    email = p.get("email", "")
    summary = data.get("summary", "")
    education = data.get("education", [])
    work = data.get("work", [])
    projects = data.get("projects", [])
    skills = data.get("skills", [])

    # Header
    parts.append('<div class="header"><h1>' + esc(name) + '</h1>')
    if job_title:
        parts.append('<div class="title">' + esc(job_title) + '</div>')
    website = p.get("personal_website", "")
    contacts = ' | '.join(filter(None, [esc(city), esc(phone), esc(email), esc(website)]))
    if contacts:
        parts.append('<div class="contact">' + contacts + '</div>')
    parts.append('</div>')

    # Summary
    if summary:
        parts.append('<div class="section"><h2>个人概述</h2><p class="summary">' + esc(summary) + '</p></div>')

    # Work
    if work:
        parts.append('<div class="section"><h2>工作经历</h2>')
        for w in work:
            company = esc(w.get("company",""))
            period_w = esc(w.get("startDate","") + " - " + w.get("endDate",""))
            title_w = esc(w.get("title",""))
            parts.append('<div class="item"><div class="item-header"><span>' + company + '</span><span>' + period_w + '</span></div>')
            if title_w:
                parts.append('<div class="item-sub">' + title_w + '</div>')
            for h in w.get("highlights", []):
                parts.append('<li>' + esc(h) + '</li>')
            parts.append('</div>')
        parts.append('</div>')

    # Projects
    if projects:
        parts.append('<div class="section"><h2>项目经历</h2>')
        for proj in projects:
            pname = esc(proj.get("name",""))
            pdate = esc(proj.get("date",""))
            parts.append('<div class="item"><div class="item-header"><span>' + pname + '</span><span>' + pdate + '</span></div>')
            sub_items = []
            if proj.get("role"): sub_items.append(esc(proj["role"]))
            if proj.get("tech"): sub_items.append(esc(proj["tech"]))
            if sub_items:
                parts.append('<div class="item-sub">' + " | ".join(sub_items) + '</div>')
            for h in proj.get("highlights", []):
                parts.append('<li>' + esc(h) + '</li>')
            parts.append('</div>')
        parts.append('</div>')

    # Skills
    if skills:
        parts.append('<div class="section"><h2>专业技能</h2><div class="skills">')
        if isinstance(skills, dict):
            group_labels = [
                ("hard_skills", "硬技能"),
                ("soft_skills", "软技能"),
                ("tool_skills", "工具平台"),
            ]
            for key, label in group_labels:
                items = skills.get(key, [])
                if not items:
                    continue
                parts.append(f'<div style="margin-bottom:8px;width:100%">')
                parts.append(f'<div style="font-size:11px;color:#6b7280;font-weight:600;margin-bottom:4px">{label}</div>')
                for s in items:
                    parts.append('<span>' + esc(s) + '</span>')
                parts.append('</div>')
        else:
            for s in skills:
                parts.append('<span>' + esc(s) + '</span>')
        parts.append('</div></div>')

    # Education
    if education:
        parts.append('<div class="section"><h2>教育背景</h2>')
        for edu in education:
            school_e = esc(edu.get("school",""))
            year_e = esc(edu.get("year",""))
            deg = esc(edu.get("degree",""))
            major_e = esc(edu.get("major",""))
            parts.append('<div class="item"><div class="item-header"><span>' + school_e + '</span><span>' + year_e + '</span></div>')
            deg_str = " | ".join(filter(None, [deg, major_e]))
            if deg_str:
                parts.append('<div class="item-sub">' + deg_str + '</div>')
            parts.append('</div>')
        parts.append('</div>')

    parts.append('</div></body></html>')
    return "\n".join(parts)


async def _generate_pdf_async(html_content: str) -> bytes:
    """Generate PDF from HTML using Playwright (headless Chromium)"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            executable_path=CHROMIUM_PATH,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage'],
        )
        try:
            page = await browser.new_page()
            await page.set_viewport_size({'width': 794, 'height': 1123})
            await page.set_content(html_content)
            await page.wait_for_timeout(500)
            pdf_bytes = await page.pdf(
                format='A4',
                print_background=True,
                margin={'top': '0', 'bottom': '0', 'left': '0', 'right': '0'},
            )
            return pdf_bytes
        finally:
            await browser.close()


async def generate_pdf_async(html_content: str) -> bytes:
    """Async PDF generation"""
    return await _generate_pdf_async(html_content)


def generate_pdf_sync(html_content, css_content=""):
    full_html = html_content
    if css_content:
        full_html = '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"><style>' + css_content + '</style></head>\n<body>' + html_content + '</body>\n</html>'
    return asyncio.run(_generate_pdf_async(full_html))
