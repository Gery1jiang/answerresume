def render_resume_to_html(resume: dict) -> str:
    """将简历JSON转换为HTML字符串"""
    personal = resume.get('personal', {})
    name = personal.get('name', '')
    phone = personal.get('phone', '')
    email = personal.get('email', '')
    city = personal.get('city', '')
    job_title = personal.get('jobTitle', '')
    summary = resume.get('summary', '')
    education = resume.get('education', [])
    work = resume.get('work', [])
    projects = resume.get('projects', [])
    skills = resume.get('skills', [])
    languages = resume.get('languages', [])
    certificates = resume.get('certificates', [])
    others = resume.get('others', [])
    
    html_parts = []
    
    html_parts.append(f'<div class="resume-card">')
    
    html_parts.append(f'<h1>{name}</h1>')
    
    contact_parts = []
    if phone:
        contact_parts.append(f'手机: {phone}')
    if email:
        contact_parts.append(f'邮箱: {email}')
    if city:
        contact_parts.append(f'城市: {city}')
    if job_title:
        contact_parts.append(f'求职意向: {job_title}')
    
    if contact_parts:
        html_parts.append(f'<div class="contact">{", ".join(contact_parts)}</div>')
    
    if summary:
        html_parts.append(f'<h2>个人概述</h2>')
        html_parts.append(f'<p class="summary">{summary}</p>')
    
    if education:
        html_parts.append(f'<h2>教育背景</h2>')
        for edu in education:
            school = edu.get('school', '')
            degree = edu.get('degree', '')
            major = edu.get('major', '')
            year = edu.get('year', '')
            if school or major:
                html_parts.append(f'<div class="item-header">')
                html_parts.append(f'<span class="school">')
                if school:
                    html_parts.append(school)
                if major:
                    if school:
                        html_parts.append(f' | {major}')
                    else:
                        html_parts.append(major)
                if degree:
                    html_parts.append(f' {degree}')
                html_parts.append(f'</span>')
                if year:
                    html_parts.append(f'<span class="date">{year}</span>')
                html_parts.append(f'</div>')
    
    if work:
        html_parts.append(f'<h2>工作经历</h2>')
        for exp in work:
            company = exp.get('company', '')
            title = exp.get('title', '')
            start_date = exp.get('startDate', '')
            end_date = exp.get('endDate', '')
            highlights = exp.get('highlights', [])
            
            html_parts.append(f'<div class="item-header">')
            html_parts.append(f'<span class="company">')
            if company:
                html_parts.append(company)
            if title:
                if company:
                    html_parts.append(f' | {title}')
                else:
                    html_parts.append(title)
            html_parts.append(f'</span>')
            date_str = ''
            if start_date:
                date_str = start_date
            if end_date:
                date_str += f' – {end_date}'
            if date_str:
                html_parts.append(f'<span class="date">{date_str}</span>')
            html_parts.append(f'</div>')
            
            if highlights:
                html_parts.append(f'<ul>')
                for h in highlights:
                    html_parts.append(f'<li>{h}</li>')
                html_parts.append(f'</ul>')
    
    if projects:
        html_parts.append(f'<h2>项目经验</h2>')
        for proj in projects:
            name = proj.get('name', '')
            role = proj.get('role', '')
            date = proj.get('date', '')
            highlights = proj.get('highlights', [])
            tech = proj.get('tech', '')
            
            html_parts.append(f'<div class="item-header">')
            html_parts.append(f'<span class="company">')
            if name:
                html_parts.append(name)
            if role:
                html_parts.append(f' | {role}')
            html_parts.append(f'</span>')
            if date:
                html_parts.append(f'<span class="date">{date}</span>')
            html_parts.append(f'</div>')
            
            if highlights:
                html_parts.append(f'<ul>')
                for h in highlights:
                    html_parts.append(f'<li>{h}</li>')
                html_parts.append(f'</ul>')
            
            if tech:
                html_parts.append(f'<div class="tech">技术栈: {tech}</div>')
    
    if skills:
        html_parts.append(f'<h2>专业技能</h2>')
        # New structured format: [{"category": "...", "items": [{"label": "...", "detail": "..."}]}]
        if isinstance(skills, list) and skills and isinstance(skills[0], dict) and "category" in skills[0]:
            for group in skills:
                cat = group.get("category", "")
                if cat:
                    html_parts.append(f'<h3 style="font-size:14px;margin:8px 0 4px;color:#333;">{cat}</h3>')
                for item in group.get("items", []):
                    label = item.get("label", "")
                    detail = item.get("detail", "")
                    if label:
                        html_parts.append(f'<div style="margin:2px 0;font-size:13px;"><strong>{label}</strong>')
                        if detail:
                            html_parts.append(f'：{detail}')
                        html_parts.append('</div>')
        else:
            # Legacy flat list format
            html_parts.append(f'<div class="skills-list">')
            for skill in skills:
                html_parts.append(f'<span class="skill-tag">{skill}</span>')
            html_parts.append(f'</div>')
    
    if languages:
        html_parts.append(f'<h2>语言能力</h2>')
        lang_parts = []
        for lang in languages:
            lang_name = lang.get('name', '')
            level = lang.get('level', '')
            if lang_name:
                if level:
                    lang_parts.append(f'{lang_name}: {level}')
                else:
                    lang_parts.append(lang_name)
        if lang_parts:
            html_parts.append(f'<p>{" | ".join(lang_parts)}</p>')
    
    if certificates:
        html_parts.append(f'<h2>证书荣誉</h2>')
        html_parts.append(f'<ul>')
        for cert in certificates:
            html_parts.append(f'<li>{cert}</li>')
        html_parts.append(f'</ul>')
    
    if others:
        html_parts.append(f'<h2>其他补充</h2>')
        html_parts.append(f'<ul>')
        for item in others:
            html_parts.append(f'<li>{item}</li>')
        html_parts.append(f'</ul>')
    
    html_parts.append(f'</div>')
    
    return ''.join(html_parts)

def get_resume_css() -> str:
    """读取公共简历样式文件"""
    import os
    css_path = os.path.join(os.path.dirname(__file__), "static", "resume.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            return f.read()
    return ""
