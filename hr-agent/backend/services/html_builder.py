import json
from jinja2 import Environment, BaseLoader

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }}</title>
    <style>{{ css }}</style>
</head>
<body>
    {{ content }}
</body>
</html>
"""

def _normalize_skills(knowledge):
    """Normalize skills data to list of {title, items:[{name, desc}]} regardless of storage format."""
    raw = knowledge.get("skills", {})
    # New structured format
    sections = raw.get("skill_sections", [])
    if sections and isinstance(sections, list):
        return sections
    # skill_groups dict format
    groups = raw.get("skill_groups", {})
    if isinstance(groups, dict) and groups:
        return [{"title": k, "items": [{"name": t, "desc": ""} for t in v if isinstance(t, str)]} for k, v in groups.items()]
    # Legacy hard_skills/soft_skills/tool_skills format
    legacy_map = {"hard_skills": "硬技能", "soft_skills": "软技能", "tool_skills": "工具平台"}
    result = []
    for key, label in legacy_map.items():
        items = raw.get(key, [])
        if items:
            result.append({"title": label, "items": [{"name": t, "desc": ""} for t in items if isinstance(t, str)]})
    return result

class HTMLBuilder:
    def __init__(self):
        self.env = Environment(loader=BaseLoader())

    def render(self, title, content, css):
        template = self.env.from_string(HTML_TEMPLATE)
        return template.render(
            title=title,
            content=content,
            css=css
        )

    def generate_html(self, config, knowledge_data):
        theme_name = config.get("style", "editorial")
        themes = {
            "editorial": self._render_editorial_theme,
            "developer": self._render_developer_theme,
            "creative": self._render_creative_theme,
            "personal": self._render_personal_theme
        }
        theme_func = themes.get(theme_name, self._render_editorial_theme)
        content, css = theme_func(knowledge_data, config)

        return self.render(
            title=f"{knowledge_data.get('personal_info', {}).get('name', '个人主页')} - 个人主页",
            content=content,
            css=css
        )

    def _render_editorial_theme(self, knowledge, config):
        info = knowledge.get("personal_info", {})
        work = knowledge.get("work_experience", {}).get("work_list", [])
        projects = knowledge.get("projects", {}).get("project_list", [])
        skill_sections = _normalize_skills(knowledge)
        educations = knowledge.get("education", {}).get("education_list", [])

        name = info.get("name", "Zhang Wei")
        role = info.get("target_position", "Senior Product Manager")
        city = info.get("city", "Beijing")
        self_intro = info.get("self_intro", "Product manager with 5+ years experience in AI and B2B products, passionate about building solutions that users love.")
        email = info.get("email", "")
        phone = info.get("phone", "")
        github = info.get("github", "")
        wechat_name = info.get("wechat_name", "")
        wechat_qr = info.get("wechat_qr", "")

        nav_labels = ["Home", "About", "Work", "Experience", "Contact"]
        nav_html = ""
        for i, label in enumerate(nav_labels):
            nav_html += f'<a class="nav-btn" href="#section-{i}">{label}</a>'

        projects_html = ""
        for p in projects[:4]:
            period = p.get("period", "2024")
            p_role = p.get("role", "PM")
            p_name = p.get("name", "")
            p_desc = p.get("description", "")
            js_name = p_name.replace("'", "\\'").replace('"', '&quot;').replace('\n', ' ').replace('\r', ' ')
            js_desc = p_desc.replace("'", "\\'").replace('"', '&quot;').replace('\n', ' ').replace('\r', ' ')
            projects_html += f"""
            <div class="ed-work-card">
                <div class="ed-work-meta">{period} — {p_role}</div>
                <div class="ed-work-title">{p_name}</div>
                <div class="ed-work-desc">{p_desc}</div>
                <a class="ed-work-link" href="#" onclick="if(window.opener){{window.opener.askAboutPortfolioItem('{js_name}','{js_desc}');window.close();}}return false;">→ Read more</a>
            </div>"""

        experience_html = ""
        for w in work:
            company = w.get("company", "")
            position = w.get("position", "")
            period = w.get("period", "")
            desc = w.get("description", "")
            experience_html += f"""
            <div class="ed-timeline-item">
                <div class="ed-timeline-header">
                    <div>
                        <span class="ed-timeline-company">{company}</span>
                        <span class="ed-timeline-role">{position}</span>
                    </div>
                    <span class="ed-timeline-date">{period}</span>
                </div>
                <div class="ed-timeline-desc">{desc}</div>
            </div>"""

        education_html = ""
        if educations:
            education_html += '<div class="ed-edu-label">Education</div>'
            for edu in educations:
                school = edu.get("school", "")
                degree = edu.get("degree", "")
                major = edu.get("major", "")
                period = edu.get("period", "")
                education_html += f"""
                <div class="ed-timeline-item" style="padding: 16px 0;">
                    <div class="ed-timeline-header">
                        <div>
                            <span class="ed-timeline-company" style="font-size: 16px;">{school}</span>
                            <span class="ed-timeline-role">{degree} · {major}</span>
                        </div>
                        <span class="ed-timeline-date">{period}</span>
                    </div>
                </div>"""

        skills_html = ""
        if skill_sections:
            for section in skill_sections:
                title = section.get("title", "")
                items = section.get("items", [])
                if not items:
                    continue
                tags_html = ""
                for item in items:
                    sk_name = item.get("name", "")
                    sk_desc = item.get("desc", "")
                    label = sk_name + ("：" + sk_desc if sk_desc else "")
                    tags_html += f'<span class="ed-skill-tag">{label}</span>'
                skills_html += f"""
                <div class="ed-skill-group">
                    <div class="ed-skill-group-title">{title}</div>
                    <div class="ed-skill-tags">{tags_html}</div>
                </div>"""
        else:
            skills_html = '<div class="ed-life-text">No skills listed</div>'

        contact_links_html = ""
        if email:
            contact_links_html += f"""
            <a class="ed-contact-link" href="mailto:{email}">
                <span class="ed-contact-icon">✉</span>
                <span>{email}</span>
            </a>"""
        if phone:
            contact_links_html += f"""
            <a class="ed-contact-link" href="tel:{phone}">
                <span class="ed-contact-icon">☎</span>
                <span>{phone}</span>
            </a>"""
        if github:
            contact_links_html += f"""
            <a class="ed-contact-link" href="{github}" target="_blank" rel="noopener noreferrer">
                <span class="ed-contact-icon">⟠</span>
                <span>GitHub</span>
            </a>"""
        personal_website = info.get("personal_website", "")
        if personal_website:
            contact_links_html += f"""
            <a class="ed-contact-link" href="{personal_website}" target="_blank" rel="noopener noreferrer">
                <span class="ed-contact-icon">🌐</span>
                <span>个人网站</span>
            </a>"""
        wechat_display = wechat_name if wechat_name else "微信"
        wechat_qr_html = ""
        if wechat_qr:
            wechat_qr_html = f'<span class="wechat-qr-popup"><img src="{wechat_qr}" alt="WeChat QR Code" /></span>'
        contact_links_html += f"""
            <span class="wechat-wrapper">
                <span class="ed-contact-link">
                    <span class="ed-contact-icon">✦</span>
                    <span>{wechat_display}</span>
                </span>
                {wechat_qr_html}
            </span>"""

        content = f"""
<div class="editorial-theme">
  <nav class="editorial-nav">
    {nav_html}
  </nav>
  <div class="editorial-sections">
    <section class="section ed-hero" id="section-0">
      <div class="section-inner">
        <h1 class="ed-hero-name">{name}</h1>
        <p class="ed-hero-role">{role}</p>
        <div class="ed-hero-badge">
          <span class="ed-hero-dot"></span>
          <span>{city} · Open to opportunities</span>
        </div>
      </div>
    </section>
    <section class="section" id="section-1">
      <div class="section-inner">
        <div class="editorial-section-label">About</div>
        <div class="ed-about-layout">
          <div class="ed-about-main">
            <p>{self_intro}</p>
            <p>I believe great products come from deep user understanding and iterative delivery. My approach combines data-driven decision making with empathic design thinking.</p>
            <blockquote style="font-style: italic; font-size: 22px; color: #666; text-align: center; margin: 56px 0; line-height: 1.6;">
                "Good products are built from understanding, not assumptions."
            </blockquote>
            <p>Outside of work, I enjoy exploring new technologies, reading about behavioral economics, and contributing to product communities.</p>
          </div>
          <div class="ed-about-sidebar">
            <h4>Skills</h4>
            {skills_html}
          </div>
        </div>
      </div>
    </section>
    <section class="section" id="section-2">
      <div class="section-inner">
        <div class="editorial-section-label">Selected work</div>
        <div class="ed-work-grid">
          {projects_html}
        </div>
      </div>
    </section>
    <section class="section" id="section-3">
      <div class="section-inner">
        <div class="editorial-section-label">Experience</div>
        <div class="ed-timeline">
          {experience_html}
          {education_html}
        </div>
      </div>
    </section>
    <section class="section ed-contact" id="section-4">
      <div>
        <h2 class="ed-contact-heading">Let's talk.</h2>
        <p class="ed-contact-text">
            I'm currently exploring new opportunities. If you have a role, a project, or just a conversation — I'd love to connect.
        </p>
        <div class="ed-contact-links">
            {contact_links_html}
        </div>
      </div>
    </section>
  </div>
</div>"""

        css = """
html { scroll-behavior: smooth; }
body { margin: 0; padding: 0; }
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;500&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400&display=swap');
.editorial-theme {
  font-family: 'Playfair Display', 'Times New Roman', serif;
  background-color: #FAFAF8;
  color: #1A1A1A;
  height: 100%;
}
.editorial-nav {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  box-sizing: border-box;
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
  gap: 32px;
  padding: 24px 40px;
  font-family: 'Inter', sans-serif;
  font-size: 13px;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  background: #FAFAF8;
}

.editorial-sections .section {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 80px 40px;
}
.editorial-sections .section-inner {
  max-width: 900px;
  width: 100%;
}
.editorial-nav .nav-btn {
  background: none;
  border: none;
  color: #999;
  cursor: pointer;
  font-family: inherit;
  font-size: inherit;
  letter-spacing: inherit;
  text-transform: inherit;
  padding: 0;
  transition: color 0.2s;
}
.editorial-nav .nav-btn:hover,
.editorial-nav .nav-btn.active {
  color: #C4502A;
}
.editorial-section-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #999;
  margin-bottom: 40px;
}
.ed-hero { text-align: center; flex-direction: column; }
.ed-hero-name { font-size: 64px; font-weight: 400; margin-bottom: 16px; }
.ed-hero-role { font-family: 'Inter', sans-serif; font-size: 22px; color: #333; margin-bottom: 24px; }
.ed-hero-badge { display: inline-flex; align-items: center; gap: 8px; font-family: 'Inter', sans-serif; font-size: 13px; color: #666; }
.ed-hero-dot { width: 8px; height: 8px; background: #C4502A; border-radius: 50%; }
.ed-work-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; }
.ed-work-card { border: 1px solid #E8E6E1; padding: 24px; transition: transform 0.2s; }
.ed-work-card:hover { transform: translateY(-2px); }
.ed-work-meta { font-family: 'Inter', sans-serif; font-size: 12px; color: #999; margin-bottom: 12px; }
.ed-work-title { font-family: 'Inter', sans-serif; font-size: 20px; font-weight: 500; margin-bottom: 12px; }
.ed-work-desc { font-family: 'Inter', sans-serif; font-size: 14px; color: #666; line-height: 1.6; margin-bottom: 12px; }
.ed-work-desc ul { padding-left: 16px; margin: 6px 0; }
.ed-work-desc li { font-size: 13px; color: #555; line-height: 1.5; margin-bottom: 3px; }
.ed-work-link { font-family: 'Inter', sans-serif; font-size: 14px; color: #C4502A; text-decoration: none; }
.ed-about-layout { display: flex; gap: 64px; }
.ed-about-main { flex: 3; }
.ed-about-main p { font-family: 'Inter', sans-serif; font-size: 16px; line-height: 1.8; color: #333; margin-bottom: 20px; }
.ed-about-main p:first-child { font-size: 18px; }
.ed-about-sidebar { flex: 2; }
.ed-about-sidebar h4 { font-family: 'Inter', sans-serif; font-size: 14px; font-weight: 600; margin-bottom: 16px; color: #1A1A1A; }
.ed-life-item { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; }
.ed-life-placeholder { width: 48px; height: 48px; background: #E8E6E1; border-radius: 4px; flex-shrink: 0; }
.ed-life-text { font-family: 'Inter', sans-serif; font-size: 13px; color: #666; line-height: 1.4; }
.ed-timeline { border-top: 1px solid #E8E6E1; }
.ed-timeline-item { padding: 32px 0; border-bottom: 1px solid #E8E6E1; }
.ed-timeline-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 12px; }
.ed-timeline-company { font-family: 'Inter', sans-serif; font-size: 18px; font-weight: 600; }
.ed-timeline-role { font-family: 'Inter', sans-serif; font-size: 15px; color: #666; margin-left: 8px; }
.ed-timeline-date { font-family: 'Inter', sans-serif; font-size: 14px; color: #999; white-space: nowrap; }
.ed-timeline-desc { font-family: 'Inter', sans-serif; font-size: 14px; color: #333; line-height: 1.7; }
.ed-edu-label { font-family: 'Inter', sans-serif; font-size: 12px; color: #C4502A; text-transform: uppercase; letter-spacing: 0.05em; margin-top: 24px; margin-bottom: 12px; }
.ed-edu-item { font-family: 'Inter', sans-serif; font-size: 14px; color: #666; display: flex; gap: 16px; margin-bottom: 8px; }
.ed-contact { text-align: center; flex-direction: column; }
.ed-contact-heading { font-size: 48px; font-weight: 400; margin-bottom: 16px; }
.ed-contact-text { font-family: 'Inter', sans-serif; font-size: 16px; color: #666; max-width: 480px; line-height: 1.6; margin-bottom: 32px; }
.ed-contact-email { font-family: 'Inter', sans-serif; font-size: 24px; color: #C4502A; text-decoration: none; display: block; margin-bottom: 32px; }
.ed-contact-socials { display: flex; gap: 24px; justify-content: center; font-family: 'Inter', sans-serif; font-size: 14px; }
.ed-contact-socials a { color: #999; text-decoration: none; }
.ed-contact-socials a:hover { color: #C4502A; }
.ed-skill-group { margin-bottom: 20px; }
.ed-skill-group-title { font-family: 'Inter', sans-serif; font-size: 12px; font-weight: 600; color: #1A1A1A; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px; }
.ed-skill-tags { display: inline-flex; flex-wrap: wrap; gap: 6px; }
.ed-skill-tag { font-family: 'Inter', sans-serif; font-size: 12px; color: #555; background: #F0EEE8; border-radius: 4px; padding: 4px 10px; display: inline-block; }
.ed-contact-links { display: flex; flex-direction: column; align-items: center; gap: 12px; margin-bottom: 32px; }
.ed-contact-link { font-family: 'Inter', sans-serif; font-size: 15px; color: #666; text-decoration: none; display: inline-flex; align-items: center; gap: 8px; transition: color 0.2s; }
.ed-contact-link:hover { color: #C4502A; }
.ed-contact-icon { font-size: 16px; color: #999; }
.wechat-wrapper { position: relative; display: inline-block; cursor: pointer; }
.wechat-qr-popup { display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 8px; z-index: 100; background: #fff; padding: 8px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.15); }
.wechat-wrapper:hover .wechat-qr-popup { display: block; }
.wechat-qr-popup img { width: 150px; height: 150px; border-radius: 8px; display: block; }
.wechat-qr-popup::after { content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); border: 6px solid transparent; border-top-color: white; }
"""
        return content, css

    def _render_developer_theme(self, knowledge, config):
        info = knowledge.get("personal_info", {})
        work = knowledge.get("work_experience", {}).get("work_list", [])
        projects = knowledge.get("projects", {}).get("project_list", [])
        skill_sections = _normalize_skills(knowledge)
        educations = knowledge.get("education", {}).get("education_list", [])

        name = info.get("name", "Li Chen")
        role = info.get("target_position", "Full-Stack Engineer")
        city = info.get("city", "Shanghai")
        self_intro = info.get("self_intro", "Engineer focused on building reliable, scalable systems. Passionate about developer tools, API design, and cloud infrastructure.")
        email = info.get("email", "")
        phone = info.get("phone", "")
        github = info.get("github", "")
        wechat_name = info.get("wechat_name", "")
        wechat_qr = info.get("wechat_qr", "")

        nav_labels = ["Home", "Projects", "Exp", "Stack", "About"]
        nav_html = ""
        for i, label in enumerate(nav_labels):
            nav_html += f'<a class="nav-btn" href="#section-{i}">{label}</a>'

        projects_html = ""
        for p in projects[:4]:
            p_name = p.get("name", "")
            p_desc = p.get("description", "")
            tech_stack = p.get("tech_stack", "")
            if isinstance(tech_stack, list):
                tech_items = [t.strip() for t in tech_stack if t.strip()]
            else:
                tech_items = [t.strip() for t in str(tech_stack).split(",") if t.strip()]
            chips_html = ""
            for t in tech_items:
                chips_html += f'<span class="dev-project-chip">{t}</span>'
            projects_html += f"""
            <div class="dev-project-card">
                <div class="dev-project-name">{p_name}</div>
                <div class="dev-project-desc">{p_desc}</div>
                <div class="dev-project-chips">{chips_html}</div>
                <div class="dev-project-links">
                    <a href="#">GitHub</a>
                    <a href="#">Live</a>
                </div>
            </div>"""

        experience_html = ""
        for w in work:
            company = w.get("company", "")
            position = w.get("position", "")
            period = w.get("period", "")
            desc = w.get("description", "")
            experience_html += f"""
            <div class="dev-timeline-item">
                <div class="dev-timeline-header">
                    <div>
                        <span class="dev-timeline-company">{company}</span>
                        <span class="dev-timeline-role">{position}</span>
                    </div>
                    <span class="dev-timeline-date">{period}</span>
                </div>
                <div class="dev-timeline-desc">{desc}</div>
            </div>"""

        education_html = ""
        if educations:
            education_html += '<div class="dev-edu-block"><div class="dev-edu-header">Education</div>'
            for edu in educations:
                school = edu.get("school", "")
                degree = edu.get("degree", "")
                major = edu.get("major", "")
                period = edu.get("period", "")
                education_html += f"""
                <div class="dev-timeline-item" style="padding: 16px 0;">
                    <div class="dev-timeline-header">
                        <div>
                            <span class="dev-timeline-company" style="font-size: 14px;">{school}</span>
                            <span class="dev-timeline-role">{degree} · {major}</span>
                        </div>
                        <span class="dev-timeline-date">{period}</span>
                    </div>
                </div>"""
            education_html += '</div>'

        stack_html = ""
        if skill_sections:
            for section in skill_sections[:4]:
                title = section.get("title", "")
                items = section.get("items", [])
                chips_html = ""
                for item in items[:8]:
                    sk_name = item.get("name", "")
                    sk_desc = item.get("desc", "")
                    label = sk_name + ("：" + sk_desc[:20] if sk_desc else "")
                    chips_html += f'<span class="dev-stack-chip">{label}</span>'
                stack_html += f"""
                <div class="dev-stack-cat">
                    <h4>{title}</h4>
                    <div class="dev-stack-chips">{chips_html}</div>
                </div>"""
        else:
            for cat in ['Languages', 'Frameworks', 'Infrastructure', 'Tools']:
                stack_html += f"""
                <div class="dev-stack-cat">
                    <h4>{cat}</h4>
                    <div class="dev-stack-chips">
                        <span class="dev-stack-chip">TypeScript</span>
                        <span class="dev-stack-chip">Python</span>
                        <span class="dev-stack-chip">Go</span>
                        <span class="dev-stack-chip">Rust</span>
                    </div>
                </div>"""

        contact_grid_html = ""
        if email:
            contact_grid_html += f"""
            <div class="dev-contact-item">
                <span>Email</span>
                <a href="mailto:{email}">{email}</a>
            </div>"""
        if phone:
            contact_grid_html += f"""
            <div class="dev-contact-item">
                <span>Phone</span>
                <a href="tel:{phone}">{phone}</a>
            </div>"""
        if github:
            github_display = github.replace("https://", "").replace("http://", "")
            contact_grid_html += f"""
            <div class="dev-contact-item">
                <span>GitHub</span>
                <a href="{github}" target="_blank" rel="noopener noreferrer">{github_display}</a>
            </div>"""
        wechat_display = wechat_name if wechat_name else "微信"
        if wechat_qr:
            contact_grid_html += f"""
            <div class="dev-contact-item">
                <span>WeChat</span>
                <div class="dev-wechat-wrap">
                    <span style="color: #4D9DE0;">{wechat_display}</span>
                    <div class="dev-wechat-popup">
                        <img src="{wechat_qr}" alt="WeChat QR" />
                    </div>
                </div>
            </div>"""
        else:
            contact_grid_html += f"""
            <div class="dev-contact-item">
                <span>WeChat</span>
                <span style="color: #CCC;">{wechat_display}</span>
            </div>"""

        content = f"""
<div class="developer-theme">
  <nav class="developer-nav">
    <span class="nav-left">{name}</span>
    <div class="nav-links">
      {nav_html}
    </div>
  </nav>
  <div class="developer-sections">
    <section class="section dev-hero" id="section-0">
      <div>
        <p class="dev-hero-greeting">&gt; Hello, I'm {name}<span class="dev-hero-cursor"></span></p>
        <h1 class="dev-hero-name">{role}</h1>
        <p class="dev-hero-role">{" / ".join([i.get("name","") for s in skill_sections[:1] for i in s.get("items",[])[:3]]) if skill_sections else "React / Go / Kubernetes"}</p>
        <div class="dev-hero-badge">
          <span class="dev-hero-dot"></span>
          <span>{city} · Open to new roles</span>
        </div>
      </div>
    </section>
    <section class="section" id="section-1">
      <div class="section-inner">
        <div class="dev-section-label">Featured Projects</div>
        <div class="dev-projects">
          {projects_html}
        </div>
      </div>
    </section>
    <section class="section" id="section-2">
      <div class="section-inner">
        <div class="dev-section-label">Experience</div>
        <div class="dev-timeline">
          {experience_html}
          {education_html}
        </div>
      </div>
    </section>
    <section class="section" id="section-3">
      <div class="section-inner">
        <div class="dev-section-label">Tech Stack</div>
        <div class="dev-stack-grid">
          {stack_html}
        </div>
      </div>
    </section>
    <section class="section" id="section-4">
      <div class="section-inner">
        <div class="dev-section-label">About</div>
        <div class="dev-about-wrap">
          <div class="dev-about-main">
            <p>{self_intro}</p>
            <p>I care about clean architecture, good test coverage, and products that respect their users' time. Outside work I contribute to open source and experiment with side projects.</p>
            <div>
              <span class="dev-interest-chip">Open Source</span>
              <span class="dev-interest-chip">CLI Tools</span>
              <span class="dev-interest-chip">Cloud Native</span>
            </div>
            <div class="dev-contact-grid">
              {contact_grid_html}
            </div>
          </div>
        </div>
      </div>
    </section>
  </div>
</div>"""

        css = """
html { scroll-behavior: smooth; }
body { margin: 0; padding: 0; }
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400&display=swap');
.developer-theme {
  font-family: 'Inter', sans-serif;
  background-color: #0A0A0A;
  color: #FFFFFF;
  height: 100%;
}
.developer-nav {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  box-sizing: border-box;
  z-index: 1000;
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 40px;
  background: #0A0A0A;
  font-family: 'JetBrains Mono', monospace;
}

.developer-sections .section {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 80px 60px;
}
.developer-sections .section-inner {
  max-width: 960px;
  width: 100%;
}
.developer-nav .nav-left {
  font-size: 16px;
}
.developer-nav .nav-links {
  display: flex;
  gap: 24px;
}
.developer-nav .nav-btn {
  background: none;
  border: none;
  color: #555;
  cursor: pointer;
  font-family: inherit;
  font-size: 12px;
  padding: 0;
  transition: color 0.2s;
}
.developer-nav .nav-btn:hover,
.developer-nav .nav-btn.active {
  color: #FFF;
}
.dev-hero { flex-direction: column; text-align: center; }
.dev-hero-greeting {
  font-family: 'JetBrains Mono', monospace;
  font-size: 18px; color: #888; margin-bottom: 20px;
}
.dev-hero-cursor {
  display: inline-block; width: 10px; height: 20px;
  background: #3DD68C; margin-left: 4px;
  animation: dev-blink 1s infinite;
}
@keyframes dev-blink { 0%,50% { opacity:1; } 51%,100% { opacity:0; } }
.dev-hero-name { font-size: 52px; font-weight: 700; letter-spacing: -0.02em; margin-bottom: 12px; }
.dev-hero-role { font-size: 22px; color: #AAA; margin-bottom: 24px; }
.dev-hero-badge {
  display: inline-flex; align-items: center; gap: 8px;
  font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #888;
}
.dev-hero-dot { width: 8px; height: 8px; background: #3DD68C; border-radius: 50%; animation: dev-blink 2s infinite; }
.dev-section-label {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px; color: #555; text-transform: uppercase;
  letter-spacing: 0.1em; margin-bottom: 40px;
}
.dev-projects { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
.dev-project-card {
  background: #111; border: 1px solid #222; padding: 24px;
  transition: border-color 0.2s;
}
.dev-project-card:hover { border-color: #333; }
.dev-project-name { font-family: 'JetBrains Mono', monospace; font-size: 16px; margin-bottom: 8px; }
.dev-project-desc { font-size: 13px; color: #888; line-height: 1.6; margin-bottom: 16px; }
.dev-project-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
.dev-project-chip {
  font-family: 'JetBrains Mono', monospace; font-size: 11px;
  color: #888; background: #1A1A1A; padding: 3px 8px; border: 1px solid #222;
}
.dev-project-links { display: flex; gap: 12px; font-family: 'JetBrains Mono', monospace; font-size: 12px; }
.dev-project-links a { color: #4D9DE0; text-decoration: none; }
.dev-stack-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 24px; }
.dev-stack-cat h4 { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #555; margin-bottom: 16px; text-transform: uppercase; }
.dev-stack-chips { display: flex; flex-direction: column; gap: 6px; }
.dev-stack-chip {
  font-family: 'JetBrains Mono', monospace; font-size: 12px;
  color: #AAA; background: #111; border: 1px solid #222;
  padding: 4px 10px; display: inline-block; width: fit-content;
}
.dev-timeline { border-top: 1px solid #1A1A1A; }
.dev-timeline-item { padding: 28px 0; border-bottom: 1px solid #1A1A1A; }
.dev-timeline-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
.dev-timeline-company { font-size: 15px; font-weight: 600; }
.dev-timeline-role { color: #AAA; font-size: 13px; margin-left: 6px; }
.dev-timeline-date { font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #555; }
.dev-timeline-desc { font-size: 13px; color: #888; line-height: 1.6; }
.dev-edu-block { margin-top: 32px; }
.dev-edu-header { font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #3DD68C; margin-bottom: 12px; }
.dev-about-wrap { display: flex; gap: 64px; align-items: flex-start; }
.dev-about-main { flex: 2; }
.dev-about-main p { font-size: 15px; line-height: 1.8; color: #CCC; margin-bottom: 16px; }
.dev-interest-chip {
  display: inline-block; font-family: 'JetBrains Mono', monospace;
  font-size: 12px; color: #888; background: #111; border: 1px solid #222;
  padding: 6px 14px; margin: 4px 6px 4px 0;
}
.dev-contact-links { margin-top: 32px; }
.dev-contact-links a {
  display: block; font-family: 'JetBrains Mono', monospace;
  font-size: 14px; color: #4D9DE0; text-decoration: none; margin-bottom: 12px;
}
.dev-contact-grid { display: flex; flex-wrap: wrap; gap: 24px; margin-top: 32px; }
.dev-contact-item {
  display: flex; align-items: center; gap: 8px;
  font-family: 'JetBrains Mono', monospace; font-size: 13px;
}
.dev-contact-item a { color: #4D9DE0; text-decoration: none; }
.dev-contact-item span { color: #888; }
.dev-wechat-wrap { position: relative; display: inline-block; cursor: pointer; }
.dev-wechat-popup { display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 8px; z-index: 100; background: #1A1A1A; padding: 8px; border-radius: 8px; border: 1px solid #333; }
.dev-wechat-wrap:hover .dev-wechat-popup { display: block; }
.dev-wechat-popup img { width: 150px; height: 150px; border-radius: 4px; }
.dev-wechat-popup::after { content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); border: 6px solid transparent; border-top-color: #1A1A1A; }
"""
        return content, css

    def _render_creative_theme(self, knowledge, config):
        info = knowledge.get("personal_info", {})
        work = knowledge.get("work_experience", {}).get("work_list", [])
        projects = knowledge.get("projects", {}).get("project_list", [])
        skill_sections = _normalize_skills(knowledge)
        educations = knowledge.get("education", {}).get("education_list", [])

        name = info.get("name", "Your Name")
        role = info.get("target_position", "Creative Professional")
        self_intro = info.get("self_intro", "A passionate creative professional dedicated to crafting meaningful digital experiences that bridge the gap between aesthetics and functionality.")
        email = info.get("email", "")
        phone = info.get("phone", "")
        github = info.get("github", "")
        wechat_name = info.get("wechat_name", "")
        wechat_qr = info.get("wechat_qr", "")

        nav_labels = ["Home", "Work", "Experience", "About", "Contact"]
        nav_html = ""
        for i, label in enumerate(nav_labels):
            nav_html += f'<a class="nav-btn" href="#section-{i}">{label}</a>'

        work_html = ""
        if projects:
            for p in projects:
                p_name = p.get("name", "")
                p_role = p.get("role", "")
                p_period = p.get("period", "")
                p_desc = p.get("description", "")
                tech_stack = p.get("tech_stack", "")
                if isinstance(tech_stack, list):
                    tech_items = [t.strip() for t in tech_stack if t.strip()]
                else:
                    tech_items = [t.strip() for t in str(tech_stack).split(",") if t.strip()]
                tech_html = ""
                if tech_items:
                    for t in tech_items:
                        tech_html += f'<span class="cr-work-chip">{t}</span>'
                    tech_html = f'<div class="cr-work-card-tech">{tech_html}</div>'
                work_html += f"""
                <div class="cr-work-card">
                    <h3 class="cr-work-card-name">{p_name}</h3>
                    <p class="cr-work-card-role">{p_role}{" · " + p_period if p_period else ""}</p>
                    <p class="cr-work-card-desc">{p_desc}</p>
                    {tech_html}
                </div>"""
        else:
            work_html = '<div class="cr-empty-state">No projects listed yet</div>'

        exp_html = ""
        if work:
            for w in work:
                company = w.get("company", "")
                position = w.get("position", "")
                period = w.get("period", "")
                desc = w.get("description", "")
                desc_html = f'<div class="cr-exp-desc">{desc}</div>' if desc else ""
                exp_html += f"""
                <div class="cr-exp-item">
                    <div class="cr-exp-header">
                        <div>
                            <span class="cr-exp-company">{company}</span>
                            <span class="cr-exp-role">{position}</span>
                        </div>
                        <span class="cr-exp-date">{period}</span>
                    </div>
                    {desc_html}
                </div>"""

        edu_html = ""
        if educations:
            edu_html += '<div class="cr-edu-label">Education</div>'
            for edu in educations:
                school = edu.get("school", "")
                degree = edu.get("degree", "")
                major = edu.get("major", "")
                period = edu.get("period", "")
                edu_html += f"""
                <div class="cr-edu-item">
                    <div class="cr-edu-header">
                        <div>
                            <span class="cr-edu-school">{school}</span>
                            <span class="cr-edu-degree">{degree}{" · " + major if major else ""}</span>
                        </div>
                        <span class="cr-edu-date">{period}</span>
                    </div>
                </div>"""

        if not work and not educations:
            exp_html = '<div class="cr-empty-state">No experience listed yet</div>'

        about_skills_html = ""
        if skill_sections:
            for section in skill_sections[:3]:
                title = section.get("title", "")
                items = section.get("items", [])
                tags_html = ""
                for item in items[:5]:
                    sk_name = item.get("name", "")
                    sk_desc = item.get("desc", "")
                    label = sk_name + ("：" + sk_desc[:30] if sk_desc else "")
                    tags_html += f'<span class="cr-about-skill-tag">{label}</span>'
                about_skills_html += f"""
                <div class="cr-about-skill-group">
                    <div class="cr-about-skill-title">{title}</div>
                    <div class="cr-about-skill-tags">{tags_html}</div>
                </div>"""
            about_skills_html = f"""
            <div class="cr-about-skills-sidebar">
                <h4>Core Skills</h4>
                {about_skills_html}
            </div>"""

        contact_links_html = ""
        if phone:
            contact_links_html += f'<a class="cr-contact-link" href="tel:{phone}">{phone}</a>'
        if github:
            contact_links_html += f'<a class="cr-contact-link" href="{github}" target="_blank" rel="noopener noreferrer">GitHub</a>'
        wechat_display = wechat_name if wechat_name else "微信"
        wechat_qr_html = ""
        if wechat_qr:
            wechat_qr_html = f'<div class="cr-wechat-qr-popup"><img src="{wechat_qr}" alt="WeChat QR" class="cr-wechat-qr-img" /></div>'
        contact_links_html += f"""
            <span class="cr-contact-wechat">
                <span class="cr-contact-link">{wechat_display}</span>
                {wechat_qr_html}
            </span>"""

        content = f"""
<div class="creative-theme">
  <nav class="creative-nav">
    {nav_html}
  </nav>
  <div class="creative-sections">
    <section class="section section-dark" id="section-0">
      <div class="cr-hero-wrap">
        <h1 class="cr-hero-name">{name}</h1>
      </div>
    </section>
    <section class="section section-light" id="section-1">
      <div class="section-inner">
        <div class="creative-section-label">Selected work</div>
        <div class="cr-work-grid">
          {work_html}
        </div>
      </div>
    </section>
    <section class="section section-dark" id="section-2">
      <div class="section-inner">
        <div class="creative-section-label">Experience</div>
        {exp_html}
        {edu_html}
      </div>
    </section>
    <section class="section section-light" id="section-3">
      <div class="section-inner">
        <div class="cr-about-wrap">
          <div class="cr-about-portrait"></div>
          <div class="cr-about-right">
            <h2>{name}</h2>
            <p class="cr-about-role">{role}</p>
            <p>{self_intro}</p>
            <p>I believe great design is invisible — it removes friction, guides attention, and makes complex things feel simple. Every pixel should have purpose.</p>
            {about_skills_html}
          </div>
        </div>
      </div>
    </section>
    <section class="section section-dark" id="section-4">
      <div class="cr-contact-wrap">
        <h2 class="cr-contact-heading">Get in touch</h2>
        <a class="cr-contact-email" href="mailto:{email}">{email if email else "your@email.com"}</a>
        <div class="cr-contact-links">
          {contact_links_html}
        </div>
      </div>
    </section>
  </div>
</div>"""

        css = """
html { scroll-behavior: smooth; }
body { margin: 0; padding: 0; }
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500&family=DM+Mono:wght@400&display=swap');
.creative-theme {
  font-family: 'DM Sans', sans-serif;
  background-color: #0F0F0F;
  color: #FFFFFF;
  height: 100%;
}
.creative-nav {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  box-sizing: border-box;
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
  gap: 28px;
  padding: 32px 40px;
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  background: #0F0F0F;
  color: #FFF;
}

.creative-sections .section {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}
.creative-sections .section-light {
  background: #F2F2F0;
  color: #0F0F0F;
}
.creative-sections .section-dark {
  background: #0F0F0F;
  color: #FFF;
}
.creative-sections .section-inner {
  max-width: 1100px;
  width: 100%;
  padding: 80px 40px;
}
.creative-nav .nav-btn {
  background: none; border: none; color: #888;
  cursor: pointer; font-family: inherit; font-size: inherit;
  padding: 0; transition: color 0.2s;
}
.creative-nav .nav-btn:hover,
.creative-nav .nav-btn.active { color: #FFF; }
.creative-section-label {
  font-family: 'DM Mono', monospace;
  font-size: 12px; color: #666; margin-bottom: 40px;
}
.cr-hero-wrap {
  width: 100%; height: 100vh;
  display: flex; flex-direction: column;
  justify-content: center; padding: 40px;
}
.cr-hero-name {
  font-size: 100px; font-weight: 300;
  letter-spacing: -0.03em; margin-bottom: 16px;
}
.cr-hero-role { font-size: 20px; font-weight: 300; color: #999; margin-bottom: 64px; }
.cr-hero-teaser {
  display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
}
.cr-hero-teaser-item {
  height: 280px; background: #1A1A1A; position: relative; overflow: hidden;
}
.cr-hero-teaser-item:hover .cr-teaser-overlay { opacity: 1; }
.cr-teaser-overlay {
  position: absolute; inset: 0;
  background: rgba(0,0,0,0.8);
  display: flex; flex-direction: column; justify-content: flex-end;
  padding: 24px; opacity: 0; transition: opacity 0.3s;
}
.cr-work-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 24px;
}
.cr-work-card {
  background: #E8E5E0;
  border-radius: 12px;
  padding: 40px;
  position: relative;
  overflow: hidden;
  transition: transform 0.2s;
}
.cr-work-card:hover {
  transform: translateY(-2px);
}
.cr-work-card-name {
  font-size: 24px;
  font-weight: 400;
  margin-bottom: 8px;
  color: #0F0F0F;
}
.cr-work-card-role {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  color: #666;
  margin-bottom: 16px;
}
.cr-work-card-desc {
  font-size: 14px;
  line-height: 1.7;
  color: #444;
  margin-bottom: 20px;
}
.cr-work-card-tech {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.cr-work-chip {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: #555;
  background: rgba(15,15,15,0.06);
  border: 1px solid rgba(15,15,15,0.12);
  border-radius: 4px;
  padding: 3px 8px;
}
.cr-exp-timeline {
  border-top: 1px solid #222;
}
.cr-exp-item {
  padding: 32px 0;
  border-bottom: 1px solid #222;
}
.cr-exp-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}
.cr-exp-company {
  font-size: 18px;
  font-weight: 500;
}
.cr-exp-role {
  font-size: 14px;
  color: #999;
  margin-left: 12px;
}
.cr-exp-date {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  color: #666;
  white-space: nowrap;
}
.cr-exp-desc {
  font-size: 14px;
  line-height: 1.7;
  color: #CCC;
}
.cr-edu-label {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-top: 32px;
  margin-bottom: 16px;
}
.cr-edu-item {
  padding: 20px 0;
  border-bottom: 1px solid #222;
}
.cr-edu-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}
.cr-edu-school {
  font-size: 16px;
  font-weight: 500;
}
.cr-edu-degree {
  font-size: 13px;
  color: #999;
  margin-left: 12px;
}
.cr-edu-date {
  font-family: 'DM Mono', monospace;
  font-size: 12px;
  color: #666;
  white-space: nowrap;
}
.cr-skills-grid {
  display: flex;
  flex-direction: column;
  gap: 32px;
}
.cr-skill-group {
  margin-bottom: 0;
}
.cr-skill-group-title {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  font-weight: 400;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 12px;
}
.cr-skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.cr-skill-tag {
  font-size: 13px;
  color: #444;
  background: rgba(15,15,15,0.05);
  border: 1px solid rgba(15,15,15,0.1);
  border-radius: 6px;
  padding: 6px 14px;
  display: inline-block;
}
.cr-about-wrap { display: flex; gap: 48px; align-items: center; }
.cr-about-portrait { width: 240px; height: 240px; border-radius: 50%; background: #333; flex-shrink: 0; }
.cr-about-right { flex: 1; }
.cr-about-right h2 { font-size: 28px; margin-bottom: 8px; }
.cr-about-role { color: #999; margin-bottom: 24px; font-family: 'DM Mono', monospace; font-size: 13px; }
.cr-about-right p { font-size: 15px; line-height: 1.8; margin-bottom: 16px; color: #CCC; }
.cr-about-thumbs { display: flex; gap: 12px; margin-top: 24px; }
.cr-about-thumb { width: 100px; height: 100px; background: #333; border-radius: 8px; }
.cr-about-skills-sidebar {
  margin-top: 32px;
  padding-top: 24px;
  border-top: 1px solid #222;
}
.cr-about-skills-sidebar h4 {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: #666;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  margin-bottom: 16px;
}
.cr-about-skill-group {
  margin-bottom: 16px;
}
.cr-about-skill-title {
  font-family: 'DM Mono', monospace;
  font-size: 11px;
  color: #888;
  margin-bottom: 6px;
}
.cr-about-skill-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.cr-about-skill-tag {
  font-size: 12px;
  color: #AAA;
  background: rgba(255,255,255,0.06);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 4px;
  padding: 3px 10px;
  display: inline-block;
}
.cr-contact-wrap { text-align: center; }
.cr-contact-heading { font-size: 70px; font-weight: 300; margin-bottom: 32px; }
.cr-contact-email {
  font-size: 22px; color: #FFF; text-decoration: none;
  display: inline-block; margin-bottom: 48px;
  border-bottom: 1px solid rgba(255,255,255,0.3); padding-bottom: 2px;
  transition: border-color 0.2s;
}
.cr-contact-email:hover { border-color: #FFF; }
.cr-contact-links { display: flex; flex-direction: column; align-items: center; gap: 16px; }
.cr-contact-link { font-size: 18px; color: #999; text-decoration: none; transition: color 0.2s; border-bottom: 1px solid transparent; }
.cr-contact-link:hover { color: #FFF; border-bottom-color: rgba(255,255,255,0.3); }
.cr-contact-wechat { position: relative; }
.cr-wechat-qr-popup {
  position: absolute; bottom: calc(100% + 12px); left: 50%; transform: translateX(-50%);
  background: #1A1A1A; border: 1px solid #333; border-radius: 8px;
  padding: 12px; box-shadow: 0 8px 32px rgba(0,0,0,0.6);
  opacity: 0; pointer-events: none; transition: opacity 0.2s;
  z-index: 10;
}
.cr-contact-wechat:hover .cr-wechat-qr-popup { opacity: 1; pointer-events: auto; }
.cr-wechat-qr-popup::after {
  content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%);
  border: 6px solid transparent; border-top-color: #333;
}
.cr-wechat-qr-img { width: 160px; height: 160px; display: block; border-radius: 4px; }
.cr-empty-state {
  font-family: 'DM Mono', monospace;
  font-size: 13px;
  color: #555;
  text-align: center;
  padding: 40px 0;
}
"""
        return content, css

    def _render_personal_theme(self, knowledge, config):
        info = knowledge.get("personal_info", {})
        work = knowledge.get("work_experience", {}).get("work_list", [])
        projects = knowledge.get("projects", {}).get("project_list", [])
        educations = knowledge.get("education", {}).get("education_list", [])
        skill_sections = _normalize_skills(knowledge)

        name = info.get("name", "Wang Fang")
        role = info.get("target_position", "I help early-stage teams build the things people keep coming back to.")
        city = info.get("city", "Shanghai")
        self_intro = info.get("self_intro", "Growth and community professional with 5+ years in product-led growth. I specialize in building communities that drive user retention and activation.")
        email = info.get("email", "wangfang@email.com")
        phone = info.get("phone", "")
        github = info.get("github", "")
        wechat_name = info.get("wechat_name", "")
        wechat_qr = info.get("wechat_qr", "")

        nav_labels = ["Home", "About", "Work", "Experience", "Contact"]
        nav_html = ""
        for i, label in enumerate(nav_labels):
            nav_html += f'<a class="nav-btn" href="#section-{i}">{label}</a>'

        work_html = ""
        if projects:
            for p in projects[:4]:
                p_name = p.get("name", "")
                p_period = p.get("period", "2024")
                p_role = p.get("role", "")
                p_desc = p.get("description", "")
                tech_stack = p.get("tech_stack", "")
                metric_html = f'<div class="pb-work-metric">{tech_stack}</div>' if tech_stack else ""
                js_name = p_name.replace("'", "\\'").replace('"', '&quot;').replace('\n', ' ').replace('\r', ' ')
                js_desc = p_desc.replace("'", "\\'").replace('"', '&quot;').replace('\n', ' ').replace('\r', ' ')
                work_html += f"""
                <div class="pb-work-entry">
                    <div class="pb-work-header">
                        <span class="pb-work-name">{p_name}</span>
                        <span class="pb-work-year">{p_period}</span>
                    </div>
                    <div class="pb-work-role">{p_role}</div>
                    <div class="pb-work-story">{p_desc}</div>
                    {metric_html}
                    <div class="pb-work-link"><a href="#" onclick="if(window.opener){{window.opener.askAboutPortfolioItem('{js_name}','{js_desc}');window.close();}}return false;">→ Learn more</a></div>
                </div>"""
        else:
            work_html = """
            <div class="pb-work-entry">
                <div class="pb-work-header"><span class="pb-work-name">Community Growth Program</span><span class="pb-work-year">2024</span></div>
                <div class="pb-work-role">Growth Lead</div>
                <div class="pb-work-story">Built a referral program from scratch that drove 300+ qualified leads in 3 months</div>
                <div class="pb-work-metric">30% of new sign-ups came from referrals</div>
            </div>
            <div class="pb-work-entry">
                <div class="pb-work-header"><span class="pb-work-name">User Retention Revamp</span><span class="pb-work-year">2023</span></div>
                <div class="pb-work-role">Product Growth Manager</div>
                <div class="pb-work-story">Redesigned the onboarding flow and implemented behavioral email triggers</div>
                <div class="pb-work-metric">D30 retention improved from 22% to 41%</div>
            </div>"""

        exp_html = ""
        if work:
            exp_html += '<div class="pb-exp-timeline"><div class="pb-exp-group-title">Work</div>'
            for w in work:
                position = w.get("position", "")
                company = w.get("company", "")
                period = w.get("period", "")
                desc = w.get("description", "")
                title = f"{position}{' · ' + company if company else ''}"
                period_html = f'<span class="pb-exp-period">{period}</span>' if period else ""
                desc_html = f'<div class="pb-exp-desc">{desc}</div>' if desc else ""
                exp_html += f"""
                <div class="pb-exp-entry">
                    <div class="pb-exp-dot"></div>
                    <div class="pb-exp-header">
                        <span class="pb-exp-title">{title}</span>
                        {period_html}
                    </div>
                    {desc_html}
                </div>"""
            exp_html += '</div>'

        edu_html = ""
        if educations:
            edu_html += '<div class="pb-exp-timeline pb-exp-edu"><div class="pb-exp-group-title">Education</div>'
            for edu in educations:
                school = edu.get("school", "")
                period = edu.get("period", "")
                degree = edu.get("degree", "")
                major = edu.get("major", "")
                period_html = f'<span class="pb-exp-period">{period}</span>' if period else ""
                subtitle = " · ".join(filter(None, [degree, major]))
                subtitle_html = f'<div class="pb-exp-subtitle">{subtitle}</div>' if subtitle else ""
                edu_html += f"""
                <div class="pb-exp-entry">
                    <div class="pb-exp-dot"></div>
                    <div class="pb-exp-header">
                        <span class="pb-exp-title">{school}</span>
                        {period_html}
                    </div>
                    {subtitle_html}
                </div>"""
            edu_html += '</div>'

        if not work and not educations:
            exp_html = '<p class="pb-body-text">No experience data available yet.</p>'

        skills_html = ""
        if skill_sections:
            for section in skill_sections:
                title = section.get("title", "")
                items = section.get("items", [])
                tags_html = ""
                for item in items:
                    sk_name = item.get("name", "")
                    sk_desc = item.get("desc", "")
                    label = sk_name + ("：" + sk_desc if sk_desc else "")
                    tags_html += f'<span class="pb-skill-tag">{label}</span>'
                skills_html += f"""
                <div class="pb-skills-group">
                    <div class="pb-skills-category">{title}</div>
                    <div class="pb-skills-tags">{tags_html}</div>
                </div>"""
        else:
            skills_html = '<p class="pb-body-text">No skills listed</p>'

        contact_grid_html = ""
        if phone:
            contact_grid_html += f"""
            <div class="pb-contact-item">
                <div class="pb-contact-label">Phone</div>
                <div class="pb-contact-value">
                    <a href="tel:{phone}">{phone}</a>
                </div>
            </div>"""
        if github:
            github_url = github if github.startswith("http") else f"https://github.com/{github}"
            contact_grid_html += f"""
            <div class="pb-contact-item">
                <div class="pb-contact-label">GitHub</div>
                <div class="pb-contact-value">
                    <a href="{github_url}" target="_blank" rel="noopener noreferrer">{github}</a>
                </div>
            </div>"""
        wechat_display = wechat_name if wechat_name else "微信"
        if wechat_qr:
            contact_grid_html += f"""
            <div class="pb-contact-item">
                <div class="pb-contact-label">WeChat</div>
                <div class="pb-contact-value">
                    <span class="pb-wechat-wrap">
                        <span>{wechat_display}</span>
                        <span class="pb-wechat-popup">
                            <img src="{wechat_qr}" alt="WeChat QR Code" />
                        </span>
                    </span>
                </div>
            </div>"""
        else:
            contact_grid_html += f"""
            <div class="pb-contact-item">
                <div class="pb-contact-label">WeChat</div>
                <div class="pb-contact-value">
                    <span>{wechat_display}</span>
                </div>
            </div>"""

        content = f"""
<div class="personal-brand-theme">
  <nav class="personal-nav">
    {nav_html}
  </nav>
  <div class="personal-sections">
    <section class="section" id="section-0">
      <div class="pb-hero-wrap" style="max-width: 800px;">
        <div class="pb-hero-left">
          <h1 class="pb-hero-name">{name}</h1>
          <p class="pb-hero-role">{role}</p>
          <div class="pb-hero-badge">
            <span class="pb-hero-dot"></span>
            <span>{city} · Open to opportunities</span>
          </div>
        </div>
        <div class="pb-hero-portrait"></div>
      </div>
    </section>
    <section class="section" id="section-1">
      <div class="section-inner" style="max-width: 800px;">
        <div class="pb-about-layout">
          <div class="pb-about-main">
            <p>{self_intro}</p>
            <p>I approach problems with first-principles thinking and a bias toward action. My work combines data analysis with deep empathy for user needs — understanding both the "what" and the "why" behind user behavior.</p>
          </div>
          <div class="pb-about-sidebar">
            <h4>Skills</h4>
            {skills_html}
          </div>
        </div>
      </div>
    </section>
    <section class="section" id="section-2">
      <div class="section-inner">
        <h2 class="pb-section-title">Selected work</h2>
        {work_html}
      </div>
    </section>
    <section class="section" id="section-3">
      <div class="section-inner" style="max-width: 800px;">
        <h2 class="pb-section-title">Experience</h2>
        {exp_html}
        {edu_html}
      </div>
    </section>
    <section class="section" id="section-4">
      <div class="section-inner" style="text-align: left;">
        <h2 class="pb-contact-heading">Find me</h2>
        <p class="pb-contact-sub">
            I'd love to hear from you — whether it's a role, a project, or just a conversation.
        </p>
        <a class="pb-contact-email" href="mailto:{email}">{email}</a>
        <div class="pb-contact-grid">
          {contact_grid_html}
        </div>
      </div>
    </section>
  </div>
</div>"""

        css = """
html { scroll-behavior: smooth; }
body { margin: 0; padding: 0; }
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&family=Lora:wght@400;500;600&display=swap');
.personal-brand-theme {
  font-family: 'Inter', sans-serif;
  background-color: #FEFDF9;
  color: #1A1A1A;
  height: 100%;
}
.personal-nav {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  box-sizing: border-box;
  z-index: 1000;
  display: flex;
  justify-content: flex-end;
  gap: 28px;
  padding: 24px 40px;
  font-size: 14px;
  background: #FEFDF9;
}

.personal-sections .section {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 80px 40px;
}
.personal-sections .section-inner {
  max-width: 680px;
  width: 100%;
}
.personal-nav .nav-btn {
  background: none; border: none; color: #999;
  cursor: pointer; font-family: inherit; font-size: inherit;
  padding: 0; transition: color 0.2s;
}
.personal-nav .nav-btn:hover,
.personal-nav .nav-btn.active { color: #C4502A; }
.pb-hero-wrap {
  display: flex; gap: 48px; align-items: center;
}
.pb-hero-left { flex: 1; }
.pb-hero-name {
  font-family: 'Lora', serif;
  font-size: 52px; font-weight: 400; margin-bottom: 16px;
}
.pb-hero-role {
  font-size: 22px; color: #333; margin-bottom: 24px; line-height: 1.5;
}
.pb-hero-badge {
  display: inline-flex; align-items: center; gap: 8px; font-size: 14px; color: #666;
}
.pb-hero-dot {
  width: 8px; height: 8px; background: #3DD68C; border-radius: 50%;
  animation: pb-pulse 2s infinite;
}
@keyframes pb-pulse { 0%,100% { opacity:1; } 50% { opacity:0.5; } }
.pb-hero-portrait {
  width: 160px; height: 160px; border-radius: 50%;
  background: #EEE5D8; flex-shrink: 0;
}
.pb-section-title {
  font-family: 'Lora', serif;
  font-size: 32px; margin-bottom: 32px;
}
.pb-body-text { font-size: 16px; line-height: 1.75; color: #333; }
.pb-body-text p { margin-bottom: 20px; }
.pb-pull-quote {
  font-family: 'Lora', serif; font-style: italic;
  font-size: 22px; text-align: center;
  margin: 56px 0; line-height: 1.6; color: #666;
}
.pb-work-entry { padding: 32px 0; border-bottom: 1px solid #E8E4D8; }
.pb-work-header { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 8px; }
.pb-work-name { font-size: 18px; font-weight: 600; font-family: 'Lora', serif; }
.pb-work-year { font-size: 14px; color: #999; }
.pb-work-role { font-size: 14px; color: #666; margin-bottom: 12px; }
.pb-work-story { font-size: 15px; line-height: 1.7; color: #333; margin-bottom: 12px; }
.pb-work-metric { font-size: 14px; color: #C4502A; margin-bottom: 8px; }
.pb-work-link a {
  font-size: 14px; color: #C4502A; text-decoration: none;
  border-bottom: 1px solid transparent; transition: border-color 0.2s;
}
.pb-work-link a:hover { border-bottom-color: #C4502A; }
.pb-exp-timeline {
  position: relative;
  padding-left: 28px;
  margin-bottom: 40px;
}
.pb-exp-timeline::before {
  content: '';
  position: absolute;
  left: 5px;
  top: 8px;
  bottom: 0;
  width: 2px;
  background: #E8E4D8;
}
.pb-exp-group-title {
  font-family: 'Lora', serif;
  font-size: 22px;
  margin-bottom: 24px;
  color: #1A1A1A;
}
.pb-exp-entry {
  position: relative;
  margin-bottom: 28px;
  padding-bottom: 28px;
  border-bottom: 1px solid #F0EDE6;
}
.pb-exp-entry:last-child {
  border-bottom: none;
  margin-bottom: 0;
  padding-bottom: 0;
}
.pb-exp-dot {
  position: absolute;
  left: -27px;
  top: 6px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: #C4502A;
  border: 2px solid #FEFDF9;
  box-shadow: 0 0 0 2px #C4502A;
}
.pb-exp-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 4px;
}
.pb-exp-title {
  font-size: 16px;
  font-weight: 600;
  font-family: 'Lora', serif;
  color: #1A1A1A;
}
.pb-exp-period {
  font-size: 13px;
  color: #999;
  flex-shrink: 0;
  margin-left: 12px;
}
.pb-exp-subtitle {
  font-size: 14px;
  color: #666;
  margin-bottom: 8px;
}
.pb-exp-desc {
  font-size: 14px;
  line-height: 1.7;
  color: #444;
}
.pb-exp-edu {
  margin-top: 40px;
}
.pb-about-layout { display: flex; gap: 48px; }
.pb-about-main { flex: 1.3; }
.pb-about-main p { font-size: 15px; line-height: 1.8; color: #333; margin-bottom: 16px; }
.pb-about-main p:first-child { font-family: 'Lora', serif; font-size: 18px; }
.pb-looking-for h4 {
  font-family: 'Lora', serif; font-size: 18px; margin: 24px 0 12px;
}
.pb-about-sidebar { flex: 1; }
.pb-about-sidebar h4 { font-size: 14px; font-weight: 600; margin-bottom: 16px; }
.pb-skills-group {
  margin-bottom: 20px;
}
.pb-skills-category {
  font-size: 12px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: #999;
  margin-bottom: 8px;
}
.pb-skills-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}
.pb-skill-tag {
  display: inline-block;
  padding: 4px 12px;
  font-size: 13px;
  color: #C4502A;
  background: #FDF5F0;
  border: 1px solid #F2D5C8;
  border-radius: 20px;
  line-height: 1.4;
}
.pb-contact-heading { font-family: 'Lora', serif; font-size: 28px; margin-bottom: 16px; }
.pb-contact-sub { font-size: 15px; line-height: 1.7; color: #666; margin-bottom: 32px; }
.pb-contact-email { font-size: 22px; color: #C4502A; text-decoration: none; display: inline-block; margin-bottom: 40px; }
.pb-contact-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; max-width: 480px; }
.pb-contact-item { border-top: 1px solid #E8E4D8; padding-top: 12px; }
.pb-contact-label { font-size: 14px; font-weight: 600; }
.pb-contact-value { font-size: 13px; color: #999; }
.pb-contact-value a { color: #C4502A; text-decoration: none; }
.pb-contact-value a:hover { text-decoration: underline; }
.pb-wechat-wrap { position: relative; display: inline-block; cursor: pointer; }
.pb-wechat-popup { display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); margin-bottom: 8px; z-index: 100; background: #FFF; padding: 8px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
.pb-wechat-wrap:hover .pb-wechat-popup { display: block; }
.pb-wechat-popup img { width: 150px; height: 150px; border-radius: 4px; }
.pb-wechat-popup::after { content: ''; position: absolute; top: 100%; left: 50%; transform: translateX(-50%); border: 6px solid transparent; border-top-color: #FFF; }
"""
        return content, css

html_builder = HTMLBuilder()
