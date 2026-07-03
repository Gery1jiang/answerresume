"""Semantic intent router — API embedding + cosine similarity + LLM fallback."""

import re
import numpy as np
from collections import OrderedDict

# ── Intent definitions ──────────────────────────────────────

_INTENTS: OrderedDict[str, dict] = OrderedDict([
    ("kimi_crawl_tool", {
        "tool": "kimi_crawl_tool",
        "params": {},
        "examples": [
            "帮我抓取产品经理的岗位",
            "爬取最近的招聘信息",
            "搜索杭州的Java开发岗位",
            "找一些AI相关的职位",
            "查一下51job上的最新岗位",
            "帮我搜几个产品运营的工作",
            "抓取boss直聘上的岗位信息",
            "爬一下招聘网站的数据",
            "我要搜索一个岗位",
            "帮我找找工作",
        ],
    }),
    ("match_jobs_tool", {
        "tool": "match_jobs_tool",
        "params": {},
        "examples": [
            "帮我匹配一下这个岗位",
            "看看这些岗位的匹配度",
            "评分一下刚才抓取的岗位",
            "分析一下这个岗位适不适合我",
            "帮我算算匹配分数",
            "这个岗位跟我匹配吗",
            "评估一下这些工作的匹配度",
            "看看哪个岗位最合适",
            "分析一下匹配情况",
        ],
    }),
    ("generate_resume_tool", {
        "tool": "generate_resume_tool",
        "params": {},
        "examples": [
            "帮我生成一份简历",
            "做一份简历PDF",
            "根据我的信息制作简历",
            "写一份产品经理的简历",
            "生成求职简历",
            "帮我做一份个人简历",
            "制作一份简历文档",
        ],
    }),
    ("parse_file_tool", {
        "tool": "parse_file_tool",
        "params": {},
        "examples": [
            "帮我解析这个文件",
            "看看这个图片里有什么",
            "读取一下这个文档的内容",
            "解析上传的PDF文件",
            "帮我读一下这个文件",
            "提取文件中的文字",
            "解析一下这个附件",
            "把这个文件的内容读出来",
            "帮我看看这个文件说了什么",
            "解析文档中的信息",
        ],
    }),
    ("create_interview_record_tool", {
        "tool": "create_interview_record_tool",
        "params": {},
        "examples": [
            "新增一个面试记录",
            "创建面试宝典",
            "录入刚才解析的面试信息",
            "帮我记录一下这次面试",
            "创建一个面试记录",
            "新增面试记录",
        ],
    }),
    ("generate_interview_report_tool", {
        "tool": "generate_interview_report_tool",
        "params": {},
        "examples": [
            "生成面试报告",
            "做一份面试宝典",
            "生成阿里巴巴的面试报告",
            "帮我创建面试攻略",
            "生成面试指南",
        ],
    }),
    ("web_search_tool", {
        "tool": "web_search_tool",
        "params": {},
        "examples": [
            "帮我搜索一下这个信息",
            "查一下最新的行业动态",
            "搜索一下这家公司的背景",
            "在线查一下这个人物",
            "帮我搜一下",
            "查一下这个新闻",
        ],
    }),
    ("query_system_data_tool", {
        "tool": "query_system_data_tool",
        "params": {},
        "examples": [
            "查看系统统计数据",
            "查询用户数据",
            "统计一下访问量",
            "看看后台数据",
            "查一下系统记录",
            "查看数据统计",
        ],
    }),
    ("knowledge_preview", {
        "tool": "knowledge_preview",
        "params": {},
        "examples": [
            "修改一下我的工作经历",
            "更新知识库中的个人信息",
            "帮我改一下项目经历",
            "换一下简历上的自我介绍",
            "修改知识库内容",
            "更新我的简历信息",
        ],
    }),
    ("knowledge_rebuild_vector", {
        "tool": "knowledge_rebuild_vector",
        "params": {},
        "examples": [
            "重建知识库索引",
            "刷新向量数据库",
            "重新构建知识库",
        ],
    }),
    ("parse_file_tool", {
        "tool": "parse_file_tool",
        "params": {},
        "examples": [
            "识别这张图片的文字",
            "OCR一下这个图片",
            "提取图片中的文字内容",
            "帮我把这个图片的文字提取出来",
            "这张图里写了什么内容",
            "帮我读一下这张图片",
            "翻译图片中的文字",
        ],
    }),
    ("query_sessions_tool", {
        "tool": "query_sessions_tool",
        "params": {},
        "examples": [
            "查一下会话记录",
            "查看访客会话统计",
            "统计会话数据",
        ],
    }),
])
# ── Embedding cache ─────────────────────────────────────────

_EXAMPLE_EMBEDDINGS: dict[str, np.ndarray] | None = None  # {intent_key: averaged_embedding}

_EMBEDDER = None  # OpenAIEmbeddings instance

def _get_embedder():
    global _EMBEDDER
    if _EMBEDDER is not None:
        return _EMBEDDER
    try:
        from langchain_community.embeddings import OpenAIEmbeddings
        from config import settings
        _EMBEDDER = OpenAIEmbeddings(
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_API_BASE,
            model=settings.SILICONFLOW_EMBEDDING_MODEL,
        )
    except Exception as e:
        print(f"[semantic_router] embedder init failed: {e}")
    return _EMBEDDER


def _build_index():
    global _EXAMPLE_EMBEDDINGS
    embedder = _get_embedder()
    if embedder is None:
        return

    _EXAMPLE_EMBEDDINGS = {}
    for key, intent in _INTENTS.items():
        texts = intent["examples"]
        try:
            embs = embedder.embed_documents(texts)
            mean_emb = np.mean(embs, axis=0)
            _EXAMPLE_EMBEDDINGS[key] = mean_emb / (np.linalg.norm(mean_emb) + 1e-9)
        except Exception as e:
            print(f"[semantic_router] embedding failed for {key}: {e}")


# ── Keyword fast path ───────────────────────────────────────

_KEYWORD_ROUTES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?:帮(?:我)?)?(?:抓取|爬取|搜索).*?(?:招聘|岗位|职位|工作)"), "kimi_crawl_tool"),
    (re.compile(r"(?:帮(?:我)?)?(?:匹配|评分|评估|分析).*(?:匹配|适合|评估|评分|度|性)"), "match_jobs_tool"),
    (re.compile(r"(?:帮(?:我)?)?(?:生成|做|制作|写).*简历"), "generate_resume_tool"),
    (re.compile(r"(?:帮(?:我)?)?(?:解析|读取|提取|打开).*(?:文件|图片|文档|PDF|附件|内容|文字)"), "parse_file_tool"),
    (re.compile(r"(?:帮(?:我)?)?(?:新增|创建|添加).*面试"), "create_interview_record_tool"),
    (re.compile(r"(?:帮(?:我)?)?(?:生成|创建|制作).*面试.*报告"), "generate_interview_report_tool"),
    (re.compile(r"(?:搜索|查|找).*(?:新闻|信息|资料|网站|网页)"), "web_search_tool"),
    (re.compile(r"(?:帮(?:我)?)?(?:修改|更新|编辑|换).*(?:知识|简历|经历|信息)"), "knowledge_preview"),
    (re.compile(r"(?:重建|刷新|重新).*(?:索引|向量|知识库)"), "knowledge_rebuild_vector"),
    (re.compile(r"(?:查|查询|查看|搜索).*(?:会话|聊天|对话|记录)"), "query_sessions_tool"),
    (re.compile(r"(?:查|查询|查看|搜索).*(?:统计|数据|系统|指标)"), "query_system_data_tool"),
]

def _keyword_route(text: str) -> str | None:
    for pattern, tool in _KEYWORD_ROUTES:
        if pattern.search(text.strip()):
            return tool
    return None


# ── Public API ──────────────────────────────────────────────

_SIMILARITY_THRESHOLD = 0.72


def classify(user_input: str) -> dict | None:
    if not user_input or not user_input.strip():
        return None

    text = user_input.strip()

    # 1. Keyword fast path
    kw_tool = _keyword_route(text)
    if kw_tool:
        return {"tool": kw_tool, "params": {}}

    # 2. Embedding similarity
    if _EXAMPLE_EMBEDDINGS is None:
        _build_index()

    if _EXAMPLE_EMBEDDINGS:
        embedder = _get_embedder()
        if embedder:
            try:
                query_emb = np.array(embedder.embed_query(text))
                query_norm = query_emb / (np.linalg.norm(query_emb) + 1e-9)
                best_key = None
                best_score = -1.0
                for key, mean_emb in _EXAMPLE_EMBEDDINGS.items():
                    score = float(np.dot(query_norm, mean_emb))
                    if score > best_score:
                        best_score = score
                        best_key = key
                if best_key and best_score >= _SIMILARITY_THRESHOLD:
                    return {"tool": best_key, "params": {}}
            except Exception as e:
                print(f"[semantic_router] query embedding error: {e}")

    return None


def warmup():
    _build_index()
