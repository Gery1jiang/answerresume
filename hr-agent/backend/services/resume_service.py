import os
import json
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, ListItem, ListFlowable
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from sqlalchemy.orm import Session as DBSession
from services.database import SessionLocal
from services.models import Resume
from config import settings
from typing import Optional


class ResumeService:
    def __init__(self, db: Optional[DBSession] = None):
        self.db = db or SessionLocal()

    def read_knowledge(self):
        knowledge_dir = settings.KNOWLEDGE_DIR
        knowledge_content = ""

        if not os.path.exists(knowledge_dir):
            return knowledge_content

        try:
            for filename in sorted(os.listdir(knowledge_dir)):
                if filename.endswith('.md'):
                    filepath = os.path.join(knowledge_dir, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            content = f.read()
                            category = filename.replace('.md', '')
                            knowledge_content += f"## {category}\n{content}\n\n"
                    except Exception as e:
                        print(f"Error reading {filename}: {e}")
        except Exception as e:
            print(f"Error reading knowledge directory: {e}")

        return knowledge_content

    def generate_resume_json(self, jd: str = "", target_job: str = "", user_id: str = "", raw_content: str = "") -> dict:
        from services.ai_service import generate_resume_json as ai_generate_resume
        return ai_generate_resume(jd=jd, target_job=target_job, user_id=user_id, raw_content=raw_content)

    def generate_resume_content(self, jd: str = "", target_job: str = "", user_id: str = "", raw_content: str = "") -> str:
        resume_json = self.generate_resume_json(jd=jd, target_job=target_job, user_id=user_id, raw_content=raw_content)
        return json.dumps(resume_json, ensure_ascii=False)

    def generate_pdf(self, content):
        try:
            pdfmetrics.registerFont(TTFont('SimHei', 'simhei.ttf'))
        except Exception:
            try:
                font_paths = [
                    'C:/Windows/Fonts/simhei.ttf',
                    '/Library/Fonts/SimHei.ttf',
                    '/usr/share/fonts/truetype/wqy/wqy-microhei.ttc',
                    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
                    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
                ]
                for font_path in font_paths:
                    if os.path.exists(font_path):
                        pdfmetrics.registerFont(TTFont('SimHei', font_path))
                        break
            except Exception:
                pass

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)

        font_name = 'SimHei' if 'SimHei' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'

        title_style = ParagraphStyle(
            "Title",
            fontSize=18,
            bold=True,
            alignment=1,
            spaceAfter=12,
            fontName=font_name
        )

        heading_style = ParagraphStyle(
            "Heading1",
            fontSize=14,
            bold=True,
            textColor=colors.darkblue,
            spaceBefore=12,
            spaceAfter=6,
            fontName=font_name
        )

        normal_style = ParagraphStyle(
            "BodyText",
            fontSize=10,
            leading=16,
            fontName=font_name
        )

        bullet_style = ParagraphStyle(
            "Bullet",
            fontSize=10,
            leading=16,
            leftIndent=12,
            fontName=font_name
        )

        resume_data = json.loads(content) if isinstance(content, str) else content

        elements = []

        personal = resume_data.get('personal', {})
        name = personal.get('name', '未命名')
        phone = personal.get('phone', '')
        email = personal.get('email', '')
        city = personal.get('city', '')
        job_title = personal.get('jobTitle', '')
        age = personal.get('age', '')

        contact_parts = []
        if phone:
            contact_parts.append(f"📱 {phone}")
        if email:
            contact_parts.append(f"📧 {email}")
        if city:
            contact_parts.append(f"📍 {city}")
        if age:
            contact_parts.append(f"🎂 {age}岁")

        elements.append(Paragraph(name, title_style))
        if contact_parts:
            elements.append(Paragraph(" | ".join(contact_parts), normal_style))
        if job_title:
            elements.append(Paragraph(f"🎯 {job_title}", normal_style))
        elements.append(Spacer(1, 12))

        summary = resume_data.get('summary', '')
        if summary:
            elements.append(Paragraph("个人概述", heading_style))
            elements.append(Paragraph(summary, normal_style))
            elements.append(Spacer(1, 8))

        work = resume_data.get('work', [])
        if work:
            elements.append(Paragraph("工作经历", heading_style))
            for w in work:
                company = w.get('company', '')
                title = w.get('title', '')
                start = w.get('startDate', '')
                end = w.get('endDate', '')
                highlights = w.get('highlights', [])

                header = f"**{company}** | {title}"
                if start or end:
                    header += f"（{start} – {end}）"
                elements.append(Paragraph(header, normal_style))

                for h in highlights:
                    elements.append(Paragraph(f"• {h}", bullet_style))
            elements.append(Spacer(1, 8))

        projects = resume_data.get('projects', [])
        if projects:
            elements.append(Paragraph("项目经验", heading_style))
            for p in projects:
                proj_name = p.get('name', '')
                role = p.get('role', '')
                date = p.get('date', '')
                tech = p.get('tech', '')
                highlights = p.get('highlights', [])

                header = f"**{proj_name}**"
                if date:
                    header += f"（{date}）"
                if role:
                    header += f" | 角色：{role}"
                elements.append(Paragraph(header, normal_style))
                if tech:
                    elements.append(Paragraph(f"技术栈：{tech}", bullet_style))
                for h in highlights:
                    elements.append(Paragraph(f"• {h}", bullet_style))
            elements.append(Spacer(1, 8))

        skills = resume_data.get('skills', [])
        if skills:
            elements.append(Paragraph("技能", heading_style))
            if isinstance(skills, dict):
                group_labels = [
                    ("hard_skills", "硬技能"),
                    ("soft_skills", "软技能"),
                    ("tool_skills", "工具平台"),
                ]
                for key, label in group_labels:
                    items = skills.get(key, [])
                    if items:
                        elements.append(Paragraph(f"<b>{label}：</b>" + "、".join(items), normal_style))
            else:
                skills_text = "、".join(skills) if isinstance(skills, list) else str(skills)
                elements.append(Paragraph(skills_text, normal_style))
            elements.append(Spacer(1, 8))

        languages = resume_data.get('languages', [])
        if languages:
            elements.append(Paragraph("语言能力", heading_style))
            for lang in languages:
                if isinstance(lang, dict):
                    name = lang.get('name', '')
                    level = lang.get('level', '')
                    parts = [p for p in [name, level] if p]
                    if parts:
                        elements.append(Paragraph("、".join(parts), normal_style))
                else:
                    elements.append(Paragraph(str(lang), normal_style))
            elements.append(Spacer(1, 8))

        certificates = resume_data.get('certificates', [])
        if certificates:
            elements.append(Paragraph("证书", heading_style))
            for cert in certificates:
                elements.append(Paragraph(f"• {cert}", bullet_style))
            elements.append(Spacer(1, 8))

        education = resume_data.get('education', [])
        if education:
            elements.append(Paragraph("教育背景", heading_style))
            for edu in education:
                school = edu.get('school', '')
                degree = edu.get('degree', '')
                major = edu.get('major', '')
                year = edu.get('year', '')
                parts = [p for p in [school, degree, major, year] if p]
                if parts:
                    elements.append(Paragraph(" | ".join(parts), normal_style))
            elements.append(Spacer(1, 8))

        doc.build(elements)
        buffer.seek(0)
        return buffer.getvalue()

    def save_resume(self, user_info: str = "", target_job: str = "", user_id: str = "", raw_content: str = "", jd: str = ""):
        # raw_content overrides KB when provided (from uploaded file OCR)
        # user_info / jd are supplementary references (JD or user notes)
        _jd = jd or user_info
        content = self.generate_resume_content(jd=_jd, target_job=target_job, user_id=user_id, raw_content=raw_content)

        resume_json = json.loads(content)
        pdf_bytes = self.generate_pdf(resume_json)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"resume_{timestamp}.pdf"

        os.makedirs(settings.RESUME_DIR, exist_ok=True)
        filepath = os.path.join(settings.RESUME_DIR, filename)

        with open(filepath, 'wb') as f:
            f.write(pdf_bytes)

        existing_resumes = self.db.query(Resume).all()
        is_default = len(existing_resumes) == 0

        personal = resume_json.get('personal', {})
        name = personal.get('name', f'简历_{timestamp}')

        resume = Resume(
            filename=filename,
            title=name,
            content=content,
            is_default=is_default,
            user_id=user_id,
        )

        self.db.add(resume)
        self.db.commit()
        self.db.refresh(resume)

        return resume.id

    def get_resumes(self, user_id=None):
        from datetime import timezone, timedelta
        beijing_tz = timezone(timedelta(hours=8))
        q = self.db.query(Resume)
        if user_id and str(user_id).strip():
            q = q.filter(Resume.user_id == user_id)
        resumes = q.order_by(Resume.created_at.desc()).all()
        result = []
        for r in resumes:
            created = r.created_at
            if created:
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                created = created.astimezone(beijing_tz)
                created_str = created.strftime("%Y-%m-%d %H:%M:%S")
            else:
                created_str = None
            _job_title = ""
            if r.content:
                try:
                    _parsed = json.loads(r.content)
                    _job_title = (_parsed.get("personal", {}) or {}).get("jobTitle", "")
                except Exception:
                    pass
            result.append({
                "id": r.id,
                "filename": r.filename,
                "title": r.title,
                "job_title": _job_title,
                "created_at": created_str,
                "is_default": r.is_default
            })
        return result

    def get_resume_by_id(self, resume_id, user_id=""):
        q = self.db.query(Resume).filter(Resume.id == resume_id)
        if user_id:
            q = q.filter(Resume.user_id == user_id)
        return q.first()

    def get_default_resume(self, user_id=""):
        q = self.db.query(Resume).filter(Resume.is_default == True)
        if user_id:
            q = q.filter(Resume.user_id == user_id)
        return q.first()

    def set_default_resume(self, resume_id, user_id=""):
        q = self.db.query(Resume).filter(Resume.id == resume_id)
        if user_id:
            q = q.filter(Resume.user_id == user_id)
        resume = q.first()
        if not resume:
            return False

        self.db.query(Resume).filter(Resume.user_id == user_id).update({Resume.is_default: False})
        resume.is_default = True
        self.db.commit()
        return True

    def delete_resume(self, resume_id, user_id=""):
        q = self.db.query(Resume).filter(Resume.id == resume_id)
        if user_id:
            q = q.filter(Resume.user_id == user_id)
        resume = q.first()
        if not resume:
            return False

        if resume.is_default:
            other_resumes = self.db.query(Resume).filter(Resume.id != resume_id).all()
            if other_resumes:
                other_resumes[0].is_default = True

        filepath = os.path.join(settings.RESUME_DIR, resume.filename)
        if os.path.exists(filepath):
            os.remove(filepath)

        self.db.delete(resume)
        self.db.commit()
        return True

resume_service = ResumeService()