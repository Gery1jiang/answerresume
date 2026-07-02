import asyncio
import json
import httpx
from config import settings, get_provider_base_url
from services.prompt_manager import prompt_manager

_INTENT_DETECT_TIMEOUT = 15
_INTENT_MAX_RETRIES = 2
_INTENT_RETRY_DELAY = 1.0

INTENT_CATEGORIES = {
    "chitchat": "寒暄问候，没有实质求职提问",
    "probing_general": "一般性了解候选人，问基础信息（经历、技能、项目等），没有明显兴趣信号",
    "probing_details": "深入了解候选人，追问具体细节（项目细节、技术方案、数据等），表现出兴趣",
    "salary_discussion": "讨论薪资、待遇、期望薪酬",
    "interview_interest": "表达面试意向（想约时间聊聊、进一步了解），但未明确安排具体面试",
    "ready_to_schedule": "明确要求邀约面试、确认面试时间、讨论具体邀约安排",
}

async def classify_intent(conversation_history: list[dict]) -> dict:
    """
    Classify the visitor's latest intent based on conversation context.

    Args:
        conversation_history: list of {"role": "user"/"assistant", "content": str}

    Returns:
        dict with:
          - intent: str - one of the INTENT_CATEGORIES keys
          - confidence: float - 0.0 to 1.0
          - label: str - human readable label
          - should_suggest_booking: bool - whether to show booking card
    """
    recent = conversation_history[-8:] if len(conversation_history) > 8 else conversation_history
    context = "\n".join(
        [f"{'HR' if m['role'] == 'user' else 'AI'}: {m['content'][:300]}" for m in recent]
    )

    categories_desc = "\n".join([f"- {k}: {v}" for k, v in INTENT_CATEGORIES.items()])

    prompt_template = prompt_manager.get("classify_intent_prompt", "")
    if not prompt_template:
        return {"intent": "probing_general", "confidence": 0.5, "label": "一般了解", "should_suggest_booking": False, "suggested_time": None}
    prompt = prompt_template.format(categories_desc=categories_desc, context=context)

    _vcfg = None
    last_error = None
    for attempt in range(_INTENT_MAX_RETRIES):
        try:
            if _vcfg is None:
                from config import get_visitor_llm_config
                _vcfg = get_visitor_llm_config()
            async with httpx.AsyncClient(timeout=_INTENT_DETECT_TIMEOUT) as client:
                resp = await client.post(
                    f"{_vcfg['api_base']}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {_vcfg['api_key']}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": _vcfg["model"],
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.1,
                        "max_tokens": 200,
                    },
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"].strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                result = json.loads(content)
                intent = result.get("intent", "probing_general")
                confidence = float(result.get("confidence", 0.5))
                suggested_time = result.get("suggested_time") or None
                should_suggest = intent in ("interview_interest", "ready_to_schedule") and confidence >= 0.4
                return {
                    "intent": intent,
                    "confidence": confidence,
                    "label": INTENT_CATEGORIES.get(intent, "一般了解"),
                    "should_suggest_booking": should_suggest,
                    "suggested_time": suggested_time,
                }
        except (httpx.TimeoutException, httpx.ConnectError, httpx.RemoteProtocolError,
                httpx.HTTPStatusError) as e:
            last_error = e
            if attempt < _INTENT_MAX_RETRIES - 1:
                print(f"Intent detection attempt {attempt + 1} transient error, retrying: {e}")
                await asyncio.sleep(_INTENT_RETRY_DELAY)
            else:
                print(f"Intent detection failed after {_INTENT_MAX_RETRIES} attempts: {e}")
        except Exception as e:
            print(f"Intent detection failed (non-transient): {e}")
            break

    return {
        "intent": "probing_general",
        "confidence": 0.0,
        "label": "一般了解",
        "should_suggest_booking": False,
        "suggested_time": None,
    }


KB_INTENT_CATEGORIES = {
    "greeting": "打招呼、寒暄、自我介绍，没有实质性提问",
    "personal_info": "问个人基本信息（姓名、年龄、所在地、手机号、邮箱、GitHub）",
    "education": "问教育背景（学历、学校、专业、毕业时间）",
    "work_experience": "问工作经历、在哪家公司、在职时间、职位（不含离职原因）",
    "project_experience": "问项目经验、具体项目细节、技术方案",
    "skills": "问技术栈、专业技能、擅长什么",
    "faq": "问标准面试问题（离职原因、优缺点、职业规划、加班看法、团队合作、核心优势等）",
    "salary": "问薪资、待遇、期望薪酬",
    "company_match": "问与某公司的匹配度、你了解某公司吗、你和某公司契合吗",
    "schedule_interview": "邀约面试、确认面试时间、安排面试",
    "other": "其他不归类的提问",
}

# 类别 → KB 文件名映射（FAISS metadata category）
CATEGORY_KB_FILE_MAP = {
    "personal_info": "01_个人信息",
    "education": "02_教育背景",
    "work_experience": "03_工作经历",
    "project_experience": "04_项目经历",
    "skills": "05_专业技能栈",
    "faq": "06_HR高频问答库",
}


_KB_KEYWORD_RULES: list[tuple[list[str], str]] = [
    (["你好", "您好", "hi", "hello", "在吗", "在不在", "你是谁", "你叫什么", "幸会", "认识你"], "greeting"),
    (["电话", "手机", "邮箱", "年龄", "多大", "哪里人", "姓名", "名字", "GitHub", "所在地", "住哪", "born", "出生"], "personal_info"),
    (["毕业", "学历", "学校", "专业", "学位", "教育背景", "大学", "硕士", "博士", "本科", "研究生", "就读", "留学"], "education"),
    (["工作经历", "在哪家公司", "在职时间", "做过什么工作", "上一份", "前公司", "工作经验", "工作年限", "工龄", "从业", "任职", "就职", "跳槽", "离职"], "work_experience"),
    (["项目", "技术方案", "负责什么", "你做过什么", "项目经验", "做过哪些", "项目案例", "典型案例", "交付", "开发过", "参与.*项目", "负责.*项目"], "project_experience"),
    (["技能", "技术栈", "编程语言", "框架", "擅长", "会什么", "精通", "熟悉什么", "会用", "掌握", "技术能力", "开发语言", "工具", "平台"], "skills"),
    (["薪资", "待遇", "薪酬", "工资", "期望", "多少钱", "月薪", "年薪", "薪水", "收入", "offer", "package", "总包"], "salary"),
    (["面试", "约", "安排", "什么时候方便", "有空吗", "聊聊", "见面", "沟通一下", "进一步交流", "邀请", "邀约"], "schedule_interview"),
    (["离职原因", "优缺点", "职业规划", "加班", "团队合作", "核心优势", "劣势", "weakness", "strength", "特长", "不足", "缺点", "优势"], "faq"),
    (["匹配度", "匹配吗", "了解.*公司", "契合", "适合.*公司", "文化", "价值观"], "company_match"),
]


def _fast_kb_classify(query: str) -> str | None:
    """快速关键词匹配，命中后直接返回意图，无需调 LLM。"""
    q = query.lower().strip()
    for keywords, intent in _KB_KEYWORD_RULES:
        for kw in keywords:
            if kw.lower() in q:
                return intent
    return None


async def classify_kb_intent(query: str) -> str:
    """判断用户单条提问属于哪个 KB 意图类别，返回类别 key 字符串。"""
    # 快速路径：关键词匹配
    fast = _fast_kb_classify(query)
    if fast is not None:
        return fast

    from config import get_visitor_llm_config
    _vcfg = get_visitor_llm_config()

    categories_desc = "\n".join([f"- {k}: {v}" for k, v in KB_INTENT_CATEGORIES.items()])

    prompt_template = prompt_manager.get("classify_kb_intent_prompt", "")
    if not prompt_template:
        return "other"
    prompt = prompt_template.format(categories_desc=categories_desc, query=query)

    for attempt in range(_INTENT_MAX_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=_INTENT_DETECT_TIMEOUT) as client:
                resp = await client.post(
                    f"{_vcfg['api_base']}/chat/completions",
                    headers={"Authorization": f"Bearer {_vcfg['api_key']}", "Content-Type": "application/json"},
                    json={"model": _vcfg["model"], "messages": [{"role": "user", "content": prompt}], "temperature": 0.1, "max_tokens": 100},
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"].strip()
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                result = json.loads(content)
                intent = result.get("intent", "other")
                return intent if intent in KB_INTENT_CATEGORIES else "other"
        except Exception as e:
            if attempt < _INTENT_MAX_RETRIES - 1:
                await asyncio.sleep(_INTENT_RETRY_DELAY)
            else:
                print(f"KB intent classification failed: {e}")
                return "other"
    return "other"
