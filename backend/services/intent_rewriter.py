"""Unified intent rewriter — single entry for all tool intent resolution.

Returns list[dict] (tool calls) or [] (no tool → LangGraph).
Tiers: keyword → embedding → LLM. Each tier can return 0, 1, or N tools.
"""

import re

# ── File marker detection ──────────────────────────────────

_FILE_MARKER = re.compile(r"\[文件:\s*(\S+\.\w+)\]")

def _extract_filenames(text: str) -> list[str]:
    return _FILE_MARKER.findall(text)

# ── Parameter extraction helpers ────────────────────────────

_CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉",
    "南京", "苏州", "西安", "重庆", "长沙", "天津", "郑州",
    "东莞", "青岛", "厦门", "宁波", "大连", "合肥", "佛山",
    "福州", "昆明", "贵阳", "南宁", "哈尔滨", "长春",
]

_PLATFORMS: dict[str, list[str]] = {
    "51job": ["51job", "前程无忧", "51"],
    "boss": ["boss", "Boss", "BOSS", "直聘", "BOSS直聘"],
    "zhaopin": ["zhaopin", "智联", "智联招聘"],
}

_CITY_PATTERN = re.compile("|".join(_CITIES))


def _extract_params(text: str) -> dict:
    params: dict = {}
    city_m = _CITY_PATTERN.search(text)
    if city_m:
        params["city"] = city_m.group(0)
    for platform, aliases in _PLATFORMS.items():
        for alias in aliases:
            if alias in text:
                params["platform"] = platform
                break
    # keywords: clean text of city/platform/common words
    cleanup = re.compile(
        r"抓[取]?|爬[取]?|搜索|搜|找|"
        r"匹配|评分|评估|分析|"
        r"新增|创建|添加|录入|面试|记录|"
        r"生成|报告|解析|文件|简历|"
        r"查询|数据|系统|知识库|修改|重建|向量|"
        r"识别|图片|OCR|提取|文字|翻译|"
        r"会话|统计|在线|信息|"
        r"查一下|并|然后|再|接着|之后|且|还有|同时|"
        r"帮[我]?|请|的|一下|最新|一个|给[我]?|"
        r"这个|那个|这些|那些|"
        r"上|下|里|在"
    )
    for city in _CITIES:
        text = text.replace(city, "")
    kw = cleanup.sub("", text).strip()
    kw = re.sub(r"\s+", "", kw)
    if kw:
        params["keywords"] = kw
    return params


# ── Tool verb patterns (shared: keyword + LLM both need these) ──

_TOOL_VERB_PATTERNS: dict[str, re.Pattern] = {
    name: re.compile(pat)
    for name, pat in [
        ("crawl_1", r'抓(?:取)?'),
        ("crawl_2", r'爬(?:取)?'),
        ("search_1", r'搜索'),
        ("search_2", r'搜(?!索)'),
        ("search_3", r'找'),
        ("match", r'匹配'),
        ("score", r'评分'),
        ("evaluate", r'评估'),
        ("analyze", r'分析'),
        ("generate", r'生成'),
        ("make", r'做(?!到|完|好|成|不)'),
        ("create", r'制作'),
        ("write", r'写'),
        ("parse", r'解析'),
        ("read", r'读取'),
        ("extract", r'提取'),
        ("open", r'打开'),
        ("new", r'新增'),
        ("add", r'创建|添加'),
        ("modify", r'修改'),
        ("update", r'更新'),
        ("edit", r'编辑'),
        ("rebuild", r'重建'),
        ("refresh", r'刷新'),
        ("recognize", r'识别'),
        ("query", r'查询|查看'),
        ("find", r'(?<!新)(?<!搜 )查(?!询|看|找|阅|问|过|明|封|收|办|处|核)'),
    ]
}

_TOOL_CONJUNCTIONS = re.compile(r'(?:并|且|同时|然后|还要|并且|以及|再)')


def _is_compound(text: str) -> bool:
    """True if text clearly asks for multiple tools."""
    if _TOOL_CONJUNCTIONS.search(text):
        return True
    found = set()
    for name, pat in _TOOL_VERB_PATTERNS.items():
        if pat.search(text):
            found.add(name)
    return len(found) >= 2


def _fill_params(actions: list[dict], raw_text: str) -> list[dict]:
    """Fill missing params from raw text for keyword/embedding-matched tools."""
    for act in actions:
        if act.get("params"):
            continue
        if act["tool"] in ("kimi_crawl_tool", "match_jobs_tool"):
            act["params"] = _extract_params(raw_text)
        elif act["tool"] == "create_interview_record_tool":
            city_m = _CITY_PATTERN.search(raw_text)
            if city_m:
                act["params"] = {"city_for_search": city_m.group(0)}
    return actions


def rewrite(user_input: str, llm_func=None) -> list[dict]:
    if not user_input or not user_input.strip():
        return []

    text = user_input.strip()

    # Tier 0: File marker detection — [文件: xxx.ext]
    _filenames = _extract_filenames(text)
    if _filenames:
        return [{"tool": "parse_file_tool", "params": {"filename": _filenames[0]}}]

    # Tier 1: Keyword fast path — clear single intent only
    if not _is_compound(text):
        from services.task.semantic_router import _keyword_route
        kw = _keyword_route(text)
        if kw:
            return _fill_params([{"tool": kw, "params": {}}], text)

    # Tier 2: Embedding similarity — clear single intent only
    if not _is_compound(text):
        from services.task.semantic_router import classify as _semantic_classify
        intent = _semantic_classify(text)
        if intent:
            return _fill_params([intent], text)

    # Tier 3: LLM rewrite — handles multi, ambiguous, compound
    if llm_func:
        result = llm_func(text)
        if result:
            return result

    return []
