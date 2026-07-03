import re

_CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "成都", "武汉",
    "南京", "苏州", "西安", "重庆", "长沙", "天津", "郑州",
    "东莞", "青岛", "厦门", "宁波", "大连", "合肥", "佛山",
    "福州", "昆明", "贵阳", "南宁", "哈尔滨", "长春",
]

_PLATFORMS = {
    "51job": ["51job", "前程无忧", "51"],
    "boss": ["boss", "Boss", "BOSS", "直聘", "BOSS直聘"],
    "zhaopin": ["zhaopin", "智联", "智联招聘"],
}

_SEPARATORS = re.compile(
    r"[，。、；\n]"
    r"|(?<=.)并(?=.)"
    r"|然后"
    r"|再"
    r"|接着"
    r"|之后"
    r"|且(?=\S)"
    r"|还有"
    r"|同时"
    r"|并且"
)

_TOOL_PATTERNS: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"抓取|爬取|搜索.*岗位|搜.*岗位|找.*岗位"), "kimi_crawl_tool", "crawl"),
    (re.compile(r"匹配|评分|评估.*岗位|匹配度"), "match_jobs_tool", "match"),
    (re.compile(r"新增.*面试|创建.*面试|录入.*面试|面试记录"), "create_interview_record_tool", "create_interview"),
    (re.compile(r"生成.*报告|面试宝典"), "generate_interview_report_tool", "report"),
    (re.compile(r"取消.*报告|停止.*报告"), "cancel_report_tool", "cancel_report"),
    (re.compile(r"报告.*进度|报告.*状态|报告好了没"), "check_report_status_tool", "check_report"),
    (re.compile(r"文件解析|解析.*文件|看看.*文件|读.*文件"), "parse_file_tool", "parse"),
    (re.compile(r"生成.*简历|做.*简历|制作.*简历|写.*简历"), "generate_resume_tool", "resume"),
    (re.compile(r"查询.*数据|查询.*系统|查询.*列表|统计|查看.*数据"), "query_system_data_tool", "query"),
    (re.compile(r"在线搜索|搜索.*信息|搜索一下|查一下"), "web_search_tool", "search"),
    (re.compile(r"知识库.*修改|修改.*知识库|改名|换.*经历|知识库.*预览"), "knowledge_preview", "kb_preview"),
    (re.compile(r"重建.*向量|刷新.*知识库"), "knowledge_rebuild_vector", "kb_rebuild"),
    (re.compile(r"识别.*图片|OCR|提取.*文字|翻译.*图片"), "parse_file_tool", "ocr"),
    (re.compile(r"查询.*会话|会话.*统计|访客.*统计"), "query_sessions_tool", "sessions"),
]

_FILE_MARKER = re.compile(r"\[文件:\s*(\S+\.\w+)\]")
_CITY_PATTERN = re.compile("|".join(_CITIES))
_KEYWORD_CLEANUP = re.compile(r"抓取|爬取|搜索|匹配|评分|评估|岗位|新增|创建|录入|面试|记录|生成|报告|解析|文件|简历|查询|数据|系统|知识库|修改|重建|向量|识别|图片|OCR|提取|文字|翻译|会话|统计|在线|搜索|信息|查一下|并|然后|再|接着|之后|且|还有|同时|帮我|请|的|一下|最新|一个")


def _split_into_segments(text: str) -> list[str]:
    text = text.strip()
    parts = [s.strip() for s in _SEPARATORS.split(text) if s.strip()]
    if not parts:
        parts = [text]
    return parts


def _extract_city(text: str) -> str | None:
    m = _CITY_PATTERN.search(text)
    return m.group(0) if m else None


def _extract_platform(text: str) -> str | None:
    for platform, aliases in _PLATFORMS.items():
        for alias in aliases:
            if alias in text:
                return platform
    return None


def _extract_keywords(text: str, remove_city: bool = True) -> str:
    result = text
    if remove_city:
        for city in _CITIES:
            result = result.replace(city, "")
    result = _KEYWORD_CLEANUP.sub("", result).strip()
    result = re.sub(r"\s+", "", result)
    return result if result else text


def _segment_to_action(segment: str) -> dict | None:
    for pattern, tool, _ in _TOOL_PATTERNS:
        if pattern.search(segment):
            params = {}
            if tool == "kimi_crawl_tool":
                city = _extract_city(segment)
                platform = _extract_platform(segment)
                keywords = _extract_keywords(segment)
                if keywords:
                    params["keywords"] = keywords
                if city:
                    params["city"] = city
                if platform:
                    params["platform"] = platform
            elif tool == "create_interview_record_tool":
                city = _extract_city(segment)
                if city:
                    params["city_for_search"] = city
            elif tool == "generate_interview_report_tool":
                company = (
                    segment.replace("生成", "").replace("面试报告", "")
                    .replace("面试宝典", "").replace("的", "").strip()
                )
                if company:
                    params["company"] = company
            return {"tool": tool, "params": params}
    return None


def _extract_filenames(text: str) -> list[str]:
    return _FILE_MARKER.findall(text)


def _has_any_tool_keyword(text: str) -> bool:
    for pattern, _, _ in _TOOL_PATTERNS:
        if pattern.search(text):
            return True
    return False


def parse_actions(user_input: str) -> list[dict]:
    if not user_input or not user_input.strip():
        return []

    filenames = _extract_filenames(user_input)
    clean_text = _FILE_MARKER.sub("", user_input)

    if not _has_any_tool_keyword(clean_text) and not filenames:
        return []

    segments = _split_into_segments(clean_text)

    actions: list[dict] = []
    for seg in segments:
        action = _segment_to_action(seg)
        if action:
            actions.append(action)

    if filenames and not any(a["tool"] == "parse_file_tool" for a in actions):
        for fname in filenames:
            actions.append({"tool": "parse_file_tool", "params": {"filename": fname}})

    if not actions and filenames:
        return [{"tool": "parse_file_tool", "params": {"filename": f}} for f in filenames]

    return actions
