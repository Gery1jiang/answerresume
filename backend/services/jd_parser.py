"""Parse JD text into structured fields using LLM."""

import json
import re
from langchain_core.messages import HumanMessage, SystemMessage
from services.ai_service import llm as ai_llm

PARSE_PROMPT = """你是一个招聘专家，从岗位描述中提取结构化信息。

=== JD 文本 ===
{jd_text}

提取以下字段，输出纯 JSON（不要 markdown 代码块，不要其他文字）：
{{
  "education": "学历要求，如'本科及以上'、'硕士'、'不限'，未提及则null",
  "experience_years": "经验年限数值（仅数字），如3，未提及则null",
  "skills": ["从JD中提取的关键技能列表，每项一个字符串"],
  "responsibilities": ["从JD中提取的主要职责列表，每项一句话"],
  "industry": "所属行业/领域，如'互联网'、'金融'、'制造业'，不确定则null",
  "salary_min": "薪资范围下限（万/月），如2.0，未提及则null",
  "salary_max": "薪资范围上限（万/月），如3.5，未提及则null",
  "location": "工作地点，如'杭州'，未提及则null"
}}

要求：
- skills 提取硬技能（编程语言、框架、工具、平台），不包括软技能
- responsibilities 提取核心职责，每条5-20字
- industry 根据公司业务和岗位内容推断
"""


def parse_jd(jd_text: str) -> dict:
    """Extract structured fields from JD text using LLM."""
    if not jd_text or not jd_text.strip():
        return {}

    prompt = PARSE_PROMPT.format(jd_text=jd_text[:2000])

    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content="提取结构化信息"),
    ]
    response = ai_llm.invoke(messages)
    content = response.content.strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[1]
        if "```" in content:
            content = content.rsplit("```", 1)[0]
    content = content.strip()

    try:
        result = json.loads(content)
        for k in ["education", "industry", "location"]:
            if result.get(k) is None:
                result[k] = ""
        for k in ["experience_years", "salary_min", "salary_max"]:
            if result.get(k) is None:
                result[k] = 0
            else:
                try:
                    result[k] = int(float(result[k])) if k == "experience_years" else float(result[k])
                except (ValueError, TypeError):
                    result[k] = 0
        if not isinstance(result.get("skills"), list):
            result["skills"] = []
        if not isinstance(result.get("responsibilities"), list):
            result["responsibilities"] = []
        return result
    except (json.JSONDecodeError, KeyError) as e:
        print(f"[jd_parser] LLM 返回解析失败: {e}, raw: {content[:200]}")
        return {}


def parse_salary_range(salary_str: str) -> tuple:
    """Parse salary string like '2-4万·14薪' into (min, max) in 万/月."""
    if not salary_str:
        return (0, 0)
    s = salary_str.replace("·", "-").replace("~", "-").replace("—", "-").replace("～", "-").replace("．", ".")
    # Match patterns like "2-4万" or "1.5-2.8万" or "8千-1.2万"
    m = re.search(r'([\d.]+)\s*[-~]\s*([\d.]+)\s*万', s)
    if m:
        return (float(m.group(1)), float(m.group(2)))
    m = re.search(r'([\d.]+)\s*[-~]\s*([\d.]+)\s*千', s)
    if m:
        return (round(float(m.group(1)) / 10, 2), round(float(m.group(2)) / 10, 2))
    m = re.search(r'([\d.]+)\s*万', s)
    if m:
        v = float(m.group(1))
        return (v, v)
    m = re.search(r'([\d.]+)\s*千', s)
    if m:
        v = round(float(m.group(1)) / 10, 2)
        return (v, v)
    return (0, 0)


def parse_experience_years(text: str) -> int:
    """Extract experience years from JD text as fallback."""
    patterns = [
        (r'(\d+)\s*年\s*以上', lambda m: int(m.group(1))),
        (r'(\d+)[-~]\s*(\d+)\s*年', lambda m: int(m.group(1))),
    ]
    for pattern, fn in patterns:
        m = re.search(pattern, text)
        if m:
            return fn(m)
    return 0
