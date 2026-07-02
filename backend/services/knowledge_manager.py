"""
Knowledge Manager - LLM-powered knowledge base management tool.
Handles: preview (parse user intent), confirm (apply changes), FAQ regeneration.
"""
import json
import hashlib
import time
import os
from typing import Optional, Dict, Any

from langchain_core.messages import HumanMessage, SystemMessage

from services.database import SessionLocal
from services.models import KnowledgeBase
from services.rag_service import rag_service
from services.ai_service import llm as ai_llm
from config import settings

# ============================================================
# Preview Storage (file-based, survives hot reload)
# ============================================================

PREVIEW_FILE = "/tmp/knowledge_previews.json"


class PreviewStorage:
    def __init__(self, ttl: int = 600):
        self._ttl = ttl
        self._store: Dict[str, dict] = {}
        self._load()

    def _load(self):
        try:
            if os.path.exists(PREVIEW_FILE):
                with open(PREVIEW_FILE, "r") as f:
                    content = f.read().strip()
                    if content:
                        self._store = json.loads(content)
        except Exception:
            self._store = {}

    def _save(self):
        try:
            os.makedirs(os.path.dirname(PREVIEW_FILE) or ".", exist_ok=True)
            with open(PREVIEW_FILE, "w") as f:
                json.dump(self._store, f)
        except Exception:
            pass

    def store(self, data: dict) -> str:
        content = json.dumps(data, ensure_ascii=False, sort_keys=True)
        preview_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        self._store[preview_id] = {"data": data, "created_at": time.time()}
        self._save()
        return preview_id

    def get(self, preview_id: str) -> Optional[dict]:
        self._load()
        entry = self._store.get(preview_id)
        if not entry:
            return None
        if time.time() - entry["created_at"] > self._ttl:
            del self._store[preview_id]
            self._save()
            return None
        return entry["data"]

    def invalidate(self, preview_id: str):
        self._load()
        self._store.pop(preview_id, None)
        self._save()

preview_storage = PreviewStorage()


# ============================================================
# Helper: sync category data to MD file
# ============================================================

def _category_to_filename(category: str) -> str:
    mapping = {
        "personal_info": "01_个人信息",
        "education": "02_教育背景",
        "work_experience": "03_工作经历",
        "projects": "04_项目经历",
        "skills": "05_专业技能栈",
        "faq": "06_HR高频问答库",
        "stats": "07_高频问题统计",
    }
    return mapping.get(category, category)


def _get_kb_dir(user_id=""):
    """Get the per-user or global knowledge directory."""
    if user_id:
        return os.path.join(settings.USER_DATA_DIR, user_id, "knowledge")
    return settings.KNOWLEDGE_DIR


def _cleanup_stale_md_files(user_id=""):
    """Remove MD files for categories no longer in the DB."""
    db = SessionLocal()
    try:
        q = db.query(KnowledgeBase.category)
        if user_id:
            q = q.filter(KnowledgeBase.user_id == user_id)
        known_categories = [row[0] for row in q.all()]
        known_filenames = {_category_to_filename(c) for c in known_categories}
        # Always keep 07_高频问题统计 (stats) even if not in DB yet
        known_filenames.add("07_高频问题统计")
    finally:
        db.close()

    kb_dir = _get_kb_dir(user_id)
    if not os.path.isdir(kb_dir):
        return

    for fname in os.listdir(kb_dir):
        if not fname.endswith(".md"):
            continue
        stem = fname[:-3]
        if stem not in known_filenames:
            filepath = os.path.join(kb_dir, fname)
            try:
                os.remove(filepath)
                print(f"[knowledge_manager] Removed stale MD file: {fname}")
            except OSError as e:
                print(f"[knowledge_manager] Failed to remove {fname}: {e}")


def _sync_category_to_md(category: str, data: dict, user_id=""):
    """Write structured data to the corresponding MD file."""
    filename = _category_to_filename(category)
    kb_dir = _get_kb_dir(user_id)
    os.makedirs(kb_dir, exist_ok=True)
    filepath = os.path.join(kb_dir, f"{filename}.md")

    lines = []
    if category == "personal_info":
        lines.append("## 个人信息")
        field_map = {
            "name": "姓名", "age": "年龄", "city": "所在城市",
            "email": "邮箱", "phone": "电话", "github": "GitHub",
            "personal_website": "个人网站",
            "work_years": "工作年限", "current_status": "当前状态",
            "target_position": "意向岗位", "expected_location": "期望工作地点",
            "start_date": "到岗时间", "salary_expectation": "薪资期望范围",
            "wechat_name": "微信昵称", "wechat_qr": "微信二维码",
        }
        for eng, chn in field_map.items():
            v = data.get(eng) or data.get("basic_info", {}).get(eng, "")
            if v:
                lines.append(f"- {chn}：{v}")
        tags = data.get("job_tags", [])
        if tags:
            lines.append("")
            lines.append("## 职业标签")
            for i, t in enumerate(tags):
                lines.append(f"- 核心标签{i+1}：{t}")
        intro = data.get("self_intro") or data.get("intro", "")
        if intro:
            lines.append("")
            lines.append("## 个人简介")
            lines.append(intro)
    elif category == "education":
        lines.append("## 教育背景")
        for edu in data.get("education_list", []):
            lines.append(f"- **{edu.get('school', '')}** ({edu.get('period', '')}): {edu.get('degree', '')}")
    elif category == "work_experience":
        lines.append("## 工作经历")
        for work in data.get("work_list", []):
            lines.append(f"### {work.get('company', '')} ({work.get('period', '')})")
            lines.append(f"- 职位: {work.get('position', '')}")
            if work.get("description"):
                for dline in work["description"].split("\n"):
                    stripped = dline.strip()
                    if stripped:
                        lines.append(f"  {stripped}" if stripped.startswith("- ") else f"- {stripped}")
    elif category == "projects":
        lines.append("## 项目经历")
        for proj in data.get("project_list", []):
            period = proj.get("period", "")
            period_str = f" ({period})" if period else ""
            lines.append(f"### {proj.get('name', '')}{period_str}")
            lines.append(f"- 角色: {proj.get('role', '')}")
            lines.append(f"- 技术: {proj.get('tech_stack', '')}")
            if proj.get("company"):
                lines.append(f"- 所属公司/阶段: {proj['company']}")
            if proj.get("description"):
                for dline in proj["description"].split("\n"):
                    stripped = dline.strip()
                    if stripped:
                        lines.append(f"  {stripped}" if stripped.startswith("- ") else f"- {stripped}")
    elif category == "skills":
        lines.append("## 专业技能栈")
        sections = data.get("skill_sections", [])
        if sections:
            for section in sections:
                title = section.get("title", "")
                items = section.get("items", [])
                if not title and not items:
                    continue
                lines.append(f"### {title}")
                for item in items:
                    name = item.get("name", "")
                    desc = item.get("desc", "")
                    if name:
                        lines.append(f"- **{name}**：{desc}")
        else:
            # Legacy: skill_groups dict format
            for cat, tags in data.get("skill_groups", {}).items():
                lines.append(f"- {cat}: {', '.join(tags)}")
    elif category == "faq":
        lines.append("## HR高频问答库")
        for qa in data.get("faq_list", []):
            lines.append(f"**Q: {qa.get('question', '')}**")
            lines.append(f"A: {qa.get('answer', '')}")
            lines.append("")
    elif category == "stats":
        lines.append("## 高频问题统计")
        for q in data.get("questions", []):
            lines.append(f"- {q.get('question', '')}: {q.get('count', 0)}次")

    content = ("\n".join(lines)) if lines else str(data)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)


# ============================================================
# Helper: dump KB data for LLM context
# ============================================================

def _get_all_kb_data(user_id=None) -> dict:
    """Fetch structured knowledge from the DB, optionally filtered by user_id."""
    db = SessionLocal()
    try:
        q = db.query(KnowledgeBase)
        if user_id:
            q = q.filter(KnowledgeBase.user_id == user_id)
        kbs = q.all()
        result = {}
        for kb in kbs:
            if kb.category == "main_kb_ids":
                continue
            try:
                result[kb.category] = json.loads(kb.data) if kb.data else {}
            except Exception:
                result[kb.category] = {}
        return result
    finally:
        db.close()


# ============================================================
# LLM parse: user text → structured preview
# ============================================================

CATEGORY_SCHEMA_HINTS = {
    "personal_info": '包含字段: name(姓名), age(年龄), city(城市), email, phone, github, personal_website(个人网站), work_years(工作年限), current_status(当前状态), target_position(意向岗位), expected_location(期望地点), start_date(到岗时间), salary_expectation(薪资期望), job_tags([]), self_intro(个人简介)',
    "education": 'education_list[] 每条含: school(学校), period(时间), degree(学历/专业)',
    "work_experience": 'work_list[] 每条含: company(公司), period(时间), position(职位), description(描述)',
    "projects": 'project_list[] 每条含: name(项目名), role(角色), tech_stack(技术栈), description(描述)',
    "skills": 'skill_sections[] 每条含: title(分类标题), items[] 每条含: name(技能名称), desc(技能描述)',
    "faq": 'faq_list[] 每条含: question(问题), answer(回答)',
}

SYSTEM_PARSE_PROMPT = """你是知识库管理助手的解析引擎。用户输入一段自然语言，你需要解析出他想怎么修改知识库。

知识库分类结构：
{cat_hints}

=== 当前知识库数据 ===
{current_kb_json}

=== 用户输入 ===
{user_text}

输出 JSON（纯JSON，不要markdown代码块，不要其他文字）：

{{
  "mode": "field" | "experience" | "global",
  "summary": "面向用户的概要描述，中文，如"将修改：姓名张三→江汉辉"",
  "faq_regenerate": false,
  "changes": [
    {{
      "category": "分类名",
      "description": "这条变更的描述，如"姓名：张三 → 江汉辉"",
      "new_data": {{ /* 该分类完整的更新后数据，保留所有字段 */ }}
    }}
  ]
}}

判断规则：
- mode=field：用户只改少量字段（1-2个），如"把名字改成江汉辉"
- mode=experience：用户提供了一段完整经历，涉及单个分类的某条记录替换/新增
- mode=global：用户提供了大量信息（≥3个分类有变动）

处理原则：
1. new_data 必须包含该分类所有字段，没提及的字段保留原值
2. 对 experience/global 模式的 work/project/education 条目，按公司名/项目名/学校名模糊匹配，匹配上则替换，匹配不上则新增到列表末尾
3. 对 faq 分类默认不修改，除非用户明确说要改FAQ
4. summary 要易懂，让用户一看就知道要改什么
"""


def _llm_parse(text: str, user_id: str = None) -> dict:
    """Call LLM to parse user intent into structured change instructions."""
    kb_data = _get_all_kb_data(user_id)
    cat_hints = "\n".join(f"- {k}: {v}" for k, v in CATEGORY_SCHEMA_HINTS.items())

    prompt = SYSTEM_PARSE_PROMPT.format(
        cat_hints=cat_hints,
        current_kb_json=json.dumps(kb_data, ensure_ascii=False, indent=2),
        user_text=text,
    )

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=text),
    ]
    response = ai_llm.invoke(messages)
    content = response.content.strip()

    # Strip markdown code block if present
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if "```" in content:
            content = content.rsplit("```", 1)[0]
    content = content.strip()

    return json.loads(content)


# ============================================================
# Apply changes to KB
# ============================================================

def _apply_change(db_session, category: str, new_data: dict, user_id=""):
    """Merge new_data into the existing KB record for this category."""
    q = db_session.query(KnowledgeBase).filter(KnowledgeBase.category == category)
    if user_id:
        q = q.filter(KnowledgeBase.user_id == user_id)
    kb = q.first()
    if not kb:
        kb = KnowledgeBase(category=category, data="{}", user_id=user_id or None)
        db_session.add(kb)
        db_session.flush()

    current = json.loads(kb.data) if isinstance(kb.data, str) else {}
    current.update(new_data)
    kb.data = json.dumps(current, ensure_ascii=False)


# ============================================================
# FAQ regeneration
# ============================================================

FAQ_REGENERATE_PROMPT = """你是一位资深HR。基于以下候选人的完整资料，为TA生成10个常见的面试问题及回答。

注意：保留以下10个问题类型，不要新增也不要删减题型，只需填入个性化的答案：

1. 离职原因是什么？
2. 期望薪资是多少？
3. 最快何时到岗？
4. 为什么选择我们公司？
5. 你的核心优势是什么？
6. 你对加班怎么看？
7. 你的职业规划是什么？
8. 你带过团队吗？
9. 为什么离开上一家公司？
10. 你做过哪些成功的AI产品？

=== 候选人资料 ===
{kb_summary}

输出 JSON 格式（纯JSON，不要markdown代码块）：
{{"faq_list": [
  {{"question": "离职原因是什么？", "answer": "..."}},
  ...
]}}

要求：
- 答案基于候选人真实的资料，不要编造
- 答案自然口语化，像真实面试回答
- 每条答案30-100字
- 薪资期望、到岗时间等信息从资料中提取
"""


def _regenerate_faq(user_id=None) -> str:
    """Regenerate FAQ answers based on current KB data, keeping question templates."""
    knowledge_data = _get_all_kb_data(user_id)
    # Build a compact summary from all categories
    summary_parts = []
    pi = knowledge_data.get("personal_info", {})
    if pi:
        summary_parts.append(f"个人信息：{pi.get('name','')}，{pi.get('age','')}岁，{pi.get('city','')}，{pi.get('phone','')}，{pi.get('email','')}")
        summary_parts.append(f"当前状态：{pi.get('current_status','')}，期望{pi.get('expected_location','')}，{pi.get('salary_expectation','')}，{pi.get('start_date','')}")
        summary_parts.append(f"目标岗位：{pi.get('target_position','')}")
        summary_parts.append(f"个人简介：{pi.get('self_intro','')}")

    work = knowledge_data.get("work_experience", {}).get("work_list", [])
    if work:
        summary_parts.append("\n工作经历：")
        for w in work:
            summary_parts.append(f"- {w.get('company','')} ({w.get('period','')}) {w.get('position','')}")

    projects = knowledge_data.get("projects", {}).get("project_list", [])
    if projects:
        summary_parts.append("\n项目经历：")
        for p in projects:
            summary_parts.append(f"- {p.get('name','')} ({p.get('role','')}) {p.get('description','')[:100]}")

    skills_data = knowledge_data.get("skills", {})
    skill_sections = skills_data.get("skill_sections", [])
    if skill_sections:
        summary_parts.append("\n技能：")
        for sec in skill_sections:
            items_str = "; ".join(f"{i.get('name','')}: {i.get('desc','')}" for i in sec.get("items", []))
            summary_parts.append(f"- {sec.get('title','')}: {items_str}")
    else:
        skill_groups = skills_data.get("skill_groups", {})
        if skill_groups:
            summary_parts.append(f"\n技能：{json.dumps(skill_groups, ensure_ascii=False)}")

    kb_summary = "\n".join(summary_parts)

    prompt = FAQ_REGENERATE_PROMPT.format(kb_summary=kb_summary)

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="请根据资料生成10条FAQ"),
    ]
    response = ai_llm.invoke(messages)
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if "```" in content:
            content = content.rsplit("```", 1)[0]
    content = content.strip()

    result = json.loads(content)
    faq_list = result.get("faq_list", [])
    return faq_list


def _apply_faq_update(faq_list: list, user_id=""):
    """Save regenerated FAQ to KB and sync."""
    db = SessionLocal()
    try:
        _apply_change(db, "faq", {"faq_list": faq_list}, user_id)
        _sync_category_to_md("faq", {"faq_list": faq_list}, user_id)
        rag_service.update_category("faq", db, user_id)
        db.commit()
    finally:
        db.close()


# ============================================================
# Public API
# ============================================================

def preview(text: str, user_id: str = None) -> dict:
    """
    Parse user text and return a preview of changes.
    Returns: {preview_id, mode, summary, faq_regenerate, changes, expires_in}
    """
    parsed = _llm_parse(text, user_id)
    preview_id = preview_storage.store(parsed)
    return {
        "preview_id": preview_id,
        "mode": parsed.get("mode", "field"),
        "summary": parsed.get("summary", ""),
        "faq_regenerate": parsed.get("faq_regenerate", False),
        "changes": parsed.get("changes", []),
        "expires_in": 600,
    }


def confirm(preview_id: str, user_id="") -> dict:
    """
    Apply changes from a preview.
    Returns: {success, message}
    """
    preview = preview_storage.get(preview_id)
    if not preview:
        return {"success": False, "message": "预览已过期或无效，请重新发起"}

    changes = preview.get("changes", [])
    db = SessionLocal()
    try:
        # 1. Merge all changes into DB first (so _sync_category_to_md reads complete data)
        for change in changes:
            cat = change.get("category", "")
            new_data = change.get("new_data", {})
            if not cat or not new_data:
                continue
            _apply_change(db, cat, new_data, user_id)

        # 2. Sync to MD — read merged data from DB, not raw LLM output
        for change in changes:
            cat = change.get("category", "")
            if cat:
                q = db.query(KnowledgeBase).filter(KnowledgeBase.category == cat)
                if user_id:
                    q = q.filter(KnowledgeBase.user_id == user_id)
                kb = q.first()
                if kb:
                    merged = json.loads(kb.data) if isinstance(kb.data, str) else {}
                    _sync_category_to_md(cat, merged, user_id)

        # 3. Update FAISS for affected categories
        for change in changes:
            cat = change.get("category", "")
            if cat:
                rag_service.update_category(cat, db, user_id)

        # 4. Regenerate FAQ if needed
        if preview.get("faq_regenerate"):
            faq_list = _regenerate_faq(user_id)
            _apply_change(db, "faq", {"faq_list": faq_list}, user_id)
            q = db.query(KnowledgeBase).filter(KnowledgeBase.category == "faq")
            if user_id:
                q = q.filter(KnowledgeBase.user_id == user_id)
            kb = q.first()
            if kb:
                merged = json.loads(kb.data) if isinstance(kb.data, str) else {}
                _sync_category_to_md("faq", merged, user_id)
            rag_service.update_category("faq", db, user_id)

        db.commit()
        preview_storage.invalidate(preview_id)

        _cleanup_stale_md_files(user_id)

        return {"success": True, "message": "知识库已更新完成"}
    except Exception as e:
        db.rollback()
        return {"success": False, "message": f"执行失败: {str(e)}"}
    finally:
        db.close()


def regenerate_faq(user_id="") -> dict:
    """Regenerate FAQ based on current knowledge base data."""
    try:
        faq_list = _regenerate_faq(user_id)
        _apply_faq_update(faq_list, user_id)
        return {"success": True, "message": f"FAQ已重新生成（{len(faq_list)}条）", "faq_list": faq_list}
    except Exception as e:
        return {"success": False, "message": f"FAQ再生失败: {str(e)}"}
