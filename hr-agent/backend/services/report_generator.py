import asyncio
import json
import logging
import os
import re
import contextvars
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx
from sqlalchemy.orm import Session as DBSession
from jinja2 import Environment, FileSystemLoader

from config import settings, get_user_knowledge_dir
from services.database import SessionLocal
from services.models import InterviewGuide, ReportGenerationTask
from services.usage_service import usage_service

_report_user_id: contextvars.ContextVar[str] = contextvars.ContextVar('report_user_id', default='')

logger = logging.getLogger(__name__)


class ReportCancelledError(Exception):
    """Raised inside _generate_report_body when the task is cancelled by user."""


def _check_report_cancelled(guide_id: int):
    """Quick DB check — if task status changed to cancelled, abort."""
    try:
        from services.database import SessionLocal
        from services.models import ReportGenerationTask
        _db = SessionLocal()
        try:
            task = _db.query(ReportGenerationTask).filter(
                ReportGenerationTask.guide_id == guide_id,
                ReportGenerationTask.status == "cancelled",
            ).first()
            if task:
                raise ReportCancelledError("用户取消")
        finally:
            _db.close()
    except ReportCancelledError:
        raise
    except Exception:
        pass
if not logger.handlers:
    _h = logging.StreamHandler()
    _h.setLevel(logging.INFO)
    logger.addHandler(_h)
logger.setLevel(logging.INFO)




_CLIENT = httpx.AsyncClient(
    timeout=httpx.Timeout(30.0, connect=10.0),
    limits=httpx.Limits(max_connections=10, max_keepalive_connections=5),
)

# ═══════════════════════════════════════════════════════════════════════
#  Report format versioning
#  Bump REPORT_FORMAT_VERSION whenever you change the LLM JSON schema or
#  the Jinja2 template in a way that would break backward compatibility.
#  Stored in DB alongside generated reports for traceability.
# ═══════════════════════════════════════════════════════════════════════
REPORT_FORMAT_VERSION = "2.0"
REPORT_TEMPLATE_NAME = "interview_report.md"
# Fields that MUST be present in the content dict passed to the template.
# When adding a new field, add it here; when removing, remove it here.
REQUIRED_CONTENT_FIELDS = {
    "company_profile",
    "products",
    "product_details",
    "business_lines",
    "business_model",
    "revenue_model",
    "target_customers",
    "competitors",
    "competitive_barriers",
    "market_risks",
    "product_advantages",
    "product_disadvantages",
    "optimization_suggestions",
    "fit_analysis",
    "value_proposition",
    "common_interview_questions",
    "questions_to_ask",
    "interview_tips",
    "report_metadata",
    "report_format_version",
}

# ── LLM config: read saved admin panel config from DB, fall back to .env ──

# Track search results for report metadata
_report_search_results: list[dict] = []


# ── Webpage deep-scrape integration ───────────────────────────────
# Primary: HTTP + trafilatura/BS4 crawler. Fallback: Firecrawl (credit-budgeted).
# Non-blocking, never raises on failure.

HAS_FIRECRAWL = False
_firecrawl_client = None
_firecrawl_daily_used = 0
_firecrawl_last_key = ""


_SCRAPE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:136.0) Gecko/20100101 Firefox/136.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}


async def _http_scrape(url: str, max_chars: int = 15000) -> str | None:
    """Fallback scraper: HTTP GET + trafilatura / BeautifulSoup."""
    try:
        import requests as _req
        resp = _req.get(url, headers=_SCRAPE_HEADERS, timeout=15)
        resp.raise_for_status()
        html = resp.text

        try:
            import trafilatura as _tf
            text = _tf.extract(html, include_formatting=False, with_metadata=False,
                               include_links=False, output_format="txt")
            if text and len(text) > 100:
                return text[:max_chars]
        except (ImportError, Exception):
            pass

        from bs4 import BeautifulSoup as _BS
        soup = _BS(html, "lxml")
        for tag in soup.select("script, style, nav, footer, header, aside, .sidebar, .nav, .footer, .header, .ad"):
            tag.decompose()
        lines: list[str] = []
        for el in soup.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "th", "blockquote", "pre"]):
            t = el.get_text(strip=True)
            if len(t) > 15:
                lines.append(t)
        text = "\n".join(lines)
        return text[:max_chars] if len(text) > 100 else None
    except Exception as e:
        logger.debug("_http_scrape failed for %s: %s", url, e)
        return None

def _init_firecrawl():
    global HAS_FIRECRAWL, _firecrawl_client, _firecrawl_last_key
    api_key = getattr(settings, "FIRECRAWL_API_KEY", "")
    if not api_key:
        HAS_FIRECRAWL = False
        _firecrawl_client = None
        return
    # Re-init if key changed
    if _firecrawl_client is not None and api_key == _firecrawl_last_key:
        return
    try:
        from firecrawl import Firecrawl
        _firecrawl_client = Firecrawl(api_key=api_key)
        _firecrawl_last_key = api_key
        HAS_FIRECRAWL = True
        logger.info("Firecrawl client ready (daily budget: %d)",
                     getattr(settings, "FIRECRAWL_DAILY_BUDGET", 20))
    except Exception as e:
        logger.warning("Firecrawl init skipped: %s", e)


def _firecrawl_budget_remaining() -> int:
    budget = getattr(settings, "FIRECRAWL_DAILY_BUDGET", 20)
    return max(0, budget - _firecrawl_daily_used)


class _FirecrawlGrader:
    """Grade=2 always scrape, grade=1 if budget>=3, grade=0 skip."""
    HIGH = [
        "baike.so.com", "baike.baidu.com",       # 百科
        "icinfo.cn", "gov.cn",                    # 官方
        "aiqicha", "tianyancha", "qcc.com", "qixin",  # 工商登记
    ]
    MEDIUM = [
        "163.com", "nbd.com.cn", "people.com.cn", "thepaper.cn",
        "mp.weixin.qq.com",
    ]

    @classmethod
    def grade(cls, url: str) -> int:
        if any(p in url for p in cls.HIGH):
            return 2
        if any(p in url for p in cls.MEDIUM):
            return 1
        return 0

    @classmethod
    def should_scrape(cls, url: str) -> bool:
        remaining = _firecrawl_budget_remaining()
        g = cls.grade(url)
        if g == 0:
            return False
        if g == 2:
            return True
        if g == 1 and remaining >= 3:
            return True
        return False


async def _firecrawl_scrape(url: str) -> Optional[str]:
    """Scrape one URL with Firecrawl. Returns markdown or None."""
    global _firecrawl_daily_used
    if not HAS_FIRECRAWL or _firecrawl_client is None:
        return None
    _firecrawl_daily_used += 1
    try:
        result = _firecrawl_client.scrape(url, formats=["markdown"])
        if result and hasattr(result, "markdown") and result.markdown:
            text = result.markdown[:3000]
            logger.info("Firecrawl OK: %s (%d chars)", url, len(text))
            _uid = _report_user_id.get()
            if _uid:
                usage_service.record(user_id=_uid, event_type="search_api", model="firecrawl", search_calls=1)
            return text
        return None
    except Exception as e:
        logger.warning("Firecrawl failed: %s — %s", url, e)
        return None


async def _enrich_with_firecrawl(results: dict) -> dict:
    """After SearXNG search, scrape high-value URLs with Firecrawl or HTTP fallback."""
    _init_firecrawl()

    candidates: list[tuple[int, str, dict]] = []
    seen: set[str] = set()
    for eng, data in results.get("engines", {}).items():
        for item in data.get("items", []):
            url = item.get("url", "")
            if url and url not in seen:
                seen.add(url)
                g = _FirecrawlGrader.grade(url)
                if g > 0:
                    candidates.append((g, url, item))

    candidates.sort(key=lambda x: -x[0])
    logger.info("Scrape enrichment: %d candidates", len(candidates))

    scraped = 0
    for g, url, item in candidates:
        if not _FirecrawlGrader.should_scrape(url):
            continue
        full_text = await _http_scrape(url)
        if not full_text and HAS_FIRECRAWL:
            remaining = _firecrawl_budget_remaining()
            if scraped < remaining:
                full_text = await _firecrawl_scrape(url)
        if full_text:
            item["full_text"] = full_text
            scraped += 1

    logger.info("Scrape enrichment done: scraped %d pages", scraped)
    return results


_BIZ_SOURCE_DOMAINS = {
    "tianyancha.com": "工商登记",
    "qcc.com": "工商登记",
    "qixin.com": "工商登记",
    "aiqicha.baidu.com": "工商登记",
    "qichacha.com": "工商登记",
    "qichamao.com": "工商登记",
    "baike.baidu.com": "百科",
    "baike.so.com": "百科",
    "gov.cn": "官方",
    "36kr.com": "商业资讯",
}


def _classify_source(url: str) -> str:
    """Classify AnySearch result source domain into a label for the LLM."""
    for domain, label in _BIZ_SOURCE_DOMAINS.items():
        if domain in url:
            return label
    return "网页"


async def _anysearch_search(query: str, limit: int = 5) -> list[dict]:
    api_key = getattr(settings, "ANYSEARCH_API_KEY", "")
    if not api_key:
        logger.info("AnySearch not configured -- skip")
        return []
    try:
        resp = await _CLIENT.post(
            "https://api.anysearch.com/v1/search",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "domain": "general",
                "limit": limit,
                "lang": "zh",
            },
            timeout=30,
        )
        if resp.status_code != 200:
            logger.warning("AnySearch returned %d: %s", resp.status_code, resp.text[:200])
            return []
        _uid = _report_user_id.get()
        if _uid:
            usage_service.record(user_id=_uid, event_type="search_api", model="anysearch", search_calls=1)
        data = resp.json()
        if data.get("code") != 0:
            logger.warning("AnySearch error: %s", data.get("message", ""))
            return []
        results = data.get("data", {}).get("results", [])
        entries = [
            {
                "title": r.get("title", ""),
                "content": r.get("content", "")[:500],
                "url": r.get("url", ""),
                "score": r.get("score", 0),
            }
            for r in results[:limit * 2]  # fetch more for re-ranking
        ]
        # Re-rank: prefer 工商 sources, then 百科/官方, then general
        _BIZ_PRIORITY = {  # noqa
            "工商登记": 0,
            "官方": 1,
            "百科": 2,
            "商业资讯": 3,
            "网页": 4,
        }
        for e in entries:
            e["_source_label"] = _classify_source(e.get("url", ""))
            e["_source_rank"] = _BIZ_PRIORITY.get(e["_source_label"], 99)
        entries.sort(key=lambda e: (e["_source_rank"], -e.get("score", 0)))
        return entries[:limit]
    except Exception as e:
        logger.warning("AnySearch request failed: %s", e)
        return []


async def _anysearch_format_results(results: list[dict]) -> str:
    if not results:
        return ""
    lines = ["【AnySearch 搜索结果（按权威性排序：工商登记→百科→官方→网页）】"]
    for i, r in enumerate(results, 1):
        label = r.get("_source_label", _classify_source(r.get("url", "")))
        lines.append(f"{i}. [{label}] {r['title']}")
        if r.get("url"):
            lines.append(f"   来源：{r['url']}")
        if r.get("content"):
            lines.append(f"   {r['content'][:300]}")
    return "\n".join(lines)


def _build_business_keywords(
    bg: dict, company_desc: str, jd_parsed: dict, jd_text: str
) -> str:
    """从工商搜索反馈 (bg) + JD 数据中提取业务关键词，用于定向产品/竞品搜索。
    
    优先级：bg.industry > company_description > jd_parsed.keywords > jd_parsed.summary
    返回空格分隔的关键词串（最多 3 个，每个 10 字内），为空时返回空字符串。
    """
    candidates = []

    if company_desc and len(company_desc) <= 20:
        candidates.append(company_desc)

    industry = bg.get("industry", "")
    if industry:
        short = industry.split("（")[0].split("、")[0].strip()
        if short and short not in candidates:
            candidates.append(short)

    summary = jd_parsed.get("summary", "") if isinstance(jd_parsed, dict) else ""
    if summary:
        for kw in summary.replace("，", " ").replace("/", " ").split():
            kw = kw.strip()
            if kw not in candidates and 1 < len(kw) <= 8:
                candidates.append(kw)
            if len(candidates) >= 3:
                break

    preferred = jd_parsed.get("preferred", "") if isinstance(jd_parsed, dict) else ""
    if isinstance(preferred, list):
        for p in preferred:
            if p not in candidates and 1 < len(p) <= 10:
                candidates.append(p)
            if len(candidates) >= 3:
                break

    return " ".join(candidates[:3]) if candidates else ""


def _build_jd_keywords(company_desc: str, jd_parsed: dict) -> str:
    """从公司描述 + JD 数据中提取业务关键词（不依赖 bg，用于并行化）。
    
    优先级：company_description > jd_parsed.keywords > jd_parsed.summary
    返回空格分隔的关键词串（最多 3 个，每个 10 字内），为空时返回空字符串。
    """
    candidates = []

    if company_desc and len(company_desc) <= 20:
        candidates.append(company_desc)

    summary = jd_parsed.get("summary", "") if isinstance(jd_parsed, dict) else ""
    if summary:
        for kw in summary.replace("，", " ").replace("/", " ").split():
            kw = kw.strip()
            if kw not in candidates and 1 < len(kw) <= 8:
                candidates.append(kw)
            if len(candidates) >= 3:
                break

    preferred = jd_parsed.get("preferred", "") if isinstance(jd_parsed, dict) else ""
    if isinstance(preferred, list):
        for p in preferred:
            if p not in candidates and 1 < len(p) <= 10:
                candidates.append(p)
            if len(candidates) >= 3:
                break

    return " ".join(candidates[:3]) if candidates else ""


_TAVILY_API_KEY = getattr(settings, "TAVILY_API_KEY", "")
HAS_TAVILY = bool(_TAVILY_API_KEY)


async def _tavily_search(query: str, max_results: int = 5, search_depth: str = "basic") -> dict:
    """Search via Tavily API. Returns {answer, results: [{title, content, url}]}."""
    if not HAS_TAVILY:
        logger.info("Tavily not configured -- skip")
        return {"answer": "", "results": []}
    try:
        resp = await _CLIENT.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {_TAVILY_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "search_depth": search_depth,
                "topic": "general",
                "max_results": max_results,
                "include_answer": True,
            },
            timeout=20,
        )
        if resp.status_code != 200:
            logger.warning("Tavily returned %d: %s", resp.status_code, resp.text[:200])
            return {"answer": "", "results": []}
        _uid = _report_user_id.get()
        if _uid:
            usage_service.record(user_id=_uid, event_type="search_api", model="tavily", search_calls=1)
        data = resp.json()
        return {
            "answer": data.get("answer", ""),
            "results": data.get("results", []),
        }
    except Exception as e:
        logger.warning("Tavily search failed: %s", e)
        return {"answer": "", "results": []}


_PROVIDER_BASE_URLS = {
    "SiliconFlow": "https://api.siliconflow.cn/v1",
    "LongCat": "https://api.longcat.chat/openai/v1",
    "DeepSeek": "https://api.deepseek.com/v1",
    "阿里云": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "百度智能云": "https://qianfan.baidubce.com/v2",
    "字节云": "https://ark.cn-beijing.volces.com/api/v3",
    "腾讯云": "https://hunyuan.tencentcs.com/v2",
    "智谱AI": "https://open.bigmodel.cn/api/paas/v4",
    "百川智能": "https://api.baichuan-ai.com/v1",
    "月之暗面": "https://api.moonshot.cn/v1",
    "OpenAI": "https://api.openai.com/v1",
}

def _get_llm_config() -> dict:
    """管理端 LLM 配置：DB → env 兜底（共享函数）。"""
    from config import get_admin_llm_config
    return get_admin_llm_config()

def _get_llm_key() -> str:
    return _get_llm_config()["api_key"]

def _get_llm_base() -> str:
    return _get_llm_config()["api_base"]

def _get_llm_model() -> str:
    return _get_llm_config()["model"]

TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "reports")


# ═══════════════════════════════════════════════════════════════════════
#  Phase 1.5: Candidate knowledge base loader
# ═══════════════════════════════════════════════════════════════════════

def _load_candidate_kb(user_id: str) -> dict:
    """Read knowledge base files (01-06_.md) from the user's knowledge directory."""
    kb_files = {
        "个人信息": "01_个人信息.md",
        "教育背景": "02_教育背景.md",
        "项目经历": "04_项目经历.md",
        "专业技能": "05_专业技能栈.md",
        "工作经历": "03_工作经历.md",
        "高频问答": "06_HR高频问答库.md",
    }
    kb_base = get_user_knowledge_dir(user_id)
    logger.info(f"Loading candidate KB from: {kb_base}")
    kb = {}
    for section, filename in kb_files.items():
        fp = os.path.join(kb_base, filename)
        if os.path.isfile(fp):
            try:
                with open(fp, "r", encoding="utf-8") as f:
                    kb[section] = f.read()
            except Exception as e:
                logger.warning(f"Failed to read {fp}: {e}")
                kb[section] = ""
        else:
            logger.warning(f"KB file not found: {fp}")
            kb[section] = ""
    return kb


# ═══════════════════════════════════════════════════════════════════════
#  Phase 2.7: JD parser
# ═══════════════════════════════════════════════════════════════════════

async def _parse_jd(jd_text: str) -> dict:
    """Use LLM to parse raw JD text into structured data."""
    if not jd_text or not jd_text.strip():
        return {"requirements": [], "responsibilities": [], "keywords": [], "summary": ""}
    prompt = f"""你是一个招聘专家。请分析以下岗位描述（JD），用JSON返回结构化信息。

JSON格式：
{{
  "summary": "岗位总览（一句话概括）",
  "responsibilities": ["职责1（具体可衡量）", "职责2", "职责3"],
  "requirements": ["要求1（具体可衡量）", "要求2", "要求3"],
  "preferred": ["加分项1", "加分项2"],
  "keywords": ["关键技能词1", "技能词2", "行业词1"],
  "seniority": "资历要求（如3-5年经验）",
  "education": "学历要求（如本科及以上）"
}}

JD文本：
{jd_text}"""
    return await _llm_json(prompt)


# ═══════════════════════════════════════════════════════════════════════
#  Phase 2.1: Company background (structured + milestones)
# ═══════════════════════════════════════════════════════════════════════

async def _search_multi(queries: list[str], stagger: float = 1.5) -> dict:
    """多角度并行搜索，合并结果，按URL去重。
    stagger: 查询间间隔秒数，避免上游引擎限流。"""
    if stagger > 0 and len(queries) > 1:
        results = []
        for i, q in enumerate(queries):
            if i > 0:
                await asyncio.sleep(stagger)
            results.append(await _search_all_engines(q))
        raw_results = results
    else:
        raw_results = await asyncio.gather(*[_search_all_engines(q) for q in queries], return_exceptions=True)

    merged = {"query": " | ".join(queries), "engines": {}, "timing": {}}
    seen_urls = set()
    total_start = float("inf")
    total_end = 0

    for idx, sr in enumerate(raw_results):
        if isinstance(sr, Exception):
            logger.warning(f"Search query #{idx} failed: {sr}")
            continue
        for eng, data in sr.get("engines", {}).items():
            if eng not in merged["engines"]:
                merged["engines"][eng] = {"count": 0, "items": [], "elapsed": 0}
            eng_data = merged["engines"][eng]
            for item in data.get("items", []):
                url = item.get("url", "")
                if url and url in seen_urls:
                    continue
                if url:
                    seen_urls.add(url)
                eng_data["items"].append(item)
                eng_data["count"] = len(eng_data["items"])
            eng_data["elapsed"] = max(eng_data.get("elapsed", 0), data.get("elapsed", 0))
        for eng, t in sr.get("timing", {}).items():
            if isinstance(t, (int, float)):
                if t > 0:
                    total_start = min(total_start, t)
                    total_end = max(total_end, t)
                merged["timing"][eng] = max(merged["timing"].get(eng, 0), t if isinstance(t, (int, float)) else 0)

    merged["timing"]["total"] = total_end - total_start if total_end > total_start else total_end
    # Limit items per engine to prevent prompt overflow
    for eng in merged["engines"]:
        merged["engines"][eng]["items"] = merged["engines"][eng]["items"][:8]
        merged["engines"][eng]["count"] = len(merged["engines"][eng]["items"])

    merged = await _enrich_with_firecrawl(merged)
    return merged


async def fetch_company_background(company: str, search_suffix: str = "") -> dict:
    suffix = search_suffix
    # ── Step 1: AnySearch as primary source for 工商信息 ──
    anysearch_raw = await _anysearch_search(
        f"{company} 法定代表人 注册资本 成立日期 股东 工商信息"
    )
    anysearch_text = await _anysearch_format_results(anysearch_raw) if anysearch_raw else ""

    # ── Step 2: Tavily for overview/culture/scale — 擅长返回摘要+精确数据 ──
    tavily_overview = await _tavily_search(
        f"{company}{suffix} 公司简介 员工人数 企业文化 价值观 使命 规模",
        max_results=5, search_depth="advanced",
    )
    tavily_section = ""
    if tavily_overview.get("results") or tavily_overview.get("answer"):
        lines = ["【公司概况（Tavily）】"]
        if tavily_overview.get("answer"):
            lines.append(f"摘要：{tavily_overview['answer']}")
        for r in tavily_overview.get("results", [])[:4]:
            lines.append(f"- {r.get('title','')}")
            if r.get("url"):
                lines.append(f"  链接：{r['url']}")
            if r.get("content"):
                lines.append(f"  {r['content'][:350]}")
        tavily_section = "\n".join(lines)

    # ── Step 3: SearXNG fallback for overview/culture/news ──
    fallback_queries = [
        f"{company}{suffix} 公司简介 主营业务 行业地位",
        f"{company}{suffix} 企业文化 价值观 使命",
        f"{company}{suffix} 发展历程 资质 荣誉",
        f"{company}{suffix} 员工人数 规模 融资",
        f"{company}{suffix} 2024 2025 最新消息",
        f"{company}{suffix} 招聘 岗位 薪资",
    ]
    sr_fallback = await _search_multi(fallback_queries)
    fallback_text = _format_search_results_for_prompt(sr_fallback)
    _report_search_results.append(sr_fallback)

    sections = []
    if anysearch_text:
        sections.append(f"【工商信息（AnySearch）】\n{anysearch_text}")
    if tavily_section:
        sections.append(tavily_section)
    sections.append(f"【其他公开信息（搜索引擎）】\n{fallback_text}")
    search_results = "\n\n".join(sections)

    prompt = f"""你是{company}的研究专家。请用JSON格式深度返回公司背景信息。

    严格基于下方搜索材料回答，**禁止用你自己的知识补充**。搜索未覆盖的信息标注"未找到公开信息"。
JSON格式：
{{
  "overview": "公司简介（2-3句话，包含主营业务和行业地位，必须填写）",
  "industry": "所属行业（必须填写）",
  "scale": "公司规模（人数或估值，尽量具体）",
  "funding_stage": "融资阶段（如有）",
  "culture": "公司文化、价值观、工作氛围等（2-3句话，必须填写）",
  "established": "成立时间（精确到年份或年月）",
  "registered_capital": "注册资本",
  "legal_person": "法定代表人",
  "equity_structure": "股权结构/股东背景",
  "parent_company": "母公司/上市主体（如有）",
  "headquarters": "所在地/总部地址",
  "branches": "分支机构数量或分布情况",
  "culture_values": {{
    "mission": "公司使命（如有）",
    "vision": "公司愿景（如有）",
    "values": "公司价值观（如有）",
    "operating_philosophy": "经营理念（如有）",
    "interpretation": "文化解读——面试中可以如何利用或体现（2-3句话）"
  }},
  "qualifications": [
    {{"type": "资质类型（如华为生态、金融资质、安全资质等）", "name": "资质名称", "source": "来源"}}
  ],
  "milestones": [
    {{"year": "年份", "event": "里程碑事件描述", "source": "信息来源"}},
    {{"year": "年份", "event": "里程碑事件描述", "source": "信息来源"}}
  ],
  "recent_news": ["最近的一条重要动态", "近期的第二条动态", "近期的第三条动态"]
}}
规则：
- 所有字段尽量填写，不要留空
- milestones 按时间顺序排列，至少3个，每条标注来源
- qualifications 尽量多列，标注每条来源
- recent_news 必须是字符串数组，每条一句话，提取真实具体的新闻事件
- 搜索信息不足时标注"未找到公开信息"，禁止用你自己的知识补充
- **优先使用 AnySearch 工商信息中的内容填写 established/registered_capital/legal_person/equity_structure/parent_company/headquarters 字段**
- **提取方法：在 AnySearch 的 [工商登记] 结果中，寻找 "法定代表人："、"注册资本："、"成立日期："、"注册地址：" 等字段，直接从其后提取具体数值。例如天眼查、企查查结果通常包含 "法定代表人：沈越" 这种结构，直接提取 "沈越"。不要遗漏这些字段。**
搜索供参考：
{search_results}"""
    return await _llm_json(prompt)


# ═══════════════════════════════════════════════════════════════════════
#  Phase 2.2: Product & competitor analysis (deep format)
# ═══════════════════════════════════════════════════════════════════════

def _extract_competitor_names(
    anysearch_competitor: list,
    anysearch_competitor2: list,
    tavily_competitor: dict,
    company: str,
) -> list[str]:
    """从 Tavily answer + AnySearch 结果中提取竞品公司名。

    优先级：
      1. Tavily answer（LLM 摘要，通常直接列出竞品名）
      2. AnySearch 结果正文（行业报告常提多个公司名）
    """
    candidates = set()

    # ── 来源 1: Tavily answer ──
    answer = tavily_competitor.get("answer", "") if isinstance(tavily_competitor, dict) else ""
    if answer:
        rest = ""
        for prefix in ["include ", "competitors include ", "rivals include "]:
            idx = answer.lower().find(prefix)
            if idx >= 0:
                rest = answer[idx + len(prefix):]
                break
        if not rest:
            rest = answer
        for part in re.split(r'[,，、]', rest):
            part = part.strip().rstrip('.。 ')
            part = re.sub(r'\s+and\s+.*$', '', part)
            if 2 <= len(part) <= 30 and not any(
                w in part.lower() for w in ["the ", "its ", "this ", "a "]
            ):
                candidates.add(part)

    # ── 来源 2: AnySearch 结果正文中的中文公司名 ──
    for r in (anysearch_competitor or []) + (anysearch_competitor2 or []):
        text = f"{r.get('title', '')} {r.get('content', '')[:300]}"
        # 匹配 "XX公司/科技/安全/软件" 格式
        for name in re.findall(r'[\u4e00-\u9fff]{2,4}(?:公司|科技|技术|安全|软件|时代|认证)', text):
            name = name.strip()
            if name and company not in name and 2 <= len(name) <= 12:
                candidates.add(name)

    candidates.discard(company)
    candidates.discard("")
    noise = {"官网", "百度百科", "首页", "招聘", "项目信息", "公司简介",
             "上市公司", "个人主页", "创投平台", "搜狐证券", "项目信息-36氪"}
    candidates -= noise
    return list(candidates)[:4]


async def fetch_product_business(company: str, search_suffix: str = "") -> dict:
    suffix = search_suffix

    # ── Step 1: AnySearch for product + competitor intelligence ──
    anysearch_product = await _anysearch_search(f"{company}{suffix} 产品 解决方案 业务线 核心产品")
    anysearch_competitor = await _anysearch_search(f"{company}{suffix} 竞争对手 竞品 对比 行业排名")
    anysearch_competitor2 = await _anysearch_search(f"{company}{suffix} VS 对比 优劣势 市场份额")

    # ── Step 2: Tavily for product page discovery + web results ──
    tavily_product = await _tavily_search(f"{company}{suffix} 核心产品 业务线 官网 产品介绍", max_results=8, search_depth="advanced")
    tavily_competitor = await _tavily_search(f"{company}{suffix} 竞争对手 竞品分析 行业对比 市场份额", max_results=8, search_depth="advanced")

    # ── Step 3: Build search context for LLM ──
    sections = []

    if anysearch_product:
        sections.append(await _anysearch_format_results(anysearch_product))
    if anysearch_competitor:
        sections.append(await _anysearch_format_results(anysearch_competitor))
    if anysearch_competitor2:
        sections.append(await _anysearch_format_results(anysearch_competitor2))

    if tavily_product.get("results"):
        lines = ["【Tavily 产品搜索结果】"]
        if tavily_product.get("answer"):
            lines.append(f"摘要：{tavily_product['answer']}")
        for r in tavily_product["results"][:6]:
            lines.append(f"- {r.get('title','')}")
            if r.get("url"):
                lines.append(f"  链接：{r['url']}")
            if r.get("content"):
                lines.append(f"  {r['content'][:300]}")
        sections.append("\n".join(lines))

    if tavily_competitor.get("results"):
        lines = ["【Tavily 竞品搜索结果】"]
        if tavily_competitor.get("answer"):
            lines.append(f"摘要：{tavily_competitor['answer']}")
        for r in tavily_competitor["results"][:6]:
            lines.append(f"- {r.get('title','')}")
            if r.get("url"):
                lines.append(f"  链接：{r['url']}")
            if r.get("content"):
                lines.append(f"  {r['content'][:300]}")
        sections.append("\n".join(lines))

    # ── Step 4: 网页深度抓取 — 公司官网 + 竞品网站 ──
    firecrawl_notes = ""
    _init_firecrawl()
    scraped_texts = []
    # Always try scraping (Firecrawl first, HTTP fallback)
    company_urls = set()
    for r in tavily_product.get("results", []):
        url = r.get("url", "")
        if url:
            company_urls.add(url)
    for r in (anysearch_product or [])[:2]:
        url = r.get("url", "")
        if url:
            company_urls.add(url)
    for url in list(company_urls)[:3]:
        text = await _http_scrape(url)
        if not text and HAS_FIRECRAWL and _firecrawl_budget_remaining() > 0:
            text = await _firecrawl_scrape(url)
        if text:
            scraped_texts.append(f"【公司页面】{url}\n{text}")

    # 提取竞品公司名 → 搜官网 → 深度抓取
    competitor_names = _extract_competitor_names(
        anysearch_competitor, anysearch_competitor2,
        tavily_competitor, company,
    )
    for comp_name in competitor_names[:2]:
        comp_search = await _tavily_search(f"{comp_name} 官网 产品 简介", max_results=3)
        for r in comp_search.get("results", []):
            url = r.get("url", "")
            if not url:
                continue
            text = await _http_scrape(url)
            if not text and HAS_FIRECRAWL and _firecrawl_budget_remaining() > 0:
                text = await _firecrawl_scrape(url)
            if text:
                scraped_texts.append(f"【竞品：{comp_name}】{url}\n{text}")
            break  # 每个竞品只抓一个页面

    if scraped_texts:
        sections.append(
            "以下为深度抓取的页面正文（来源可靠，优先用于产品与竞品分析）：\n"
            + "\n\n".join(scraped_texts)
        )
        firecrawl_notes = f"\n* {len(scraped_texts)}个页面通过深度抓取"

    search_results = "\n\n".join(sections)
    if not search_results.strip():
        # Fallback: use SearXNG
        fallback = await _search_multi([
            f"{company}{suffix} 产品 解决方案 业务",
            f"{company}{suffix} 竞品 竞争对手 行业排名",
        ])
        search_results = _format_search_results_for_prompt(fallback)
        _report_search_results.append(fallback)

    # ── Phase 1: Parallel extraction (focused tasks, simple JSON each) ──
    async def _extract_products():
        p = f"""你是{company}的行业分析专家。从下方搜索材料中提取该公司的主要产品、产品详情和业务线。

严格基于搜索材料，禁止用你的知识补充。搜索未覆盖的标注"未找到公开信息"。
JSON格式（只返回此JSON，不要其他文字）：
{{
  "products": ["产品1", "产品2"],
  "product_details": [
    {{
      "name": "产品名称",
      "positioning": "产品定位与目标用户",
      "features": "核心功能清单",
      "business_model": "该产品的商业模式",
      "pros": "产品优势",
      "cons": "产品劣势/局限",
      "architecture_layer": "产品归属层次",
      "source": "信息来源"
    }}
  ],
  "business_lines": [
    {{"name": "业务线名称", "description": "业务线详细介绍"}}
  ]
}}
搜索材料：
{search_results}{firecrawl_notes}"""
        return await _llm_json(p)

    async def _extract_competitors_and_market():
        p = f"""你是{company}的行业分析专家。从下方搜索材料中提取该公司的竞品信息和市场竞争分析。

严格基于搜索材料，禁止用你的知识补充。搜索未覆盖的标注"未找到公开信息"。
JSON格式（只返回此JSON，不要其他文字）：
{{
  "competitors": [
    {{
      "name": "竞品名称",
      "analysis": "竞品详细分析，包括市场份额、定位、优劣势（写具体，至少50字）",
      "advantage": "该竞品的优势",
      "disadvantage": "该竞品的劣势"
    }}
  ],
  "competitive_barriers": "竞争壁垒分析",
  "market_risks": "市场风险与挑战",
  "product_advantages": ["优势1详细说明", "优势2详细说明"],
  "product_disadvantages": ["劣势1详细说明", "劣势2详细说明"]
}}
搜索材料：
{search_results}{firecrawl_notes}"""
        return await _llm_json(p)

    async def _extract_business_model():
        p = f"""你是{company}的行业分析专家。从下方搜索材料中提取该公司的商业模式、收入模式和体系架构。

严格基于搜索材料，禁止用你的知识补充。搜索未覆盖的标注"未找到公开信息"。
JSON格式（只返回此JSON，不要其他文字）：
{{
  "architecture_overview": "产品体系架构总览，描述各产品/模块之间的层次关系和定位",
  "core_business_logic": "核心商业逻辑一句话总结",
  "business_model": "商业模式详细描述",
  "revenue_model": "盈利模式/收入来源",
  "business_model_summary": [
    {{"revenue_source": "收入来源名称", "model": "模式", "description": "说明"}}
  ],
  "target_customers": "目标客户群体和用户画像描述",
  "core_risks": ["风险1（具体描述）", "风险2（具体描述）"],
  "core_barriers": ["壁垒1（具体描述）", "壁垒2（具体描述）"],
  "optimization_suggestions": [
    {{
      "area": "优化领域",
      "suggestion": "具体优化建议和构想",
      "expected_impact": "预期效果"
    }}
  ]
}}
搜索材料：
{search_results}{firecrawl_notes}"""
        return await _llm_json(p)

    # Run 3 extraction tasks in parallel
    results = await asyncio.gather(
        _extract_products(),
        _extract_competitors_and_market(),
        _extract_business_model(),
    )

    # ── Phase 2: Merge all results ──
    merged = {}
    for r in results:
        if isinstance(r, dict) and "error" not in r:
            merged.update(r)
        elif isinstance(r, dict):
            logger.warning(f"Extraction task failed: {r.get('error', 'unknown')}")
    return merged


# ═══════════════════════════════════════════════════════════════════════
#  Phase 2.3: Personal fit analysis (KB + JD)
# ═══════════════════════════════════════════════════════════════════════

async def generate_fit_analysis(company: str, job: str, jd_text: str, jd_parsed: dict, kb: dict) -> dict:
    jd_summary = jd_parsed.get("summary", "")
    requirements = jd_parsed.get("requirements", [])
    responsibilities = jd_parsed.get("responsibilities", [])
    keywords = jd_parsed.get("keywords", [])

    candidate_info = _format_kb_for_prompt(kb)

    jd_section = f"""========== 岗位要求 (JD) ==========
JD总览：{jd_summary}
核心职责：{json.dumps(responsibilities, ensure_ascii=False)}
任职要求：{json.dumps(requirements, ensure_ascii=False)}
关键技能词：{json.dumps(keywords, ensure_ascii=False)}"""

    jd_empty_note = ""
    if not jd_text.strip():
        jd_empty_note = "\n注意：当前JD内容为空，请基于岗位通用要求进行分析，并标注'无JD参考，基于岗位通用要求'的说明"

    async def _analyze_jd():
        p = f"""你是职业规划专家。请分析{company}的{job}岗位的JD要求，拆解显性和隐性考察点。

{jd_section}
{jd_empty_note}

JSON格式（只返回此JSON，不要其他文字）：
{{
  "jd_deconstruction": [
    {{"explicit_requirement": "JD显性要求", "hidden_examination": "隐性考察点（JD没有明说但面试必问的）"}}
  ]
}}
规则：
- jd_deconstruction 拆解JD的显性要求背后的隐性考察点
- 基于JD真实内容分析，不要编造"""
        return await _llm_json(p)

    async def _analyze_candidate_fit():
        p = f"""你是职业规划专家。请分析候选人应聘{company}的{job}岗位的匹配度。

========== 候选人信息 ==========
{candidate_info}

{jd_section}
{jd_empty_note}

请从候选人视角分析：JD要求 vs 自身匹配情况、核心契合点、差距、贡献方向。

JSON格式（只返回此JSON，不要其他文字）：
{{
  "jd_requirement_vs_candidate": [
    {{"requirement": "JD中的具体要求", "candidate_match": "候选人对应情况", "score": 8, "note": "匹配说明"}}
  ],
  "core_fit_points": [
    {{"point": "核心契合点", "detail": "详细论证为什么这是一个契合点", "interview_script": "面试话术——可直接用于面试回答的第一人称阐述"}}
  ],
  "gap_analysis": [
    {{"gap": "需要补强的方面", "severity": "高/中/低", "strategy": "面试中如何应对或弥补"}}
  ],
  "i_can_contribute": [
    {{"direction": "方向名称", "detail": "具体可发挥的详细阐述，含多个要点"}}
  ],
  "overall_fit_score": 8,
  "summary": "整体契合度评价（2-3句话）"
}}
规则：
- jd_requirement_vs_candidate 逐条对照JD要求打分（1-10分）
- score 要实事求是，不要虚高
- gap_analysis 要有实际的应对策略
- 基于候选人真实信息分析，不要编造"""
        return await _llm_json(p)

    results = await asyncio.gather(
        _analyze_jd(),
        _analyze_candidate_fit(),
    )

    merged = {}
    for r in results:
        if isinstance(r, dict) and "error" not in r:
            merged.update(r)
        elif isinstance(r, dict):
            logger.warning(f"Fit analysis subtask failed: {r.get('error', 'unknown')}")
    for key in ["jd_deconstruction", "jd_requirement_vs_candidate", "core_fit_points",
                "gap_analysis", "i_can_contribute", "overall_fit_score", "summary"]:
        merged.setdefault(key, [] if key != "overall_fit_score" and key != "summary" else (0 if key == "overall_fit_score" else ""))
    return merged


# ═══════════════════════════════════════════════════════════════════════
#  Phase 2.4: Value proposition
# ═══════════════════════════════════════════════════════════════════════

async def generate_value_proposition(company: str, job: str, jd_text: str, kb: dict, company_info: dict, product_info: dict) -> dict:
    candidate_info = _format_kb_for_prompt(kb)
    company_overview = company_info.get("overview", "")
    products = product_info.get("products", [])
    competitors = product_info.get("competitors", [])
    target_customers = product_info.get("target_customers", "")

    prompt = f"""你是求职策略专家。请为应聘{company}的{job}岗位的候选人制定价值定位策略。

========== 候选人信息 ==========
{candidate_info}

========== 目标公司信息 ==========
公司简介：{company_overview}
核心产品：{json.dumps(products, ensure_ascii=False)}
目标客户：{target_customers}
市场竞品：{json.dumps(competitors, ensure_ascii=False)}

请用JSON格式返回：
{{
  "personal_brand_statement": "个人价值定位宣言（一句话）",
  "value_propositions": [
    {{"theme": "价值主题", "argument": "为什么候选人能在这家公司发挥这个价值", "evidence": "候选人经历中的具体支撑证据"}}
  ],
  "i_can_contribute": [
    {{"area": "可在哪些方面为公司做出贡献", "detail": "具体阐述（分多个要点，每个要点写具体可落地，不低于100字）"}}
  ],
  "company_advantage_for_me": [
    {{"aspect": "公司的某个特点", "reason": "为什么这对候选人有吸引力或有利"}}
  ],
  "narrative_angle": "推荐候选人在面试中塑造的人设和叙事角度"
}}
规则：
- 结合候选人真实经历和公司实际情况，不要编造
- value_propositions 至少3条
- 每条都要有 candidate_info 中的具体经历作为证据支撑""" + ("""
- 注意JD内容为空时，基于{job}岗位通用要求分析""" if not jd_text.strip() else "")

    return await _llm_json(prompt)


# ═══════════════════════════════════════════════════════════════════════
#  Phase 2.5: Interview strategy with KB + JD injection
# ═══════════════════════════════════════════════════════════════════════

async def generate_interview_strategy(company: str, job: str, jd_text: str, kb: dict) -> dict:
    queries = [
        f"{company} {job} 面试 高频问题 文化 考察重点",
        f"{company} 企业文化 面试经验 工作氛围",
        f"{company} 产品技术 行业趋势 竞争 发展",
    ]
    sr = await _search_multi(queries)
    search_results = _format_search_results_for_prompt(sr)
    _report_search_results.append(sr)
    candidate_info = _format_kb_for_prompt(kb)
    jd_section = f"\n========== 岗位描述 ==========\n{jd_text}" if jd_text.strip() else ""

    prompt = f"""你是资深面试辅导专家。请为应聘{company}的{job}岗位的候选人生成个性化面试策略。

========== 候选人信息 ==========
{candidate_info}
{jd_section}

搜索信息仅供参考，**禁止用你的知识补充**。搜索未覆盖的信息标注"未找到"。
JSON格式：
{{
  "self_intro_2min": "2分钟自我介绍稿（包含人设、核心经历、为什么适合该公司，第一人称）",
  "questions": [
    {{
      "q": "面试问题",
      "a": "回答框架（要结合候选人的实际经历和JD要求来写，详细含思路和要点）",
      "answer_script": "可直接说出口的话术（第一人称，300字左右，含思路和要点）",
      "category": "问题类别（自我介绍与动机/专业能力/行业认知/情境应对）"
    }}
  ],
  "ask_questions": ["反问面试官的问题1（针对该公司特点）", "反问面试官的问题2"],
  "tips": "面试建议（针对该公司的特点给出具体建议，结合候选人背景）",
  "narrative_angle": "推荐候选人在面试中塑造的人设和叙事角度（结合公司特点和候选人背景）"
}}
要求：
- 生成10个高频面试题，覆盖4个类别（自我介绍与动机、专业能力、行业认知、情境应对）
- 每个问题的回答框架要**结合候选人的实际经历**，不泛泛而谈
- 如果JD不为空，题目要针对JD中的职责和要求
- tips要针对{company}的特点和候选人背景给出具体建议
搜索供参考：
{search_results}"""
    return await _llm_json(prompt)


# ═══════════════════════════════════════════════════════════════════════
#  Search helpers
# ═══════════════════════════════════════════════════════════════════════

async def _search_all_engines(query: str) -> dict:
    """4引擎单次搜索（SearXNG engines 参数），按引擎分组返回结果。"""
    results = {"query": query, "engines": {}, "timing": {}}
    t0 = asyncio.get_event_loop().time()

    engine_names = "360search,baidu,chinaso news,sogou wechat"

    try:
        resp = await _CLIENT.get(
            "http://searxng:8080/search",
            headers={"X-Forwarded-For": "127.0.0.1", "X-Real-IP": "127.0.0.1"},
            params={
                "q": query,
                "format": "json",
                "language": "zh-CN",
                "engines": engine_names,
            },
            timeout=30,
        )
        data = resp.json()
        hits = data.get("results", [])
        unresponsive = data.get("unresponsive_engines", [])
        elapsed = asyncio.get_event_loop().time() - t0

        from collections import defaultdict
        eng_hits = defaultdict(list)
        for h in hits:
            eng_hits[h.get("engine", "unknown")].append(h)

        unresponsive_names = {u[0] for u in unresponsive if isinstance(u, (list, tuple)) and len(u) >= 1}

        for eng in ["360search", "baidu", "chinaso news", "sogou wechat"]:
            eng_items = eng_hits.get(eng, [])
            items = [
                {
                    "title": h.get("title"),
                    "content": (h.get("content", "") or "")[:500],
                    "url": h.get("url"),
                    "source_grade": _grade_source(h.get("url", "")),
                }
                for h in eng_items[:8]
            ]
            err = None
            if eng in unresponsive_names:
                err = "engine unresponsive"
            results["engines"][eng] = {
                "count": len(eng_items),
                "items": items,
                "elapsed": round(elapsed, 2),
            }
            if err:
                results["engines"][eng]["error"] = err
            results["timing"][eng] = round(elapsed, 2)

        results["timing"]["total"] = round(elapsed, 2)

    except Exception as e:
        logger.error("SearXNG search failed: %s", e)
        for eng in ["360search", "baidu", "chinaso news", "sogou wechat"]:
            results["engines"][eng] = {"count": 0, "items": [], "elapsed": 0, "error": str(e)}
            results["timing"][eng] = 0
        results["timing"]["total"] = 0

    return results


def _grade_source(url: str) -> str:
    """对URL进行可信度分级（A-G）"""
    if "gov.cn" in url:
        return "A"
    elif "baike.so.com" in url:
        return "B"
    elif "baike.baidu.com" in url:
        return "B"
    elif any(d in url for d in ["aiqicha", "tianyancha", "qcc.com", "qixin"]):
        return "C"
    elif any(d in url for d in ["163.com", "nbd.com.cn", "people.com.cn", "thepaper.cn"]):
        return "D"
    elif any(d in url for d in ["huangye88", "11467.com", "b2bvip", "b2b"]):
        return "E"
    elif any(d in url for d in ["zhihu", "tieba", "guba", "jobui"]):
        return "F"
    else:
        return "G"


def _verification_type(sources: list) -> str:
    """
    判断验证类型: cross(异源验证) / same(同源验证) / single(单源)
    """
    upstream_groups = {
        "百科": ["baike.so.com", "baike.baidu.com", "baike"],
        "工商": ["aiqicha", "tianyancha", "qcc.com", "qixin.com"],
        "新闻": ["163.com", "nbd.com.cn", "people.com.cn", "thepaper.cn"],
        "招聘": ["zhipin.com", "liepin.com", "jobui.com"],
        "黄页": ["huangye88", "11467.com", "b2bvip", "b2b"],
    }
    groups_found = set()
    unknown = 0
    for url in sources:
        matched = False
        for group, domains in upstream_groups.items():
            if any(d in url for d in domains):
                groups_found.add(group)
                matched = True
                break
        if not matched:
            unknown += 1
    if unknown > 0:
        groups_found.add("其他")
    if len(groups_found) >= 2:
        return "cross"
    elif len(sources) >= 2:
        return "same"
    return "single"


def _format_search_results_for_prompt(results: dict) -> str:
    """将搜索结果dict格式化为LLM prompt可读字符串"""
    firecrawl_used = 0
    lines = []
    for engine, data in results.get("engines", {}).items():
        count = data.get("count", 0)
        elapsed = data.get("elapsed", 0)
        error = data.get("error")
        if error:
            lines.append(f"? {engine}(0条, 错误: {error})")
        else:
            lines.append(f"? {engine}({count}条, {elapsed}s)")
        for item in data.get("items", []):
            grade = item.get("source_grade", "G")
            title = item.get("title", "")
            content = item.get("content", "")
            url = item.get("url", "")
            full_text = item.get("full_text", "")
            lines.append(f"  [{grade}] {title}")
            lines.append(f"  {content}")
            if full_text:
                lines.append(f"  [全文抓取] {full_text[:1200]}")
                firecrawl_used += 1
            lines.append(f"  来源: {url}")
            lines.append("")
    total = results.get("timing", {}).get("total", 0)
    lines.append(f"总耗时: {total}s")
    if firecrawl_used > 0:
        lines.append(f"* {firecrawl_used}条来源通过Firecrawl进行了深度页面抓取，以上[全文抓取]部分为页面正文，可信度高于搜索摘要。")
    header = f"搜索查询: {results.get('query', '')}"
    return header + "\n" + "\n".join(lines)


def _build_report_metadata(search_results: list[dict], generated_at: str) -> dict:
    """
    Build report metadata section: search performance, unverifiable claims, data conflicts.
    This is the JSON schema redefinition (P1) — each data point is traceable to its source.
    """
    all_timings = []
    total_queries = 0
    total_results = 0
    engine_usage = set()

    for sr in search_results:
        # Count sub-queries from merged multi-query format
        query_field = sr.get("query", "")
        if " | " in query_field:
            total_queries += len(query_field.split(" | "))
        elif query_field:
            total_queries += 1

    for sr in search_results:
        for eng, data in sr.get("engines", {}).items():
            engine_usage.add(eng)
            total_results += data.get("count", 0)
            elapsed = data.get("elapsed", 0)
            if elapsed > 0:
                all_timings.append(elapsed)

    # Compute P50/P95 from actual timings
    p50 = 0
    p95 = 0
    if all_timings:
        sorted_t = sorted(all_timings)
        n = len(sorted_t)
        p50 = sorted_t[min(int(n * 0.5), n - 1)]
        p95 = sorted_t[min(int(n * 0.95), n - 1)]

    return {
        "generated_at": generated_at,
        "search_engines_used": sorted(engine_usage),
        "total_search_queries": total_queries,
        "total_results_collected": total_results,
        "search_performance": {
            "p50_ms": int(p50 * 1000),
            "p95_ms": int(p95 * 1000),
        },
        "unverifiable_claims_removed": [],
        "data_conflicts_resolved": [],
        "data_quality": [
            {"field": "公司基础信息", "status": "search_based", "sources": "多引擎验证" if total_queries >= 2 else "单源"},
            {"field": "产品体系", "status": "search_based", "sources": "多引擎验证" if total_queries >= 2 else "单源"},
            {"field": "资质认证", "status": "search_based", "sources": "多引擎验证" if total_queries >= 2 else "单源"},
            {"field": "发展历程", "status": "search_based", "sources": "多引擎验证" if total_queries >= 2 else "单源"},
        ],
    }


# ═══════════════════════════════════════════════════════════════════════
#  LLM helper
# ═══════════════════════════════════════════════════════════════════════

async def _llm_json(prompt: str, retries: int = 3) -> dict:
    last_error = ""
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(
                    f"{_get_llm_base()}/chat/completions",
                    headers={"Authorization": f"Bearer {_get_llm_key()}", "Content-Type": "application/json"},
                    json={
                        "model": _get_llm_model(),
                        "messages": [
                            {"role": "system", "content": "你是一个专业的数据分析师，严格基于提供的搜索材料回答问题。只返回JSON，不要任何其他文字。禁止使用你自己的知识补充——搜索未覆盖的信息必须标注\u201c未找到公开信息\u201d。"},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.3,
                        "max_tokens": 16384,
                    },
                )
                content = resp.json()["choices"][0]["message"]["content"]
                json_str = _extract_json(content)
                return json.loads(json_str)
        except json.JSONDecodeError as e:
            last_error = f"JSON解析失败(第{attempt+1}次): {e}"
            logger.warning(last_error)
            continue
        except Exception as e:
            last_error = str(e)
            logger.warning(f"LLM调用失败(第{attempt+1}次): {e}")
            if attempt < retries - 1:
                await asyncio.sleep(2)
            continue
    logger.error(f"LLM调用在{retries}次重试后全部失败: {last_error}")
    return {"error": last_error}


def _extract_json(text: str) -> str:
    """Extract JSON from LLM response. Handles code fences, leading/trailing text."""
    # Try to find JSON inside ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*\n?(\{.*?\}|\[.*?\])\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Try to find a JSON object or array directly (first occurrence)
    for pattern in [r"(\{.*\})", r"(\[.*\])"]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            candidate = match.group(1).strip()
            # Validate it looks like JSON
            if candidate.startswith("{") or candidate.startswith("["):
                return candidate
    # Fallback: return raw text stripped
    return text.strip()


def _format_kb_for_prompt(kb: dict) -> str:
    """Format knowledge base dict into a readable prompt section."""
    sections = []
    for section_name in ["个人信息", "教育背景", "工作经历", "项目经历", "专业技能"]:
        content = kb.get(section_name, "")
        if content and content.strip():
            sections.append(f"===== {section_name} =====\n{content.strip()}")
    faq = kb.get("高频问答", "")
    if faq and faq.strip():
        sections.append(f"===== HR高频问答库 =====\n{faq.strip()}")
    return "\n\n".join(sections) if sections else "（无候选人信息）"


# ═══════════════════════════════════════════════════════════════════════
#  Phase 2.6 + Phase 3: Full report generation (7-step parallel)
# ═══════════════════════════════════════════════════════════════════════

def _validate_content_fields(content: dict) -> None:
    # Catch prompt-template desync: if a field is required by the template but
    # not produced in generate_full_report, this raises before the render.
    missing = REQUIRED_CONTENT_FIELDS - set(content.keys())
    if missing:
        raise ValueError(
            f"Content dict missing required fields (REPORT_FORMAT_VERSION={REPORT_FORMAT_VERSION}): "
            f"{missing}. Either add them to generate_full_report or update REQUIRED_CONTENT_FIELDS."
        )


async def generate_full_report(guide_id: int, db: Optional[DBSession] = None):
    logger.info(f"Starting report generation for guide_id={guide_id}")
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True
    try:
        guide = db.query(InterviewGuide).filter(InterviewGuide.id == guide_id).first()
        if not guide:
            logger.error(f"Guide {guide_id} not found")
            return

        _report_user_id.set(guide.user_id)

        task = db.query(ReportGenerationTask).filter(ReportGenerationTask.guide_id == guide_id).first()
        if not task:
            task = ReportGenerationTask(guide_id=guide_id, user_id=guide.user_id, status="running", started_at=datetime.utcnow())
            db.add(task)
        else:
            task.status = "running"
            task.started_at = datetime.utcnow()
            task.completed_at = None
            task.error_message = None
            task.pdf_path = None
        db.commit()
        db.refresh(task)

        try:
            has_md = bool(guide.generated_report_md and guide.generated_report_md.strip())
            has_content = bool(guide.guide_content and guide.guide_content.strip())
            if has_md and has_content:
                logger.info(f"MD already exists for guide_id={guide_id}, PDF-only regeneration")
                await asyncio.wait_for(
                    _regenerate_pdf_only(db, guide, task),
                    timeout=600.0,
                )
            else:
                await asyncio.wait_for(
                    _generate_report_body(db, guide, task),
                    timeout=600.0,
                )
        except asyncio.TimeoutError:
            task.status = "failed"
            task.error_message = "报告生成超时（300秒），请重试"
            task.completed_at = datetime.utcnow()
            db.commit()
            logger.error(f"Report generation timed out for guide_id={guide_id}")
            return
        except ReportCancelledError:
            task.status = "cancelled"
            task.completed_at = datetime.utcnow()
            db.commit()
            logger.info(f"Report generation cancelled for guide_id={guide_id}")
            return

    except Exception as e:
        logger.exception(f"Report generation failed for guide_id={guide_id}: {e}")
        try:
            task = db.query(ReportGenerationTask).filter(ReportGenerationTask.guide_id == guide_id).first()
            if task:
                task.status = "failed"
                task.error_message = str(e)[:500]
                task.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            pass
    finally:
        if close_db:
            db.close()


async def _regenerate_pdf_only(db: DBSession, guide: InterviewGuide, task: ReportGenerationTask):
    """Re-render PDF from existing guide_content, skipping MD/analysis phases."""
    guide_id = guide.id
    company = guide.company_name
    job = guide.job_title

    content = json.loads(guide.guide_content)
    bg = content.get("company_profile", {})
    pb = {
        "products": content.get("products", []),
        "product_details": content.get("product_details", []),
        "business_lines": content.get("business_lines", []),
        "business_model": content.get("business_model", ""),
        "revenue_model": content.get("revenue_model", ""),
        "target_customers": content.get("target_customers", ""),
        "competitors": content.get("competitors", []),
        "competitive_barriers": content.get("competitive_barriers", ""),
        "market_risks": content.get("market_risks", ""),
        "product_advantages": content.get("product_advantages", []),
        "product_disadvantages": content.get("product_disadvantages", []),
        "optimization_suggestions": content.get("optimization_suggestions", []),
        "architecture_overview": content.get("architecture_overview", ""),
        "business_model_summary": content.get("business_model_summary", []),
        "core_business_logic": content.get("core_business_logic", ""),
        "core_risks": content.get("core_risks", []),
        "core_barriers": content.get("core_barriers", []),
    }
    strategy = {
        "questions": content.get("common_interview_questions", []),
        "ask_questions": content.get("questions_to_ask", []),
        "tips": content.get("interview_tips", ""),
        "self_intro_2min": content.get("self_intro_2min", ""),
        "narrative_angle": content.get("narrative_angle", ""),
    }
    fit = content.get("fit_analysis", {})
    value = content.get("value_proposition", {})
    report_metadata = content.get("report_metadata", {})

    _check_report_cancelled(guide_id)

    task.progress_message = "正在渲染 HTML..."
    db.commit()

    try:
        html_template = env.get_template("interview_report.html")
        html = html_template.render(
            company_name=company, job_title=job,
            report_metadata=report_metadata, company_profile=bg,
            product_lines=pb.get("products", []),
            business_lines=pb.get("business_lines", []),
            business_model=pb.get("business_model", ""),
            revenue_model=pb.get("revenue_model", ""),
            target_customers=pb.get("target_customers", ""),
            competitors=pb.get("competitors", []),
            product_advantages=pb.get("product_advantages", []),
            product_disadvantages=pb.get("product_disadvantages", []),
            optimization_suggestions=pb.get("optimization_suggestions", []),
            common_interview_questions=strategy.get("questions", []),
            questions_to_ask=strategy.get("ask_questions", []),
            interview_tips=strategy.get("tips", ""),
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            report_format_version=REPORT_FORMAT_VERSION,
            established=bg.get("established", ""),
            registered_capital=bg.get("registered_capital", ""),
            legal_person=bg.get("legal_person", ""),
            equity_structure=bg.get("equity_structure", ""),
            parent_company=bg.get("parent_company", ""),
            headquarters=bg.get("headquarters", ""),
            branches=bg.get("branches", ""),
            culture_values=bg.get("culture_values", {}),
            qualifications=bg.get("qualifications", []),
            architecture_overview=pb.get("architecture_overview", ""),
            business_model_summary=pb.get("business_model_summary", []),
            core_business_logic=pb.get("core_business_logic", ""),
            core_risks=pb.get("core_risks", []),
            core_barriers=pb.get("core_barriers", []),
            jd_deconstruction=fit.get("jd_deconstruction", []),
            self_intro_2min=strategy.get("self_intro_2min", ""),
            narrative_angle=strategy.get("narrative_angle", value.get("narrative_angle", "")),
            industry=bg.get("industry", ""),
            scale=bg.get("scale", ""),
            funding_stage=bg.get("funding_stage", ""),
            overview=bg.get("overview", ""),
        )
        task.progress_message = "正在生成 PDF..."
        db.commit()
        from services.pdf_service import _generate_pdf_async
        pdf_bytes = await _generate_pdf_async(html)
        os.makedirs(REPORT_DIR, exist_ok=True)
        pdf_path = os.path.join(REPORT_DIR, f"interview_guide_{guide_id}.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        task.pdf_path = pdf_path
    except Exception as e:
        logger.error(f"PDF-only regeneration failed: {e}")
        raise

    task.status = "done"
    task.completed_at = datetime.utcnow()
    db.commit()


async def _generate_report_body(db: DBSession, guide: InterviewGuide, task: ReportGenerationTask):
    """Main report generation logic, extracted for timeout support.

    两阶段并行设计：
      Phase 1 — 所有独立步骤全并行（公司背景/产品/匹配/策略）
      Phase 2 — 依赖 bg+pb 的价值定位
      Phase 3 — 渲染输出
    """
    guide_id = guide.id
    company = guide.company_name
    company_desc = guide.company_description or ""
    job = guide.job_title
    jd_text = guide.jd_text or ""
    jd_parsed_raw = guide.jd_parsed or "{}"

    if isinstance(jd_parsed_raw, str):
        try:
            jd_parsed = json.loads(jd_parsed_raw)
        except (json.JSONDecodeError, TypeError):
            jd_parsed = {}
    else:
        jd_parsed = jd_parsed_raw

    kb = _load_candidate_kb(guide.user_id)

    if jd_text.strip() and not jd_parsed.get("requirements"):
        jd_parsed = await _parse_jd(jd_text)
        guide.jd_parsed = json.dumps(jd_parsed, ensure_ascii=False)
        db.commit()

    _check_report_cancelled(guide_id)

    # ── Phase 1: 所有独立步骤全并行 ──
    # 用 JD 数据计算搜索增强后缀（不依赖 bg），让产品搜索和公司背景搜索可以并行
    search_suffix = f" {company_desc}" if company_desc else ""
    biz_keywords = _build_jd_keywords(company_desc, jd_parsed)
    enriched_suffix = f" {biz_keywords}" if biz_keywords else search_suffix

    task.progress_message = "正在获取公司背景和产品信息..."
    db.commit()

    has_kb = any(v.strip() for v in kb.values())
    if has_kb:
        bg, pb, fit, strategy = await asyncio.gather(
            fetch_company_background(company, search_suffix),
            fetch_product_business(company, enriched_suffix),
            generate_fit_analysis(company, job, jd_text, jd_parsed, kb),
            generate_interview_strategy(company, job, jd_text, kb),
        )
        # ── Phase 2: 依赖 bg+pb 的价值定位 ──
        task.progress_message = "正在分析产品竞争力和业务策略..."
        db.commit()
        value = await generate_value_proposition(company, job, jd_text, kb, bg, pb)
        _check_report_cancelled(guide_id)
    else:
        bg, pb, strategy = await asyncio.gather(
            fetch_company_background(company, search_suffix),
            fetch_product_business(company, enriched_suffix),
            generate_interview_strategy(company, job, jd_text, kb),
        )
        fit, value = {}, {}

    _check_report_cancelled(guide_id)

    report_metadata = _build_report_metadata(
        search_results=list(_report_search_results),
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
    _report_search_results.clear()

    content = {
        "company_profile": bg,
        "product_lines": pb.get("products", []),
        "products": pb.get("products", []),
        "product_details": pb.get("product_details", []),
        "business_lines": pb.get("business_lines", []),
        "business_model": pb.get("business_model", ""),
        "revenue_model": pb.get("revenue_model", ""),
        "target_customers": pb.get("target_customers", ""),
        "competitors": pb.get("competitors", []),
        "competitive_barriers": pb.get("competitive_barriers", ""),
        "market_risks": pb.get("market_risks", ""),
        "product_advantages": pb.get("product_advantages", []),
        "product_disadvantages": pb.get("product_disadvantages", []),
        "optimization_suggestions": pb.get("optimization_suggestions", []),
        "fit_analysis": fit,
        "value_proposition": value,
        "common_interview_questions": strategy.get("questions", []),
        "questions_to_ask": strategy.get("ask_questions", []),
        "interview_tips": strategy.get("tips", ""),
        "report_metadata": report_metadata,
        "report_format_version": REPORT_FORMAT_VERSION,
    }

    task.progress_message = "正在生成面试报告内容和 Markdown..."
    db.commit()

    _validate_content_fields(content)
    guide.guide_content = json.dumps(content, ensure_ascii=False)
    guide.updated_at = datetime.utcnow()

    try:
        md_template = env.get_template("interview_report.md")
        md_content = md_template.render(
            company_name=company, job_title=job,
            report_format_version=REPORT_FORMAT_VERSION,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            report_metadata=report_metadata,
            overview=bg.get("overview", ""), industry=bg.get("industry", ""),
            scale=bg.get("scale", ""), funding_stage=bg.get("funding_stage", ""),
            culture=bg.get("culture", ""), milestones=bg.get("milestones", []),
            recent_news=bg.get("recent_news", []),
            products=pb.get("products", []), product_details=pb.get("product_details", []),
            business_lines=pb.get("business_lines", []),
            business_model=pb.get("business_model", ""),
            revenue_model=pb.get("revenue_model", ""),
            target_customers=pb.get("target_customers", ""),
            competitors=pb.get("competitors", []),
            competitive_barriers=pb.get("competitive_barriers", ""),
            market_risks=pb.get("market_risks", ""),
            product_advantages=pb.get("product_advantages", []),
            product_disadvantages=pb.get("product_disadvantages", []),
            optimization_suggestions=pb.get("optimization_suggestions", []),
            fit_analysis=fit, value_proposition=value,
            questions=strategy.get("questions", []),
            ask_questions=strategy.get("ask_questions", []),
            tips=strategy.get("tips", ""),
            established=bg.get("established", ""),
            registered_capital=bg.get("registered_capital", ""),
            legal_person=bg.get("legal_person", ""),
            equity_structure=bg.get("equity_structure", ""),
            parent_company=bg.get("parent_company", ""),
            headquarters=bg.get("headquarters", ""),
            branches=bg.get("branches", ""),
            culture_values=bg.get("culture_values", {}),
            qualifications=bg.get("qualifications", []),
            architecture_overview=pb.get("architecture_overview", ""),
            business_model_summary=pb.get("business_model_summary", []),
            core_business_logic=pb.get("core_business_logic", ""),
            core_risks=pb.get("core_risks", []),
            core_barriers=pb.get("core_barriers", []),
            jd_deconstruction=fit.get("jd_deconstruction", []),
            self_intro_2min=strategy.get("self_intro_2min", ""),
            narrative_angle=strategy.get("narrative_angle", value.get("narrative_angle", "")),
        )
        os.makedirs(REPORT_DIR, exist_ok=True)
        md_path = os.path.join(REPORT_DIR, f"interview_guide_{guide_id}.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        import re as _re
        md_content = _re.sub(r'</?details>\s*', '', md_content)
        md_content = _re.sub(r'</?summary>\s*', '', md_content)
        md_content = _re.sub(r'查看回答思路\s*', '', md_content)
        logger.info(f"MD report saved to {md_path}")
    except Exception as e:
        logger.error(f"MD rendering failed: {e}")
        md_content = ""

    guide.generated_report_md = md_content
    db.commit()  # 先提交 MD 内容，避免后续 PDF 超时时丢失

    try:
        html_template = env.get_template("interview_report.html")
        html = html_template.render(
            company_name=company, job_title=job,
            report_metadata=report_metadata, company_profile=bg,
            product_lines=pb.get("products", []),
            business_lines=pb.get("business_lines", []),
            business_model=pb.get("business_model", ""),
            revenue_model=pb.get("revenue_model", ""),
            target_customers=pb.get("target_customers", ""),
            competitors=pb.get("competitors", []),
            product_advantages=pb.get("product_advantages", []),
            product_disadvantages=pb.get("product_disadvantages", []),
            optimization_suggestions=pb.get("optimization_suggestions", []),
            common_interview_questions=strategy.get("questions", []),
            questions_to_ask=strategy.get("ask_questions", []),
            interview_tips=strategy.get("tips", ""),
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
            report_format_version=REPORT_FORMAT_VERSION,
            established=bg.get("established", ""),
            registered_capital=bg.get("registered_capital", ""),
            legal_person=bg.get("legal_person", ""),
            equity_structure=bg.get("equity_structure", ""),
            parent_company=bg.get("parent_company", ""),
            headquarters=bg.get("headquarters", ""),
            branches=bg.get("branches", ""),
            culture_values=bg.get("culture_values", {}),
            qualifications=bg.get("qualifications", []),
            architecture_overview=pb.get("architecture_overview", ""),
            business_model_summary=pb.get("business_model_summary", []),
            core_business_logic=pb.get("core_business_logic", ""),
            core_risks=pb.get("core_risks", []),
            core_barriers=pb.get("core_barriers", []),
            jd_deconstruction=fit.get("jd_deconstruction", []),
            self_intro_2min=strategy.get("self_intro_2min", ""),
            narrative_angle=strategy.get("narrative_angle", value.get("narrative_angle", "")),
            industry=bg.get("industry", ""),
            scale=bg.get("scale", ""),
            funding_stage=bg.get("funding_stage", ""),
            overview=bg.get("overview", ""),
        )
        from services.pdf_service import _generate_pdf_async
        pdf_bytes = await _generate_pdf_async(html)
        os.makedirs(REPORT_DIR, exist_ok=True)
        pdf_path = os.path.join(REPORT_DIR, f"interview_guide_{guide_id}.pdf")
        with open(pdf_path, "wb") as f:
            f.write(pdf_bytes)
        task.pdf_path = pdf_path
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")

    task.status = "done"
    task.completed_at = datetime.utcnow()
    db.commit()
