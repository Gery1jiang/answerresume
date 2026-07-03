import json
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv
from typing import Optional
from config import settings
from services.prompt_manager import prompt_manager

load_dotenv(".env")

def _sync_db_to_md(user_id: str = ""):
    """Sync all knowledge from DB to markdown files for a given user."""
    from services.database import SessionLocal
    from services.models.knowledge_base import KnowledgeBase
    from config import get_user_knowledge_dir
    db = SessionLocal()
    try:
        records = db.query(KnowledgeBase).filter(KnowledgeBase.user_id == user_id).all()
        knowledge_dir = get_user_knowledge_dir(user_id)
        os.makedirs(knowledge_dir, exist_ok=True)
        category_map = {
            "personal_info": "01_个人信息",
            "education": "02_教育背景",
            "work_experience": "03_工作经历",
            "projects": "04_项目经历",
            "skills": "05_专业技能栈",
            "faq": "06_HR高频问答库",
            "stats": "07_高频问题统计",
        }
        for r in records:
            filename = category_map.get(r.category, r.category)
            filepath = os.path.join(knowledge_dir, f"{filename}.md")
            raw = json.loads(r.data) if r.data else {}
            lines = [f"## {filename}"]
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        for ik, iv in item.items():
                            lines.append(f"- {ik}：{iv}" if iv else f"- {ik}")
                    else:
                        lines.append(f"- {item}")
            elif isinstance(raw, dict):
                for k, v in raw.items():
                    if isinstance(v, list):
                        for item in v:
                            if isinstance(item, dict):
                                for ik, iv in item.items():
                                    lines.append(f"- {ik}：{iv}" if iv else f"- {ik}")
                            else:
                                lines.append(f"- {item}")
                    elif isinstance(v, dict):
                        for ik, iv in v.items():
                            if iv:
                                lines.append(f"- {ik}：{iv}")
                    elif v:
                        lines.append(f"- {k}：{v}")
            content = "\n".join(lines)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
    finally:
        db.close()


def _create_llm(base_url: str, api_key: str, model: str, timeout: int = 30):
    return ChatOpenAI(
        base_url=base_url,
        api_key=api_key,
        model=model,
        temperature=0.3,
        timeout=timeout,
        max_retries=1,
    )

def _get_llm_with_fallback(timeout: int = 30) -> ChatOpenAI:
    """返回管理端配置的 LLM 实例。DB → env 兜底。"""
    from config import get_admin_llm_config
    _cfg = get_admin_llm_config()
    return _create_llm(
        _cfg["api_base"],
        _cfg["api_key"],
        _cfg["model"],
        timeout=timeout,
    )

_llm_instance = None

def _ensure_llm():
    """Lazy-init the global LLM instance."""
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = _get_llm_with_fallback(120)

def set_llm(instance):
    """Override the global LLM instance (for testing)."""
    global _llm_instance
    _llm_instance = instance

def get_llm():
    """Get the current LLM instance."""
    _ensure_llm()
    return _llm_instance

# Module-level backward compat: `from services.ai_service import llm` returns a proxy
# that delegates to the lazily-initialized LLM instance.
class _LLMProxy:
    """Proxy that delegates attribute access to the real LLM instance.
    This allows `from services.ai_service import llm` to work without
    triggering LLM creation at import time."""
    def __getattr__(self, name):
        return getattr(get_llm(), name)
    def __setattr__(self, name, value):
        setattr(get_llm(), name, value)
    def __repr__(self):
        return f"<LLMProxy for {get_llm()!r}>"
    def __call__(self, *args, **kwargs):
        return get_llm()(*args, **kwargs)
    def __bool__(self):
        return True

llm = _LLMProxy()

# JSON输出格式要求（追加到配置提示词后面）
JSON_FORMAT_REQUIREMENT = """

## JSON 格式要求
严格按照上面的排版约束（标点、加粗、空行、日期格式等）填充各字段内容。输出纯JSON，不要用markdown代码块，不要输出其他文字。结构如下：
注意：skills 为扁平数组，每项用短标签形式（如"产品规划"），不要用描述性短语，从知识库中挑选与目标岗位最贴近的 6-10 项。
{{
  "personal": {{"name": "", "phone": "", "email": "", "jobTitle": "", "personal_website": ""}},
  "summary": "",
  "education": [{{"school": "", "degree": "", "major": "", "year": ""}}],
  "work": [
    {{"company": "", "title": "", "startDate": "", "endDate": "", "highlights": ["成果描述一", "成果描述二"]}}
  ],
  "projects": [
    {{"name": "", "role": "", "date": "", "highlights": ["成果描述一", "成果描述二"], "tech": "", "company": ""}}
  ],
  "skills": [],
  "languages": [{{"name": "", "level": ""}}],
  "certificates": [],
  "others": []
}}
"""

# 用户输入模板
USER_INFO_TEMPLATE = """

## 目标岗位
{target_job}

## 岗位描述（JD，仅作匹配参考，不是个人经历）
{jd_text}

## 知识库（个人真实经历，简历内容以此为准）
{knowledge}
"""

def read_knowledge(user_id: str = ""):
    if user_id:
        # 同步 DB → MD 文件
        from services.database import SessionLocal
        from services.models import KnowledgeBase
        from config import get_user_knowledge_dir
        db = SessionLocal()
        try:
            rows = db.query(KnowledgeBase).filter(
                KnowledgeBase.user_id == user_id,
                ~KnowledgeBase.category.in_(['main_kb_ids', 'appendix_records', 'welcome_config'])
            ).order_by(KnowledgeBase.id).all()
            if rows:
                from services.knowledge_manager import _sync_category_to_md
                for r in rows:
                    try:
                        parsed = json.loads(r.data) if isinstance(r.data, str) else r.data
                    except Exception:
                        parsed = {}
                    _sync_category_to_md(r.category, parsed, user_id)
        finally:
            db.close()
        knowledge_dir = get_user_knowledge_dir(user_id)
    else:
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

def generate_resume_json(jd: str = "", target_job: str = "", user_id: str = "", raw_content: str = "") -> dict:
    
    if user_id:
        from services.knowledge_manager import _get_all_kb_data
        kb_data = _get_all_kb_data(user_id=user_id)
        work_list = kb_data.get("work_experience", {}).get("work_list", [])
        edu_list = kb_data.get("education", {}).get("education_list", [])
        proj_list = kb_data.get("projects", {}).get("project_list", [])

    knowledge = read_knowledge(user_id)
    if not knowledge:
        knowledge = "（知识库为空，仅根据用户输入生成简历）"

    base_prompt = prompt_manager.get("resume_prompt", "")
    user_section = USER_INFO_TEMPLATE.format(
        target_job=target_job or "未提供",
        jd_text=jd or "（无）",
        knowledge=knowledge
    )
    # 如果用户上传了简历文件（raw_content），替换知识库内容
    if raw_content:
        user_section = USER_INFO_TEMPLATE.format(
            target_job=target_job or "未提供",
            jd_text=jd or "（无）",
            knowledge=raw_content
        )
    prompt = base_prompt + JSON_FORMAT_REQUIREMENT + user_section

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        content = response.content.strip()
        
        if content.startswith("```json"):
            content = content[7:]
        elif content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        if not content.startswith("{"):
            raise ValueError(f"AI 未返回JSON格式")
        
        resume_json = json.loads(content)

                # 用 DB 结构化数据覆盖 personal 字段（防 LLM 遗漏或编造）
        if user_id:
            kb_personal = kb_data.get("personal_info", {})
            if resume_json.get("personal") and kb_personal.get("personal_website"):
                resume_json["personal"]["personal_website"] = kb_personal["personal_website"]

            if resume_json.get("work"):
                db_work_map = {w.get("company",""): w for w in work_list if w.get("company")}
                for w in resume_json["work"]:
                    company = w.get("company", "")
                    if company in db_work_map:
                        dw = db_work_map[company]
                        w["company"] = dw.get("company", company)
                        w["title"] = dw.get("position", w["title"])
            if resume_json.get("education"):
                db_edu_map = {e.get("school", ""): e for e in edu_list if e.get("school")}
                for e in resume_json["education"]:
                    school = e.get("school", "")
                    if school in db_edu_map:
                        e["school"] = db_edu_map[school].get("school", school)
            if resume_json.get("projects"):
                db_proj_map = {p.get("name", ""): p for p in proj_list if p.get("name")}
                db_names_used = set()
                for p in resume_json["projects"]:
                    name = p.get("name", "")
                    if name in db_proj_map:
                        db_p = db_proj_map[name]
                        p["name"] = db_p.get("name", name)
                        # 优先用 DB 的项目时间（覆盖 LLM 乱猜的日期）
                        if db_p.get("period"):
                            p["date"] = db_p["period"]
                        if not p.get("company"):
                            p["company"] = db_p.get("company", "")
                        db_names_used.add(name)
                    elif not name:
                        # 补充缺失的项目名：取第一个未使用的DB项目
                        for db_n, db_p in db_proj_map.items():
                            if db_n not in db_names_used:
                                p["name"] = db_p.get("name", db_n)
                                p["role"] = db_p.get("role", p.get("role", ""))
                                p["tech"] = db_p.get("tech_stack", p.get("tech", ""))
                                if db_p.get("period"):
                                    p["date"] = db_p["period"]
                                if not p.get("company"):
                                    p["company"] = db_p.get("company", "")
                                db_names_used.add(db_n)
                                break

            # 项目仍无日期时，从关联工作经历的时间段取兜底（包含关系，并非相等）
            if resume_json.get("projects") and resume_json.get("work"):
                work_by_company = {w.get("company", ""): w for w in resume_json["work"] if w.get("company")}
                for p in resume_json["projects"]:
                    if not p.get("date"):
                        comp = p.get("company", "")
                        if comp and comp in work_by_company:
                            w = work_by_company[comp]
                            sd = w.get("startDate", "")
                            ed = w.get("endDate", "")
                            if sd and ed:
                                p["date"] = f"{sd} - {ed}"

        # 如果传入了 target_job，覆盖 LLM 输出的岗位名（防 LLM 从 KB 取错了）
        if target_job:
            import re as _re
            target_job = _re.sub(r'^(大厂|头部|知名|一线|顶级|资深|高级)[-\s]?', '', target_job).strip()
            if "personal" not in resume_json:
                resume_json["personal"] = {}
            resume_json["personal"]["jobTitle"] = target_job

        # 去重：LLM 有时会把职位名当作公司名写成第二条，检测并移除
        if resume_json.get("work"):
            _companies = [w.get("company", "") for w in resume_json["work"]]
            _titles = [w.get("title", "") for w in resume_json["work"]]
            _keep = []
            for w in resume_json["work"]:
                c = w.get("company", "")
                t = w.get("title", "")
                if c and t and c in _titles:
                    continue
                _keep.append(w)
            resume_json["work"] = _keep

        # 补充 LLM 遗漏的工作经历（如非公司名的个人研究经历）
        if user_id and work_list:
            _short = {w.get("company", "") for w in resume_json.get("work", [])}
            for w in work_list:
                company = w.get("company", "")
                if company and company not in _short:
                    _matched = any(company[:4] in e or e[:4] in company for e in _short)
                    if not _matched:
                        if "work" not in resume_json:
                            resume_json["work"] = []
                        _period = w.get("period", "")
                        _parts = _period.split(" - ") if " - " in _period else ["", ""]
                        _desc_lines = [line.lstrip("- ").strip() for line in w.get("description", "").split("\n") if line.strip().startswith("- ")]
                        # 跨越不同子章节均匀采样，最多取5条
                        if len(_desc_lines) > 5:
                            step = len(_desc_lines) / 5
                            sampled = [_desc_lines[int(i * step)] for i in range(5)]
                        else:
                            sampled = _desc_lines
                        resume_json["work"].append({
                            "company": company,
                            "title": w.get("position", ""),
                            "startDate": _parts[0],
                            "endDate": _parts[1],
                            "highlights": sampled,
                        })

        # 排序：公司类按 endDate 倒序，非公司名排后，各自内部按 endDate 排（至今最前）
        work = resume_json.get("work", [])
        if work:
            _company_keywords = ["有限公司", "公司", "集团", "股份", "工作室", "事务所"]

            def _work_sort_key(w):
                ed = w.get("endDate", "")
                ed_key = "999999" if "至今" in ed else ed.replace(".", "").replace("-", "")
                sd = w.get("startDate", "")
                sd_key = sd.replace(".", "").replace("-", "")
                return (int(ed_key) if ed_key.isdigit() else 0, int(sd_key) if sd_key.isdigit() else 0)

            normal = [w for w in work if any(k in w.get("company", "") for k in _company_keywords)]
            personal = [w for w in work if not any(k in w.get("company", "") for k in _company_keywords)]
            normal.sort(key=_work_sort_key, reverse=True)
            personal.sort(key=_work_sort_key, reverse=True)
            resume_json["work"] = normal + personal

        # 项目排序：endDate 倒序（至今最前），相同 endDate 按 startDate 倒序
        projects = resume_json.get("projects", [])
        if projects:
            def _proj_sort_key(p):
                ed = p.get("date", "").split(" - ")[1] if " - " in p.get("date", "") else p.get("date", "")
                sd = p.get("date", "").split(" - ")[0] if " - " in p.get("date", "") else ""
                # "至今"排最前 → 用极大值
                ed_key = "999999" if "至今" in ed else ed.replace(".", "").replace("-", "")
                sd_key = sd.replace(".", "").replace("-", "")
                return (int(ed_key) if ed_key.isdigit() else 0, int(sd_key) if sd_key.isdigit() else 0)
            projects.sort(key=_proj_sort_key, reverse=True)
            resume_json["projects"] = projects

        return resume_json
    except json.JSONDecodeError as e:
        raise ValueError(f"AI 输出格式错误: {str(e)}")
    except ValueError as e:
        raise e
    except Exception as e:
        raise ValueError(f"生成失败: {str(e)}")