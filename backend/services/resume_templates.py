import json
import html as _html

def esc(s):
    return _html.escape(s or "")


def _build_header(data, pfx):
    p = data.get("personal", {})
    parts = [f'<div class="{pfx}-header">']
    name = esc(p.get("name",""))
    if name:
        parts.append(f'<h1>{name}</h1>')
    title = esc(p.get("jobTitle",""))
    if title:
        parts.append(f'<div class="{pfx}-title">{title}</div>')
    contact = " | ".join(filter(None, [esc(p.get(k,"")) for k in ("city","phone","email","personal_website")]))
    if contact:
        parts.append(f'<div class="{pfx}-contact">{contact}</div>')
    parts.append("</div>")
    return "".join(parts)


def _build_work(data, pfx):
    items = []
    for w in data.get("work", []):
        c = esc(w.get("company",""))
        sd = esc(w.get("startDate",""))
        ed = esc(w.get("endDate",""))
        period = f"{sd} - {ed}" if sd or ed else ""
        tw = esc(w.get("title",""))
        items.append(f'<div class="{pfx}-item">')
        items.append(f'<div class="{pfx}-item-header"><span class="{pfx}-company">{c}</span><span class="{pfx}-date">{period}</span></div>')
        if tw:
            items.append(f'<div class="{pfx}-item-sub">{tw}</div>')
        for h in w.get("highlights", []):
            items.append(f"<li>{esc(h)}</li>")
        items.append("</div>")
    return "".join(items)


def _build_projects(data, pfx):
    items = []
    for proj in data.get("projects", []):
        n = esc(proj.get("name",""))
        d = esc(proj.get("date",""))
        r = esc(proj.get("role",""))
        t = esc(proj.get("tech",""))
        items.append(f'<div class="{pfx}-item">')
        items.append(f'<div class="{pfx}-item-header"><span class="{pfx}-pname">{n}</span><span class="{pfx}-date">{d}</span></div>')
        sub = " | ".join(filter(None, [r, t]))
        if sub:
            items.append(f'<div class="{pfx}-item-sub">{sub}</div>')
        for h in proj.get("highlights", []):
            items.append(f"<li>{esc(h)}</li>")
        items.append("</div>")
    return "".join(items)


def _build_skills(data, pfx):
    skills_raw = data.get("skills", [])
    if not skills_raw:
        return ""

    # New structured format: [{"category": "...", "items": [{"label": "...", "detail": "..."}]}]
    if isinstance(skills_raw, list) and skills_raw and isinstance(skills_raw[0], dict) and "category" in skills_raw[0]:
        groups_html = []
        for group in skills_raw:
            cat = esc(group.get("category", ""))
            items = group.get("items", [])
            if not items:
                continue
            item_lines = ""
            for item in items:
                label = esc(item.get("label", ""))
                detail = esc(item.get("detail", ""))
                if label:
                    item_lines += f'<div class="{pfx}-skill-item"><span class="{pfx}-skill-label">{label}</span>'
                    if detail:
                        item_lines += f'<span class="{pfx}-skill-detail">：{detail}</span>'
                    item_lines += '</div>'
            groups_html.append(
                f'<div class="{pfx}-skill-group">'
                f'<div class="{pfx}-skill-group-title">{cat}</div>'
                f'{item_lines}'
                f'</div>'
            )
        if not groups_html:
            return ""
        return f'<div class="{pfx}-skills">{"".join(groups_html)}</div>'

    # Legacy: dict with groups (hard_skills/soft_skills/tool_skills or skill_groups)
    if isinstance(skills_raw, dict):
        group_labels = [
            ("hard_skills", "硬技能"),
            ("soft_skills", "软技能"),
            ("tool_skills", "工具平台"),
        ]
        groups_html = []
        for key, label in group_labels:
            items = skills_raw.get(key, [])
            if not items:
                continue
            tags = "".join(f'<span class="{pfx}-tag">{esc(s)}</span>' for s in items)
            groups_html.append(
                f'<div class="{pfx}-skill-group">'
                f'<div class="{pfx}-skill-group-title">{label}</div>'
                f'{tags}'
                f'</div>'
            )
        if not groups_html:
            return ""
        return f'<div class="{pfx}-skills">{"".join(groups_html)}</div>'

    # Old flat-list format
    tags = "".join(f'<span class="{pfx}-tag">{esc(s)}</span>' for s in skills_raw)
    return f'<div class="{pfx}-skills">{tags}</div>'


def _build_education(data, pfx):
    items = []
    for edu in data.get("education", []):
        s = esc(edu.get("school",""))
        y = esc(edu.get("year",""))
        dg = esc(edu.get("degree",""))
        m = esc(edu.get("major",""))
        items.append(f'<div class="{pfx}-item">')
        items.append(f'<div class="{pfx}-item-header"><span class="{pfx}-school">{s}</span><span class="{pfx}-date">{y}</span></div>')
        sub = " · ".join(filter(None, [dg, m]))
        if sub:
            items.append(f'<div class="{pfx}-item-sub">{sub}</div>')
        items.append("</div>")
    return "".join(items)


# ── 4 Templates ──────────────────────────────────────────────────

TEMPLATES = {
    "modern": {
        "name": "现代简洁",
        "desc": "蓝色简约风，适合技术/产品岗位",
        "css": """
.modern-page{max-width:794px;margin:0 auto;background:#fff;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;box-shadow:0 1px 4px rgba(0,0,0,0.06)}
.modern-page .inner{padding:48px 56px}
.modern-header{margin-bottom:20px;padding-bottom:14px;border-bottom:2px solid #eef2ff}
.modern-header h1{font-size:26px;color:#111827;font-weight:700;margin:0 0 4px}
.modern-title{font-size:15px;color:#4f46e5;font-weight:500;margin-bottom:6px}
.modern-contact{font-size:12px;color:#6b7280}
.modern-section{margin-bottom:16px}
.modern-section h2{font-size:13px;color:#4f46e5;font-weight:600;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px}
.modern-item{margin-bottom:8px}
.modern-item-header{display:flex;justify-content:space-between;font-weight:600;font-size:13px;color:#111827}
.modern-item-sub{font-size:12px;color:#6b7280;margin-top:1px}
.modern-company,.modern-pname,.modern-school{color:#111827}
.modern-date{font-weight:400;color:#9ca3af;font-size:12px}
.modern-item li{font-size:12px;color:#374151;line-height:1.7;padding-left:14px;margin-bottom:2px}
.modern-skills{display:flex;flex-wrap:wrap;gap:6px}
.modern-skill-group{margin-bottom:8px;width:100%}
.modern-skill-group-title{font-size:11px;color:#6b7280;font-weight:600;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px}
.modern-tag{background:#eef2ff;color:#4f46e5;padding:3px 10px;border-radius:4px;font-size:11px}
.modern-skill-item{margin-bottom:3px;font-size:12px;color:#374151;line-height:1.6}
.modern-skill-label{font-weight:600;color:#111827}
.modern-skill-detail{color:#6b7280}
.modern-summary{font-size:12px;color:#374151;line-height:1.7}
"""
    },
    "classic": {
        "name": "经典正式",
        "desc": "衬线字体双线分隔，适合金融/管理岗位",
        "css": """
.classic-page{max-width:800px;margin:0 auto;background:#fff;font-family:'Georgia','Noto Serif SC','SimSun',serif;padding:48px 56px}
.classic-header{text-align:center;margin-bottom:28px;padding-bottom:14px;border-bottom:3px double #1e293b}
.classic-header h1{font-size:28px;color:#1e293b;font-weight:700;margin:0 0 4px;letter-spacing:4px}
.classic-title{font-size:15px;color:#475569;font-weight:600;font-style:italic;margin-bottom:6px}
.classic-contact{font-size:12px;color:#64748b}
.classic-section{margin-bottom:22px}
.classic-section h2{font-size:15px;color:#1e293b;font-weight:700;border-bottom:1px solid #cbd5e1;padding-bottom:6px;margin-bottom:10px}
.classic-item{margin-bottom:12px}
.classic-item-header{display:flex;justify-content:space-between;font-weight:600;font-size:14px;color:#1e293b}
.classic-item-sub{font-size:13px;color:#475569;font-style:italic;margin-top:2px}
.classic-company,.classic-pname,.classic-school{color:#1e293b}
.classic-date{font-weight:400;color:#94a3b8;font-size:13px}
.classic-item li{font-size:13px;color:#334155;line-height:1.8;padding-left:16px;margin-bottom:3px}
.classic-skills{display:flex;flex-wrap:wrap;gap:8px}
.classic-skill-group{margin-bottom:10px;width:100%}
.classic-skill-group-title{font-size:12px;color:#64748b;font-weight:600;margin-bottom:4px;letter-spacing:0.5px}
.classic-tag{background:#f1f5f9;color:#334155;padding:4px 14px;border:1px solid #e2e8f0;font-size:12px}
.classic-skill-item{margin-bottom:3px;font-size:13px;color:#334155;line-height:1.7}
.classic-skill-label{font-weight:600;color:#1e293b}
.classic-skill-detail{color:#475569}
.classic-summary{font-size:13px;color:#334155;line-height:1.8;font-style:italic}
"""
    },
    "creative": {
        "name": "创意活力",
        "desc": "渐变色彩圆角卡片，适合设计/营销岗位",
        "css": """
.creative-page{max-width:800px;margin:0 auto;font-family:-apple-system,'PingFang SC','Microsoft YaHei',sans-serif;background:#fff}
.creative-card{background:#fff;border-radius:12px;padding:40px 48px;box-shadow:0 8px 32px rgba(0,0,0,0.12)}
.creative-header{text-align:center;margin-bottom:24px}
.creative-header h1{font-size:30px;background:linear-gradient(135deg,#667eea,#764ba2);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text;font-weight:800;margin:0 0 4px}
.creative-title{font-size:15px;color:#667eea;font-weight:600;margin-bottom:6px}
.creative-contact{font-size:12px;color:#64748b}
.creative-section{margin-bottom:20px}
.creative-section h2{font-size:13px;color:#667eea;font-weight:700;text-transform:uppercase;letter-spacing:1px;margin-bottom:10px;padding-left:12px;border-left:3px solid #667eea}
.creative-item{margin-bottom:12px;padding:10px 12px;background:#f8fafc;border-radius:8px}
.creative-item-header{display:flex;justify-content:space-between;font-weight:600;font-size:13px;color:#1e293b}
.creative-item-sub{font-size:12px;color:#667eea;margin-top:2px}
.creative-company,.creative-pname,.creative-school{color:#1e293b}
.creative-date{font-weight:400;color:#94a3b8;font-size:12px}
.creative-item li{font-size:12px;color:#475569;line-height:1.7;padding-left:14px;margin-bottom:2px}
.creative-skills{display:flex;flex-wrap:wrap;gap:6px}
.creative-skill-group{margin-bottom:8px;width:100%}
.creative-skill-group-title{font-size:11px;color:#94a3b8;font-weight:600;margin-bottom:4px;text-transform:uppercase;letter-spacing:0.5px}
.creative-tag{background:linear-gradient(135deg,#667eea,#764ba2);color:#fff;padding:4px 12px;border-radius:20px;font-size:11px}
.creative-skill-item{margin-bottom:3px;font-size:12px;color:#475569;line-height:1.7}
.creative-skill-label{font-weight:600;color:#1e293b}
.creative-skill-detail{color:#667eea}
.creative-summary{font-size:12px;color:#475569;line-height:1.7}
"""
    },
    "minimal": {
        "name": "极简留白",
        "desc": "大量留白细线分隔，适合技术/学术岗位",
        "css": """
.minimal-page{max-width:720px;margin:0 auto;background:#fff;font-family:-apple-system,'Helvetica Neue','PingFang SC',sans-serif;padding:56px 64px}
.minimal-header{margin-bottom:32px}
.minimal-header h1{font-size:24px;color:#18181b;font-weight:300;letter-spacing:3px;margin:0 0 2px;text-transform:uppercase}
.minimal-title{font-size:13px;color:#a1a1aa;font-weight:400;letter-spacing:2px;margin-bottom:8px}
.minimal-contact{font-size:11px;color:#a1a1aa;letter-spacing:1px}
.minimal-section{margin-bottom:28px}
.minimal-section h2{font-size:11px;color:#a1a1aa;font-weight:500;letter-spacing:3px;text-transform:uppercase;margin-bottom:12px;border-bottom:1px solid #e4e4e7;padding-bottom:8px}
.minimal-item{margin-bottom:16px}
.minimal-item-header{display:flex;justify-content:space-between;font-weight:400;font-size:13px;color:#18181b}
.minimal-item-sub{font-size:12px;color:#a1a1aa;margin-top:2px}
.minimal-company,.minimal-pname,.minimal-school{color:#18181b;font-weight:500}
.minimal-date{font-weight:300;color:#d4d4d8;font-size:12px}
.minimal-item li{font-size:12px;color:#52525b;line-height:1.8;padding-left:14px;margin-bottom:2px}
.minimal-skills{display:flex;flex-wrap:wrap;gap:4px}
.minimal-skill-group{margin-bottom:6px;width:100%}
.minimal-skill-group-title{font-size:10px;color:#a1a1aa;font-weight:500;margin-bottom:3px;text-transform:uppercase;letter-spacing:1px}
.minimal-tag{color:#52525b;padding:2px 0;font-size:12px;margin-right:12px}
.minimal-skill-item{margin-bottom:2px;font-size:12px;color:#52525b;line-height:1.7}
.minimal-skill-label{font-weight:500;color:#18181b}
.minimal-skill-detail{color:#a1a1aa}
.minimal-summary{font-size:12px;color:#52525b;line-height:1.8}
"""
    }
}


def render_resume(data_json, template_key="modern"):
    try:
        data = json.loads(data_json) if isinstance(data_json, str) else data_json
    except Exception:
        data = {}
    
    if template_key not in TEMPLATES:
        template_key = "modern"
    
    tmpl = TEMPLATES[template_key]
    pfx = template_key
    css = tmpl["css"]
    
    extra = f"""
.{pfx}-item li{{list-style:none;position:relative}}
.{pfx}-item li::before{{content:"\\2022";position:absolute;left:0;color:#4f46e5}}
"""
    
    sections = []
    sections.append(_build_header(data, pfx))
    
    s = data.get("summary", "")
    if s:
        sections.append(f'<div class="{pfx}-section"><h2>个人概述</h2><div class="{pfx}-summary">{esc(s)}</div></div>')
    
    w = _build_work(data, pfx)
    if w:
        sections.append(f'<div class="{pfx}-section"><h2>工作经历</h2>{w}</div>')
    
    p = _build_projects(data, pfx)
    if p:
        sections.append(f'<div class="{pfx}-section"><h2>项目经历</h2>{p}</div>')
    
    sk = _build_skills(data, pfx)
    if sk:
        sections.append(f'<div class="{pfx}-section"><h2>专业技能</h2>{sk}</div>')
    
    e = _build_education(data, pfx)
    if e:
        sections.append(f'<div class="{pfx}-section"><h2>教育背景</h2>{e}</div>')
    
    inner = "".join(sections)
    body_class = pfx + "-page"
    
    if template_key == "modern":
        inner = '<div class="inner">' + inner + '</div>'
    elif template_key == "creative":
        body_class = "creative-page"
        inner = '<div class="creative-card">' + inner + '</div>'
    
    html_out = '<!DOCTYPE html>\n<html><head><meta charset="UTF-8"><style>' + css + extra + '</style></head><body>\n<div class="' + body_class + '">' + inner + '</div>\n</body></html>'
    return html_out


def list_templates():
    return [{"key": k, "name": v["name"], "desc": v["desc"]} for k, v in TEMPLATES.items()]
