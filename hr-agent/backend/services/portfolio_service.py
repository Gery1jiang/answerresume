import json
import hashlib
from datetime import datetime, timezone, timedelta

_BEIJING_TZ = timezone(timedelta(hours=8))
from typing import Optional
from sqlalchemy.orm import Session as DBSession
from services.database import SessionLocal
from services.models import PortfolioConfig, PortfolioContent
from services.knowledge_manager import _get_all_kb_data
from services.ai_service import llm as ai_llm
from langchain_core.messages import HumanMessage, SystemMessage

_STYLE_MIGRATIONS = {
    "tech": "developer",
    "minimal": "editorial",
    "brand": "personal",
}

_NEW_BLOCK_ORDER = ["hero", "about", "experience", "projects", "contact"]
_OLD_BLOCK_IDS = {"skills", "education"}


class PortfolioService:
    def __init__(self, db: Optional[DBSession] = None):
        self.db = db or SessionLocal()
        self._condensed_cache: dict[str, str] = {}

    def _condense_text(self, text: str, item_type: str, item_name: str) -> str:
        if not text or len(text) < 100:
            return text
        cache_key = hashlib.md5(f"{item_type}:{item_name}:{text[:200]}".encode()).hexdigest()
        if cache_key in self._condensed_cache:
            return self._condensed_cache[cache_key]
        prompt = f"""原始描述是关于{item_type}「{item_name}」的详细内容。请提炼出 3-4 条核心摘要要点，每条用 <li> 包裹，整体用 <ul> 包裹。

规则：
1. 每条 15-40 字，突出量化成果和关键事实
2. 去掉背景描述和过程细节
3. 直接输出 HTML，不要加标题或多余文字
4. 整体控制在 150 字以内

示例格式：
<ul>
<li>第一条要点</li>
<li>第二条要点</li>
</ul>

原始描述：
{text}"""
        try:
            msg = [SystemMessage(content="你是个人主页文案优化助手，严格按示例格式输出。"), HumanMessage(content=prompt)]
            resp = ai_llm.bind(timeout=20).invoke(msg)
            result = resp.content.strip()
            if "<li>" not in result:
                lines = [l.strip().lstrip("-*") for l in result.split("\n") if l.strip()]
                if len(lines) >= 2:
                    items = "".join(f"<li>{l}</li>" for l in lines[:4])
                    result = f"<ul>{items}</ul>"
                else:
                    result = text
            self._condensed_cache[cache_key] = result
            return result
        except Exception:
            return text

    def _migrate_config(self, config):
        dirty = False
        if config.style in _STYLE_MIGRATIONS:
            config.style = _STYLE_MIGRATIONS[config.style]
            dirty = True
        try:
            order = json.loads(config.blocks_order)
            new_order = [b for b in order if b not in _OLD_BLOCK_IDS]
            if len(new_order) != len(order):
                config.blocks_order = json.dumps(new_order)
                dirty = True
        except (json.JSONDecodeError, TypeError):
            pass
        if dirty:
            self.db.commit()

    def get_config(self, user_id=""):
        config = self.db.query(PortfolioConfig).filter(PortfolioConfig.user_id == user_id).first()
        if not config:
            config = PortfolioConfig(user_id=user_id)
            self.db.add(config)
            self.db.commit()
            self.db.refresh(config)
        else:
            self._migrate_config(config)
        return {
            "style": config.style,
            "blocks_order": json.loads(config.blocks_order),
            "blocks_hidden": json.loads(config.blocks_hidden),
            "contact_enabled": json.loads(config.contact_enabled),
            "chat_enabled": config.chat_enabled,
            "chat_position": config.chat_position,
            "portfolio_show": config.portfolio_show,
        }

    def save_config(self, data, user_id=""):
        config = self.db.query(PortfolioConfig).filter(PortfolioConfig.user_id == user_id).first()
        if not config:
            config = PortfolioConfig(user_id=user_id)
            self.db.add(config)
        if "style" in data:
            config.style = data["style"]
        if "blocks_order" in data:
            config.blocks_order = json.dumps(data["blocks_order"])
        if "blocks_hidden" in data:
            config.blocks_hidden = json.dumps(data["blocks_hidden"])
        if "contact_enabled" in data:
            config.contact_enabled = json.dumps(data["contact_enabled"])
        if "chat_enabled" in data:
            config.chat_enabled = data["chat_enabled"]
        if "portfolio_show" in data:
            config.portfolio_show = data["portfolio_show"]
        if "chat_position" in data:
            config.chat_position = data["chat_position"]
        self.db.commit()
        return self.get_config(user_id)

    def _transform_skills(self, data: dict):
        raw_skills = data.get("skills", {})
        if not raw_skills:
            return

        # If only skill_sections exists (from rebuild cache), reconstruct skill_groups
        if "skill_sections" in raw_skills and "skill_groups" not in raw_skills:
            skill_groups = {}
            for section in raw_skills["skill_sections"]:
                title = section.get("title", "")
                items = section.get("items", [])
                names = [item.get("name", "") for item in items if item.get("name")]
                if names:
                    skill_groups[title] = names
            if skill_groups:
                raw_skills["skill_groups"] = skill_groups
                data["skills"] = raw_skills
            return

        # Convert skill_groups dict format to skill_sections (keep both)
        if "skill_groups" in raw_skills and isinstance(raw_skills["skill_groups"], dict):
            sections = []
            for cat, tags in raw_skills["skill_groups"].items():
                items = [{"name": t, "desc": ""} for t in tags if isinstance(t, str)]
                if items:
                    sections.append({"title": cat, "items": items})
            raw_skills["skill_sections"] = sections
            data["skills"] = raw_skills
        else:
            # Legacy hard_skills/soft_skills/tool_skills format
            cat_labels = {"hard_skills": "硬技能", "soft_skills": "软技能", "tool_skills": "工具平台"}
            sections = []
            skill_groups = {}
            for eng_key, cn_label in cat_labels.items():
                items = raw_skills.get(eng_key, [])
                if items:
                    names = [t for t in items if isinstance(t, str)]
                    sections.append({"title": cn_label, "items": [{"name": n, "desc": ""} for n in names]})
                    skill_groups[cn_label] = names
            if sections:
                raw_skills["skill_sections"] = sections
                raw_skills["skill_groups"] = skill_groups
                data["skills"] = raw_skills

    def get_knowledge_data(self, user_id=""):
        """Return knowledge data: use cached built content if available, else source data."""
        content = self.db.query(PortfolioContent).filter(PortfolioContent.user_id == user_id).first()
        if content and content.content_json and content.content_json != "{}":
            return json.loads(content.content_json)
        data = _get_all_kb_data(user_id=user_id)
        self._transform_skills(data)
        return data

    def rebuild(self, user_id="") -> dict:
        """Read source knowledge, condense with LLM once, store in DB."""
        data = _get_all_kb_data(user_id=user_id)
        self._transform_skills(data)
        for w in data.get("work_experience", {}).get("work_list", []):
            if w.get("description"):
                w["description"] = self._condense_text(w["description"], "工作经历", w.get("company", ""))
        for p in data.get("projects", {}).get("project_list", []):
            if p.get("description"):
                p["description"] = self._condense_text(p["description"], "项目经历", p.get("name", ""))
        content = self.db.query(PortfolioContent).filter(PortfolioContent.user_id == user_id).first()
        if not content:
            content = PortfolioContent(user_id=user_id)
            self.db.add(content)
        content.content_json = json.dumps(data, ensure_ascii=False)
        content.built_at = datetime.now(_BEIJING_TZ)
        self.db.commit()
        return data

    def get_build_status(self, user_id="") -> dict:
        content = self.db.query(PortfolioContent).filter(PortfolioContent.user_id == user_id).first()
        if content and content.content_json and content.content_json != "{}":
            if content.built_at:
                # 存的是北京时间，但 SQLite 丢了时区信息，手动补上
                bj_time = content.built_at.replace(tzinfo=_BEIJING_TZ)
                return {"built": True, "built_at": bj_time.isoformat()}
            return {"built": True, "built_at": None}
        return {"built": False, "built_at": None}


portfolio_service = PortfolioService()
