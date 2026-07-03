"""JD matching against knowledge base — 8 dimensions, Block A (硬性) + Block B (软性)."""

import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from services.ai_service import llm as ai_llm
from services.jd_parser import parse_jd, parse_salary_range, parse_experience_years
from services.rag_service import rag_service
from services.knowledge_manager import _get_all_kb_data


# ── Education level hierarchy ──
EDU_LEVELS = {
    "博士": 5, "博士及以上": 5, "博士研究生": 5,
    "硕士": 4, "硕士及以上": 4, "硕士研究生": 4,
    "本科": 3, "本科及以上": 3, "本科及本科以上": 3,
    "大专": 2, "大专及以上": 2, "专科": 2,
    "不限": 1, "无": 1, "": 1,
}

EXPERIENCE_CATEGORIES = ["工作经历", "03_工作经历", "work_experience",
                         "项目经历", "04_项目经历", "projects"]


def _edu_level(requirement: str) -> int:
    """Convert education requirement string to numeric level."""
    for kw, lv in sorted(EDU_LEVELS.items(), key=lambda x: -x[1]):
        if kw in requirement:
            return lv
    return 1


def _match_education(jd_parsed: dict, kb: dict) -> dict:
    """学历匹配 (max 10)."""
    jd_edu = jd_parsed.get("education", "")
    edu_list = kb.get("education", {}).get("education_list", [])
    if not jd_edu:
        return {"score": 10, "max": 10, "detail": "JD 未明确学历要求，默认满分"}

    jd_lv = _edu_level(jd_edu)
    candidate_lv = 1
    for edu in edu_list:
        deg = edu.get("degree", "")
        if "博士" in deg:
            candidate_lv = max(candidate_lv, 5)
        elif "硕士" in deg:
            candidate_lv = max(candidate_lv, 4)
        elif "本科" in deg or "学士" in deg:
            candidate_lv = max(candidate_lv, 3)
        elif "大专" in deg or "专科" in deg:
            candidate_lv = max(candidate_lv, 2)

    diff = candidate_lv - jd_lv
    if diff >= 0:
        return {"score": 10, "max": 10, "detail": f"学历满足要求 (JD:{jd_edu})"}
    elif diff == -1:
        return {"score": 5, "max": 10, "detail": f"学历略低于要求 (JD:{jd_edu})"}
    else:
        return {"score": 0, "max": 10, "detail": f"学历不达标 (JD:{jd_edu})"}


def _match_experience(jd_parsed: dict, kb: dict, jd_text: str) -> dict:
    """经验年限匹配 (max 15)."""
    work_years_str = kb.get("personal_info", {}).get("work_years", 0)
    try:
        work_years = int(float(work_years_str))
    except (ValueError, TypeError):
        work_years = 0

    exp_years = jd_parsed.get("experience_years", 0) or parse_experience_years(jd_text)

    # Check crawler's pre-parsed experience_required field
    exp_req = jd_parsed.get("experience_required", "")
    if exp_req and any(kw in exp_req for kw in ["无需经验", "经验不限", "无经验", "应届"]):
        return {"score": 15, "max": 15, "detail": f"JD无经验要求，你{work_years}年经验完全满足"}

    # JD says no experience required → full score
    if exp_years == 0:
        if any(kw in jd_text for kw in ["无经验", "经验不限", "无工作", "应届毕业生", "欢迎应届"]):
            return {"score": 15, "max": 15, "detail": f"JD无经验要求，你{work_years}年经验完全满足"}
        return {"score": 7, "max": 15, "detail": "无法确定年限要求，取中值"}

    if work_years == 0:
        return {"score": 7, "max": 15, "detail": "无法确定年限要求，取中值"}

    ratio = work_years / exp_years
    if ratio >= 1.5:
        return {"score": 15, "max": 15, "detail": f"你{work_years}年经验，JD要求{exp_years}年，超出要求"}
    elif ratio >= 1.0:
        return {"score": 12, "max": 15, "detail": f"你{work_years}年经验，满足JD要求{exp_years}年"}
    elif ratio >= 0.7:
        return {"score": 8, "max": 15, "detail": f"你{work_years}年经验，接近JD要求{exp_years}年"}
    else:
        return {"score": 3, "max": 15, "detail": f"你{work_years}年经验，JD要求{exp_years}年，经验不足"}


def _match_skills(jd_parsed: dict, kb: dict) -> dict:
    """技能匹配 (max 15) — LLM 评估技能重叠."""
    jd_skills = jd_parsed.get("skills", [])
    if not jd_skills:
        return {"score": 7, "max": 15, "detail": "JD 未提取到技能要求，取中值",
                "matched": [], "missing": []}

    kb_skills = kb.get("skills", {})
    all_my_skills = []
    # Handle new skill_sections format: [{"title": "...", "items": [{"name": "...", ...}]}]
    sections = kb_skills.get("skill_sections", [])
    if sections and isinstance(sections, list):
        for sec in sections:
            for item in sec.get("items", []):
                name = item.get("name", "")
                if name:
                    all_my_skills.append(name.lower().strip())
    # Handle legacy dict format: {"硬技能": ["NLP", ...]} or {"hard_skills": [...]}
    else:
        for group_name, group_skills in kb_skills.items():
            if isinstance(group_skills, list):
                all_my_skills.extend(s.lower().strip() for s in group_skills if isinstance(s, str))

    prompt = f"""你是一名招聘专家。对比候选人的技能和岗位要求的技能，输出匹配结果。

候选人技能：{json.dumps(all_my_skills, ensure_ascii=False)}
岗位要求技能：{json.dumps(jd_skills, ensure_ascii=False)}

输出 JSON：
{{"matched": ["匹配上的技能列表"], "missing": ["JD要求但候选人不具备的技能"], "rate": 匹配率(0-1之间)}}

要求：
- matched 包含候选人技能中与 JD 技能直接匹配或相近的
- missing 包含 JD 要求但在候选人技能中明确找不到的
- rate = matched / (matched + missing)
- 纯JSON，不要markdown"""

    try:
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="评估技能匹配"),
        ]
        resp = ai_llm.invoke(messages)
        content = resp.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if "```" in content:
                content = content.rsplit("```", 1)[0]
        result = json.loads(content)
        rate = min(float(result.get("rate", 0)), 1.0)
        score = round(rate * 15)
        return {
            "score": score,
            "max": 15,
            "detail": f"JD要求{len(jd_skills)}项技能，匹配{len(result.get('matched', []))}项",
            "matched": result.get("matched", []),
            "missing": result.get("missing", []),
        }
    except Exception as e:
        # Fallback: simple keyword overlap
        jd_set = set(s.lower().strip() for s in jd_skills if isinstance(s, str))
        my_set = set(all_my_skills)
        matched = jd_set & my_set
        rate = len(matched) / max(len(jd_set), 1)
        score = round(rate * 15)
        return {
            "score": score,
            "max": 15,
            "detail": f"JD要求{len(jd_set)}项技能，匹配{len(matched)}项",
            "matched": list(matched)[:10],
            "missing": list(jd_set - my_set)[:10],
        }


def _match_location(jd_parsed: dict, kb: dict, job_city: str = "", work_address: str = "") -> dict:
    """地点匹配 (max 5)."""
    jd_location = jd_parsed.get("location", "") or job_city
    expected = kb.get("personal_info", {}).get("expected_location", "")

    if not jd_location or not expected:
        # 卡片城市为空时，尝试从工作地址里找期望城市
        if expected and work_address and expected in work_address:
            return {"score": 5, "max": 5, "detail": f"工作地址含【{expected}】，符合期望"}
        return {"score": 2, "max": 5, "detail": "无法确定地点要求，取中值"}

    if jd_location in expected or expected in jd_location:
        return {"score": 5, "max": 5, "detail": f"工作地{jd_location}符合期望{expected}"}

    # Check if same city (e.g. "杭州·西湖区" contains "杭州")
    jd_city = jd_location.split("·")[0].strip()
    exp_city = expected.split("·")[0].strip()
    if jd_city == exp_city:
        return {"score": 5, "max": 5, "detail": f"同城:{jd_city}"}
    else:
        return {"score": 0, "max": 5, "detail": f"工作地{jd_location}，期望{expected}"}


def _match_salary(jd_parsed: dict, kb: dict, salary_str: str = "") -> dict:
    """薪资匹配 (max 5)."""
    jd_min = jd_parsed.get("salary_min", 0)
    jd_max = jd_parsed.get("salary_max", 0)
    if jd_min == 0 and jd_max == 0 and salary_str:
        jd_min, jd_max = parse_salary_range(salary_str)

    expected_str = kb.get("personal_info", {}).get("salary_expectation", "")
    # Parse "30K-45K" → 3.0-4.5 万/月  (K means thousands/month in Chinese context)
    salary_normalized = expected_str.upper().replace("K", "")
    expected = re.findall(r'[\d.]+', salary_normalized)
    exp_num = float(expected[0]) / 10 if expected else 0

    if jd_max == 0 or exp_num == 0:
        return {"score": 2, "max": 5, "detail": "薪资信息不足，取中值"}

    if jd_max >= exp_num:
        return {"score": 5, "max": 5, "detail": f"JD最高{jd_max}万/月 ≥ 期望{exp_num}万"}
    elif jd_max >= exp_num * 0.8:
        return {"score": 3, "max": 5, "detail": f"JD最高{jd_max}万/月，略低于期望{exp_num}万"}
    else:
        return {"score": 1, "max": 5, "detail": f"JD最高{jd_max}万/月，远低于期望{exp_num}万"}


def _match_responsibility(jd_parsed: dict, kb: dict, jd_text: str, user_id: str = "") -> dict:
    """职责相关度 (max 25) — RAG + LLM 综合评估."""
    relevant_docs = rag_service.retrieve_relevant(jd_text, k=8, user_id=user_id or None)
    exp_docs = [d for d, s in relevant_docs if s < 1.5 and
                any(c in d.metadata.get("category", "") for c in EXPERIENCE_CATEGORIES)]

    if not exp_docs:
        return {"score": 10, "max": 25, "detail": "未找到直接相关的经历匹配"}

    matched_excerpts = [d.page_content[:100].strip() for d in exp_docs[:4]]

    prompt = f"""你是一名招聘专家。评估候选人的工作/项目经历与岗位职责的匹配程度。

岗位关键职责：
{json.dumps(jd_parsed.get('responsibilities', []), ensure_ascii=False)}

候选人的相关经历节选：
{json.dumps(matched_excerpts, ensure_ascii=False)}

输出 0-100 的匹配分和原因，格式：
{{"score": 数值0-100, "reason": "一句话原因"}}
纯JSON。"""

    try:
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="评估职责匹配"),
        ]
        resp = ai_llm.invoke(messages)
        content = resp.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if "```" in content:
                content = content.rsplit("```", 1)[0]
        result = json.loads(content)
        score = round(min(float(result.get("score", 50)), 100) / 100 * 25)
        return {"score": score, "max": 25, "detail": result.get("reason", matched_excerpts[0][:60])}
    except Exception:
        score = min(len(exp_docs) * 6, 25)
        return {"score": score, "max": 25, "detail": matched_excerpts[0][:60] if matched_excerpts else "RAG 匹配完成"}


def _match_industry(jd_parsed: dict, kb: dict) -> dict:
    """领域/行业匹配 (max 15)."""
    jd_industry = jd_parsed.get("industry", "")
    if not jd_industry:
        return {"score": 7, "max": 15, "detail": "JD 未明确行业，取中值"}

    # Infer candidate's industry from work experience and project descriptions
    work_list = kb.get("work_experience", {}).get("work_list", [])
    project_list = kb.get("projects", {}).get("project_list", [])
    kb_text = " ".join(
        [w.get("description", "") for w in work_list] +
        [p.get("description", "") + p.get("tech_stack", "") for p in project_list]
    )

    jd_lower = jd_industry.lower()
    if jd_lower in kb_text.lower():
        return {"score": 15, "max": 15, "detail": f"有{jd_industry}领域经验"}

    # LLM evaluation
    prompt = f"""候选人工作经历描述：{kb_text[:500]}
岗位行业/领域：{jd_industry}

判断候选人是否有该领域的经验。只需回答 YES/NO 和一句话原因，格式：{{"match": true/false, "reason": "..."}}
纯JSON。"""

    try:
        messages = [
            SystemMessage(content=prompt),
            HumanMessage(content="评估行业匹配"),
        ]
        resp = ai_llm.invoke(messages)
        content = resp.content.strip()
        if content.startswith("```"):
            content = content.split("\n", 1)[1]
            if "```" in content:
                content = content.rsplit("```", 1)[0]
        result = json.loads(content)
        if result.get("match"):
            return {"score": 15, "max": 15, "detail": result.get("reason", "领域匹配")}
        else:
            return {"score": 5, "max": 15, "detail": result.get("reason", "领域不匹配")}
    except Exception:
        return {"score": 7, "max": 15, "detail": f"JD行业{jd_industry}，不确定匹配程度"}


def _match_complexity(jd_parsed: dict, kb: dict) -> dict:
    """项目复杂度匹配 (max 10)."""
    project_list = kb.get("projects", {}).get("project_list", [])
    jd_skills = jd_parsed.get("skills", [])

    if not project_list or not jd_skills:
        return {"score": 5, "max": 10, "detail": "信息不足，取中值"}

    # Evaluate based on tech stack depth
    project_techs = set()
    for p in project_list:
        ts = p.get("tech_stack", "")
        if ts:
            for t in re.split(r'[,，/、\s]+', ts):
                if t.strip():
                    project_techs.add(t.strip().lower())

    jd_techs = set(s.lower() for s in jd_skills)
    overlap = project_techs & jd_techs

    if len(overlap) >= 5:
        return {"score": 10, "max": 10, "detail": f"技术栈高度匹配({len(overlap)}项)"}
    elif len(overlap) >= 2:
        return {"score": 7, "max": 10, "detail": f"技术栈部分匹配({len(overlap)}项)"}
    else:
        return {"score": 3, "max": 10, "detail": f"技术栈匹配较少({len(overlap)}项)"}


def match_jd(jd_text: str, salary_str: str = "", city_str: str = "",
             crawler_parsed: dict = None, user_id: str = "", work_address: str = "") -> dict:
    """
    8-dimension matching against knowledge base.
    Block A (硬性, 50pts) + Block B (软性, 50pts).
    crawler_parsed: pre-parsed fields from crawler (education, experience_required)
    """
    if not jd_text or not jd_text.strip():
        return {"score": 0, "dimensions": {}, "summary": "JD 文本为空",
                "jd_parsed": {}}

    kb = _get_all_kb_data(user_id=user_id or None)
    jd_parsed = parse_jd(jd_text)
    # Merge crawler's pre-parsed data (takes priority for education/experience)
    if crawler_parsed:
        if crawler_parsed.get("education"):
            jd_parsed["education"] = crawler_parsed["education"]
        if crawler_parsed.get("experience_required"):
            jd_parsed["experience_required"] = crawler_parsed["experience_required"]

    # Block A: 硬性门槛 (50)
    edu = _match_education(jd_parsed, kb)
    exp = _match_experience(jd_parsed, kb, jd_text)
    skill = _match_skills(jd_parsed, kb)
    loc = _match_location(jd_parsed, kb, city_str, work_address)
    sal = _match_salary(jd_parsed, kb, salary_str)

    # Block B: 软性匹配 (50)
    resp = _match_responsibility(jd_parsed, kb, jd_text, user_id=user_id)
    ind = _match_industry(jd_parsed, kb)
    comp = _match_complexity(jd_parsed, kb)

    dimensions = {
        "education": edu,
        "experience": exp,
        "skills": skill,
        "location": loc,
        "salary": sal,
        "responsibility": resp,
        "industry": ind,
        "complexity": comp,
    }

    total = sum(d["score"] for d in dimensions.values())

    matched_skills = skill.get("matched", [])
    missing_skills = skill.get("missing", [])

    if total >= 80:
        summary = f"匹配度较高（{total}%），岗位契合度好"
    elif total >= 60:
        summary = f"匹配度中等（{total}%），部分维度需要补充"
    elif total >= 40:
        summary = f"匹配度一般（{total}%），建议查看缺失项后决定"
    else:
        summary = f"匹配度较低（{total}%），岗位方向可能不太匹配"

    return {
        "score": total,
        "dimensions": dimensions,
        "summary": summary,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "jd_parsed": jd_parsed,
    }
