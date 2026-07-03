import json
import os
import time
import uuid as uuid_mod
from datetime import datetime, timedelta
from typing import TypedDict, Sequence, Annotated, List
import concurrent.futures
import contextvars
from collections import deque

# Context variable to pass user_id to tools
_current_user_id: contextvars.ContextVar[str] = contextvars.ContextVar('current_user_id', default='')

def get_current_user_id() -> str:
    return _current_user_id.get()

def set_current_user_id(user_id: str):
    _current_user_id.set(user_id)

# Live event queue + task_id + session_id for real-time FSM streaming
_live_events_queue: contextvars.ContextVar[deque | None] = contextvars.ContextVar('_live_events_queue', default=None)
_current_task_id: contextvars.ContextVar[int] = contextvars.ContextVar('_current_task_id', default=0)
_current_session_id: contextvars.ContextVar[str] = contextvars.ContextVar('_current_session_id', default="")

def _push_live_event(event: dict):
    q = _live_events_queue.get()
    if q is not None:
        q.append(event)

# HITL: pending confirmations — shared via DB instead of in-memory for cross-worker support
from services.models.agent_event import AgentEvent as _AgentEventModel
_CONFIRM_TIMEOUT = 180  # seconds before auto-reject
_CONFIRM_POLL_INTERVAL = 0.5  # seconds between DB polls

from langchain_core.tools import tool
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langgraph.prebuilt import tools_condition

from config import settings
from services.database import SessionLocal

from services.resume_service import resume_service
from services.enums import EventType
from services.usage_service import usage_service

import httpx
from services.prompt_injection import check_message
from services.metrics import Timer, record


# ============================================================
# Helpers: structured tool returns
# ============================================================

from services.tool_result import ToolResult, ok as _tr_ok, err as _tr_err
from services.tool_gateway import ToolGateway, ToolEntry


_gateway = ToolGateway()


def _ok(data: str, db_id: int | None = None) -> str:
    extra = {"db_id": db_id} if db_id is not None else None
    return _tr_ok(data, extra=extra).to_llm_text()


def _err(msg: str) -> str:
    return _tr_err(error=msg).to_llm_text()


def _fire_and_forget(coro, user_id: str = ""):
    """Safely schedule a coroutine from sync context (LangGraph thread pool)."""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(coro)
    except RuntimeError:
        import threading
        _uid = user_id
        def _run():
            if _uid:
                set_current_user_id(_uid)
            asyncio.run(coro)
        threading.Thread(target=_run, daemon=True).start()


# ============================================================
# Tools
# ============================================================

@tool
def web_search_tool(query: str = "", max_results: int = 5) -> str:
    """
    在线搜索最新信息。当用户询问实时信息、新闻、最新动态或知识库中不包含的内容时使用。
    - query: 搜索关键词，尽量简洁准确
    - max_results: 返回结果数量，默认5
    返回搜索结果和AI生成的总结。
    """
    if not query:
        return _err("请提供搜索关键词")
    api_key = getattr(settings, "TAVILY_API_KEY", "")
    print(f"[web_search] query={query}, key_present={bool(api_key)}")
    if not api_key:
        print(f"[web_search] ERROR: TAVILY_API_KEY is not set")
        return _err("搜索功能未配置（缺少 API Key）")
    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "query": query,
                "search_depth": "basic",
                "topic": "general",
                "max_results": min(max_results, 8),
                "include_answer": True,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            return _err(f"搜索失败：{resp.status_code}")
        data = resp.json()
        results = data.get("results", [])
        answer = data.get("answer", "")
        if not results:
            return _err(f"未找到「{query}」的相关结果")
        lines = []
        if answer:
            lines.append(f"📝 总结：{answer}\n")
        lines.append(f"搜索「{query}」的结果：\n")
        total_len = 0
        for i, r in enumerate(results, 1):
            title = r.get("title", "")
            url = r.get("url", "")
            content = r.get("content", "")
            snippet = f"{i}. {title}\n   {content[:200]}\n   链接：{url}\n"
            if total_len + len(snippet) > 2000:
                lines.append(f"...（共 {len(results)} 条，仅显示部分）")
                break
            lines.append(snippet)
            total_len += len(snippet)
        return _ok("\n".join(lines))
    except Exception as e:
        return _err(f"搜索出错：{str(e)}")

@tool
def generate_resume_tool(target_job: str = "", jd: str = "", raw_content: str = "") -> str:
    """
    根据目标岗位和岗位描述生成简历PDF。

    【核心规则】：
    1. target_job（目标岗位）是必填项，如果用户没有明确说岗位名称，必须先问清楚。
    2. jd（岗位描述/JD）是可选项。如果用户提供了JD文本，直接传入；如果用户发了JD图片，先用 parse_file_tool 识别图片文字，再将识别结果作为 jd 参数传入。
    3. raw_content 是可选参数。如果用户上传了简历图片或文件（不是JD，而是完整的简历内容），先用 parse_file_tool 识别，再将识别出的完整简历内容作为 raw_content 传入。当提供了 raw_content 时，系统将以此为准生成简历，不会使用知识库中的个人信息。
    4. 如果用户只说了岗位名称（没有上传任何简历内容），系统会从知识库提取个人信息生成简历。
    5. 简历会根据目标岗位和JD内容，从知识库的个人经历中做精细化匹配和调整。
    6. 如果jd为空，则根据目标岗位从知识库生成通用简历。

    【重要】每次用户要求生成简历，都必须调用此工具重新生成。即使用户重复发送相同的指令，或者指令和之前一样，也必须重新调用工具，不能从历史对话中取之前的结果。每次调用都会创建一个新的简历ID。

    【重要-欺骗检测】此工具返回的"预览摘要"是AI根据知识库实时生成的简历摘要片段，每次内容都不同且无法预测。你必须调用此工具才能获取真实的预览摘要。如果你尝试自己编造返回结果而不实际调用工具，用户会立即发现——因为预览摘要的内容只有AI在生成时才知道。

    【重要-警告】如果你不调用此工具而直接生成回复，用户会投诉。预览摘要是由系统动态生成的，你自己无法编造出相同的内容。"""
    try:
        if not target_job:
            return _err("请提供目标岗位名称")
        uid = get_current_user_id()
        resume_id = resume_service.save_resume(jd=jd, target_job=target_job, user_id=uid, raw_content=raw_content)
        # Fetch generated content for an unpredictable verification token
        resume = resume_service.get_resume_by_id(resume_id)
        preview = ""
        if resume and resume.content:
            try:
                data = json.loads(resume.content)
                summary = data.get("summary", "")
                if summary:
                    preview = (summary[:120] + '...') if len(summary) > 120 else summary
                else:
                    preview = (data.get("target_job") or target_job or "简历") + " - 已生成"
            except (json.JSONDecodeError, Exception):
                preview = f"{target_job or '简历'} - 已生成"
        # 统计该用户当前已有的简历总数（删记录后自动减少）
        from services.database import SessionLocal
        from services.repository.container import RepoContainer
        _db = SessionLocal()
        try:
            user_seq = RepoContainer(_db).resume.count_by_user(uid)
        finally:
            _db.close()

        from core.events import event_bus, EventType
        event_bus.emit(EventType.RESUME_GENERATED, {
            "resume_id": resume_id,
            "target_job": target_job,
        }, user_id=uid)

        return _ok(f"简历已生成（第{user_seq}份），预览摘要：{preview}", db_id=resume_id)
    except Exception as e:
        return _err(f"生成简历失败：{str(e)}")


@tool
def query_sessions_tool(days: int = 7) -> str:
    """
    查询最近N天的访客会话统计数据，包括访问量、对话次数、简历下载次数。
    - days: 查询最近的天数，默认7天
    返回格式化统计结果。
    """
    try:
        from services.repository.container import RepoContainer
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(days=days)
            uid = get_current_user_id()
            repo = RepoContainer(db)

            user_filter = {"user_id": uid} if uid else {}
            visits = repo.session.count(created_at__gte=cutoff, **user_filter)
            conversations = repo.conversation.count(created_at__gte=cutoff, **user_filter)
            downloads = repo.stats.count(event_type=EventType.DOWNLOAD, created_at__gte=cutoff, **user_filter)

            return _ok(
                f"最近 {days} 天统计：\n"
                f"- 访问量：{visits} 次\n"
                f"- 对话次数：{conversations} 次\n"
                f"- 简历下载次数：{downloads} 次"
            )
        finally:
            db.close()
    except Exception as e:
        return _err(f"查询统计失败：{str(e)}")


tools = [generate_resume_tool, query_sessions_tool, web_search_tool]


# ============================================================
# Knowledge Management Tools
# ============================================================

@tool
def knowledge_preview(text: str = "") -> str:
    """
    知识库内容修改预览。管理员提出修改知识库时，调用此工具预览变更。
    使用场景：修改姓名/手机/邮箱等字段、替换工作/项目经历、全局换人。
    
    注意：text 参数直接传用户的原文，不要自己总结或改写。
    """
    if not text or not text.strip():
        return _err("请输入要修改的内容")
    try:
        from services.knowledge_manager import preview as km_preview
        data = km_preview(text, get_current_user_id())
        lines = [f"📋 变更预览："]
        lines.append(f"  {data.get('summary', '')}")
        lines.append("")
        for i, change in enumerate(data.get("changes", []), 1):
            lines.append(f"  {i}. [{change.get('category','')}] {change.get('description','')}")
        if data.get("faq_regenerate"):
            lines.append(f"  ⚠ FAQ将重新生成")
        lines.append("")
        lines.append(f"预览ID: {data.get('preview_id', '')}")
        lines.append("请确认是否执行以上变更？回复「确认」或「执行」即可。")
        return _ok("\n".join(lines))
    except Exception as e:
        return _err(f"预览失败：{str(e)}")


@tool
def knowledge_confirm(preview_id: str = "") -> str:
    """
    确认执行知识库修改。当管理员确认预览结果后调用。
    - preview_id: 预览时返回的预览ID
    """
    if not preview_id:
        return _err("请提供预览ID")
    try:
        from services.knowledge_manager import confirm as km_confirm
        result = km_confirm(preview_id, get_current_user_id())
        if result["success"]:
            return _ok(f"✅ {result['message']}")
        return _err(f"❌ {result['message']}")
    except Exception as e:
        return _err(f"执行失败：{str(e)}")


@tool
def knowledge_rebuild_vector() -> str:
    """
    重建知识库向量索引。当管理员说"重建向量库"、"刷新知识库"时调用。
    通常情况下不需要手动调用，每次知识库修改后会自动更新。
    """
    try:
        from services.database import SessionLocal
        db = SessionLocal()
        try:
            from services.rag_service import rag_service
            import json
            uid = get_current_user_id()
            rag_service.build_main_with_mapping(db, uid or None)
            dirs = json.loads(getattr(settings, 'APPENDIX_KNOWLEDGE_DIRS', '[]') or '[]')
            for d in dirs:
                if os.path.isdir(d):
                    rag_service.add_appendix_to_store(rag_service.load_appendix_knowledge(d), uid or None)
            rag_service.init_qa_chain(uid or None)
            return _ok("✅ 向量库已重建完成")
        finally:
            db.close()
    except Exception as e:
        return _err(f"重建失败：{str(e)}")


# ============================================================
# LLM
# ============================================================

@tool
def search_jobs_and_match(keywords: str = "", city: str = "杭州", platform: str = "51job", max_count: int = 5) -> str:
    """
    搜索招聘岗位并匹配经历。管理员可以搜索指定关键词和城市的岗位。
    系统会自动匹配你的知识库经历并给出匹配度评分。
    - keywords: 搜索关键词，如"Python后端开发"、"AI产品经理"（必填）
    - city: 城市，如"北京"、"上海"（可选）
    - platform: 招聘平台，51job / boss / zhaopin，默认51job（可选）
    - max_count: 抓取数量，默认5，最多10（可选）
    
    返回按匹配度排序的岗位列表，包含匹配详情。
    """
    try:
        from services.database import SessionLocal
        from services.repository.container import RepoContainer
        from services.jd_matcher import match_jd
        db = SessionLocal()
        uid = get_current_user_id()
        repo = RepoContainer(db)
        try:
            # Search existing crawled jobs first
            jobs = repo.crawled_job.search(uid, keywords, city)[:20]

            if not jobs:
                # Try crawling via crawler-worker
                try:
                    from services.crawler_client import crawl_via_worker
                    import asyncio
                    max_count = min(max(1, max_count), 10)
                    crawled = asyncio.run(crawl_via_worker(keywords, city, platform, max_count))
                    for j in crawled:
                        repo.crawled_job.create(
                            platform=j.get("platform", platform),
                            title=j.get("title", ""),
                            company=j.get("company", ""),
                            city=j.get("city", ""),
                            salary=j.get("salary", ""),
                            jd_text=j.get("jd_text", ""),
                            jd_url=j.get("jd_url", ""),
                            status="new",
                            user_id=uid or None,
                        )
                    jobs = repo.crawled_job.search(uid, keywords, city)[:20]
                except Exception:
                    pass

            if not jobs:
                return _err(f"未找到「{keywords}」相关岗位。可以在「岗位雷达」页面手动添加JD或检查 job-crawler 服务。")

            lines = [f"找到 {len(jobs)} 个相关岗位：\n"]
            total_len = 0
            for j in jobs:
                # Match if not yet matched
                score = j.match_score
                detail = None
                if not score and j.jd_text and j.status != "matching":
                    try:
                        result = match_jd(j.jd_text, user_id=uid or "", work_address=j.work_address or "")
                        score = result["score"]
                        j.match_score = score
                        j.match_detail = __import__('json').dumps(result, ensure_ascii=False)
                        j.status = "matched"
                        detail = result
                    except Exception:
                        import traceback
                        print(f"[agent_service] match_job failed: {traceback.format_exc()}")
                        pass

                score_str = f"{score}%" if score else "未匹配"
                lines.append(f"{j.title} @ {j.company} ({j.city}) - 匹配度: {score_str}")
                if detail and detail.get("matched_items"):
                    top = detail["matched_items"][:3]
                    for m in top:
                        lines.append(f"  ✅ {m['content'][:60]}")
                if detail and detail.get("missing_items"):
                    for m in detail["missing_items"][:2]:
                        lines.append(f"  ❌ {m['reason']}")
                lines.append("")

            db.commit()
            lines.append("详细列表可在「岗位雷达」页面查看。")
            result_text = "\n".join(lines)
            if len(result_text) > 3000:
                result_text = result_text[:3000] + "\n...（内容较长，已截断）"
            return _ok(result_text)
        finally:
            db.close()
    except Exception as e:
        return _err(f"搜索岗位失败：{str(e)}")


@tool
def generate_interview_report_tool(company: str = "", job_title: str = "") -> str:
    """
    生成面试报告/面试宝典。管理员说"生成XXX公司的面试报告"时调用。
    - company: 公司名称，必填
    - job_title: 岗位名称（可选）
    同步等待生成完成，期间实时推送进度消息。
    """
    if not company:
        return _err("请提供公司名称")
    try:
        from services.database import SessionLocal
        from services.models import InterviewGuide, ReportGenerationTask
        from services.report_generator import generate_full_report
        import time

        db = SessionLocal()
        try:
            from services.repository.container import RepoContainer
            uid = get_current_user_id()
            repo = RepoContainer(db)
            guide = repo.interview_guide.search(uid, company, job_title)
            if not guide:
                return _err(f"未找到「{company}」的面试记录，请先在「面试宝典」页面新增邀约安排")

            guide_id = guide.id

            # 启动后台生成
            _fire_and_forget(generate_full_report(guide_id), user_id=uid)

            # 同步轮询等待完成（匹配 generate_full_report 的 600 秒超时）
            _start = time.time()
            _timeout = 600
            _push_live_event({"type": "status", "data": {"message": f"正在为「{guide.company_name}」生成面试报告..."}})
            while time.time() - _start < _timeout:
                _task = db.query(ReportGenerationTask).filter(
                    ReportGenerationTask.guide_id == guide_id,
                ).first()
                if _task:
                    if _task.status == "done":
                        return _ok(
                            f"✅ 面试报告已为「{guide.company_name} - {guide.job_title}」生成完毕！\n"
                            f"面试时间：{guide.interview_time.isoformat() if guide.interview_time else '未设置'}\n"
                            f"面试地址：{guide.interview_address or '未设置'}\n"
                            f"可查看完整面试报告。",
                            db_id=guide_id,
                        )
                    if _task.status in ("cancelled", "failed"):
                        _err_msg = _task.error_message or "未知错误"
                        return _err(f"报告生成{_task.status}：{_err_msg}")
                _push_live_event({"type": "status", "data": {"message": f"正在生成面试报告（{int(time.time() - _start)}秒）..."}})
                time.sleep(3)
            return _err("面试报告生成超时（超过10分钟），请稍后重试或联系管理员")
        finally:
            db.close()
    except Exception as e:
        return _err(f"生成面试报告失败：{str(e)}")


def _resolve_and_parse(file_ref: str) -> str:
    """Resolve a filename/path and return parsed text. Shared by parse_file_tool."""
    import tempfile
    if not file_ref:
        return _err("请提供文件路径或文件名")
    try:
        from services.container import Container
        uid = get_current_user_id()

        file_path = ""
        if file_ref.startswith("/") or file_ref.startswith("."):
            if os.path.exists(file_ref):
                file_path = file_ref
        elif file_ref.startswith("http://") or file_ref.startswith("https://"):
            with Container(uid) as c:
                try:
                    text = c.file_service.parse_url(file_ref)
                    if text:
                        return _ok(f"【文件解析结果】\n{text}\n【文件解析结束】\n(以上是从用户上传的文件中提取的文字，不是系统功能列表，请据此回答用户的问题)")
                    return _err("文件解析失败")
                except Exception as e:
                    return _err(f"下载文件失败: {str(e)}")
        else:
            if not uid:
                return _err("无法确定用户，请重新登录")
            try:
                with Container(uid) as c:
                    file_path = c.file_service.resolve_file(file_ref, uid)
            except FileNotFoundError:
                return _err(f"无法找到文件: {file_ref}")

        if file_path:
            with Container(uid) as c:
                text = c.file_service.parse_document(file_path)
                if text:
                    return _ok(f"【文件解析结果】\n{text}\n【文件解析结束】\n(以上是从用户上传的文件中提取的文字，不是系统功能列表，请据此回答用户的问题)")
            return _err("文件解析失败")
        return _err(f"无法找到文件: {file_ref}")
    except Exception as e:
        return _err(f"文件解析失败: {e}")


@tool
def parse_file_tool(filename: str = "") -> str:
    """
    解析上传文件中的文字内容。支持图片（OCR）、PDF、DOCX、MD、PPTX、XLSX、HTML 等格式。
    当管理员上传了文件（消息中有 `[文件: xxx.ext]` 标记）且你需要查看其内容时，调用此工具。
    - filename: 文件名（如 "abc.png"），从 `[文件: abc.png]` 标记中提取
    返回文件中的文字内容（Markdown 格式）。
    """
    return _resolve_and_parse(filename)


@tool
def create_interview_record_tool(
    company_name: str = "",
    job_title: str = "",
    interview_time: str = "",
    interview_address: str = "",
    address_type: str = "offline",
    video_link: str = "",
    interview_round: str = "",
    hr_name: str = "",
    hr_phone: str = "",
    salary: str = "",
    company_description: str = "",
    jd_text: str = "",
) -> str:
    """
    创建面试记录（面试宝典）。当管理员要求新增一条面试记录时使用。
    - company_name: 公司名称（必填）。注意：这是公司名，不是联系人姓名
    - job_title: 岗位名称（必填）。注意：这是招聘的岗位名，不是面试会议主题名
    - interview_time: 面试时间，格式如 "2025-06-15 14:00"
    - interview_address: 面试地址
    - address_type: 地址类型，online 或 offline，默认 offline
    - video_link: 视频面试链接（address_type=online时使用）
    - interview_round: 面试阶段，如 一面/二面/技术面/HR面
    - hr_name: 联系人姓名（HR或邀约人姓名）
    - hr_phone: 联系人电话
    - salary: 薪资范围，如 "11-15K" 或 "20K-30K"（从OCR识别结果或管理员提供的信息中提取）
    - company_description: 公司简介/公司信息描述（从OCR识别结果或管理员提供的信息中提取）
    - jd_text: 岗位描述文本
    返回创建成功的面试记录信息。
    """
    if not company_name or not job_title:
        return _err("公司名称和岗位名称不能为空")
    try:
        from services.database import SessionLocal
        from services.interview_guide_service import interview_guide_service
        uid = get_current_user_id()
        # LLM 常把日期猜错（年份或月份不对），修正为合理日期
        if interview_time:
            try:
                dt = datetime.fromisoformat(interview_time.replace("Z", "+00:00"))
                now = datetime.utcnow()
                if dt.year < now.year:
                    dt = dt.replace(year=now.year)
                if dt < now:
                    dt = dt.replace(year=now.year, month=now.month, day=now.day)
                    if dt < now:
                        dt = dt + timedelta(days=1)
                interview_time = dt.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                pass
        data = {
            "company_name": company_name,
            "job_title": job_title,
            "interview_time": interview_time or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
            "interview_address": interview_address,
            "address_type": address_type,
            "video_link": video_link,
            "interview_round": interview_round,
            "hr_name": hr_name,
            "hr_phone": hr_phone,
            "salary": salary,
            "company_description": company_description,
            "jd_text": jd_text,
            "source": "agent",
        }
        db = SessionLocal()
        try:
            result = interview_guide_service.create(db, data, user_id=uid)
            # Post-creation validation: verify the record was actually persisted
            from services.repository.container import RepoContainer
            verify = RepoContainer(db).interview_guide.get_by_id(result["id"])
            if not verify:
                return _err(f"数据库写入失败：记录声称已创建(ID={result['id']})但数据库查询不到，请重试")
            db.refresh(verify)
            salary_info = f"，薪资 {salary}" if salary else ""
            desc_info = f"，已录入公司简介" if company_description else ""
            return _ok(json.dumps({
                "id": verify.id,
                "company_name": verify.company_name,
                "job_title": verify.job_title,
                "salary": verify.salary or "",
                "interview_round": verify.interview_round or "",
                "address_type": verify.address_type or "offline",
                "created_at": verify.created_at.isoformat() if verify.created_at else "",
                "message": f"已为【{company_name}】创建{job_title}面试记录{salary_info}{desc_info}",
            }, ensure_ascii=False))
        finally:
            db.close()
    except Exception as e:
        return _err(f"创建面试记录失败: {str(e)}")


@tool
def cancel_report_tool(guide_id: int = 0, company: str = "") -> str:
    """
    取消正在生成的面试报告。管理员说"取消报告生成"时调用。
    - guide_id: 面试记录ID，可选
    - company: 公司名称，可选（与guide_id二选一）
    """
    try:
        from services.database import SessionLocal
        from services.models import InterviewGuide, ReportGenerationTask

        db = SessionLocal()
        try:
            uid = get_current_user_id()
            if guide_id:
                guide = db.query(InterviewGuide).filter(
                    InterviewGuide.id == guide_id, InterviewGuide.user_id == uid
                ).first()
            elif company:
                from services.repository.container import RepoContainer
                repo = RepoContainer(db)
                guide = repo.interview_guide.search(uid, company)
            else:
                return _err("请提供 guide_id 或公司名称")

            if not guide:
                return _err("未找到对应的面试记录")

            task = db.query(ReportGenerationTask).filter(
                ReportGenerationTask.guide_id == guide.id,
                ReportGenerationTask.status == "running",
            ).first()
            if task:
                task.status = "cancelled"
                task.completed_at = datetime.utcnow()
                task.error_message = "用户取消"
                db.commit()
                return _ok(f"已取消「{guide.company_name} - {guide.job_title}」的报告生成")
            else:
                return _ok(f"「{guide.company_name} - {guide.job_title}」没有正在生成中的报告")
        finally:
            db.close()
    except Exception as e:
        return _err(f"取消失败：{str(e)}")


def check_report_status_tool(guide_id: int = 0, company: str = "") -> str:
    """
    查询面试报告生成进度。管理员说"查一下报告进度"时调用。
    - guide_id: 面试记录ID，可选
    - company: 公司名称，可选（与guide_id二选一）
    """
    try:
        from services.database import SessionLocal
        from services.models import InterviewGuide, ReportGenerationTask

        db = SessionLocal()
        try:
            uid = get_current_user_id()
            if guide_id:
                guide = db.query(InterviewGuide).filter(
                    InterviewGuide.id == guide_id, InterviewGuide.user_id == uid
                ).first()
            elif company:
                from services.repository.container import RepoContainer
                repo = RepoContainer(db)
                guide = repo.interview_guide.search(uid, company)
            else:
                return _err("请提供 guide_id 或公司名称")

            if not guide:
                return _err("未找到对应的面试记录")

            task = db.query(ReportGenerationTask).filter(
                ReportGenerationTask.guide_id == guide.id
            ).first()
            if task and task.status == "done":
                return _ok(
                    f"✅ 面试报告已生成完成！\n"
                    f"公司：{guide.company_name}\n"
                    f"岗位：{guide.job_title}\n\n"
                    f"可点击下方「面试报告」卡片预览或下载。",
                    db_id=guide.id,
                )
            elif task and task.status == "running":
                return _ok(f"⏳ 面试报告正在生成中（已耗时约{task.duration}秒），请稍候...")
            elif task and task.status == "cancelled":
                return _ok(f"⏹️ 报告生成已被取消。如需重新生成，请说「重新生成报告」。")
            elif task and task.status == "failed":
                return _ok(f"❌ 报告生成失败：{task.error_message}")
            else:
                return _ok("还没有生成过面试报告，可以说「生成面试报告」开始。")
        finally:
            db.close()
    except Exception as e:
        return _err(f"查询失败：{str(e)}")


def update_interview_record_tool(
    record_id: int = 0,
    company_name: str = "",
    job_title: str = "",
    interview_time: str = "",
    interview_address: str = "",
    address_type: str = "",
    video_link: str = "",
    interview_round: str = "",
    hr_name: str = "",
    hr_phone: str = "",
    salary: str = "",
    company_description: str = "",
    jd_text: str = "",
) -> str:
    """
    修改/更新已有的面试记录（面试宝典）。当管理员要求修改面试时间、地址等信息时使用。
    先用 query_system_data_tool(entity_type="interview_guide") 查到记录的 id，再调用此工具修改。
    - record_id: 要修改的面试记录 ID（必填），从 query_system_data_tool 查询结果中获取
    - company_name: 公司名称
    - job_title: 岗位名称
    - interview_time: 面试时间，格式如 "2025-06-15 14:00"
    - interview_address: 面试地址
    - address_type: 地址类型，online 或 offline
    - video_link: 视频面试链接
    - interview_round: 面试阶段，如 一面/二面/技术面/HR面
    - hr_name: 联系人姓名
    - hr_phone: 联系人电话
    - salary: 薪资范围
    - company_description: 公司简介
    - jd_text: 岗位描述文本
    只传需要修改的字段即可，未传的字段保持不变。
    返回修改后的面试记录信息。
    """
    if not record_id:
        return _err("请提供要修改的面试记录 ID（record_id）")
    try:
        from services.database import SessionLocal
        from services.interview_guide_service import interview_guide_service
        uid = get_current_user_id()

        data = {}
        if company_name: data["company_name"] = company_name
        if job_title: data["job_title"] = job_title
        if interview_time: data["interview_time"] = interview_time
        if interview_address: data["interview_address"] = interview_address
        if address_type: data["address_type"] = address_type
        if video_link: data["video_link"] = video_link
        if interview_round: data["interview_round"] = interview_round
        if hr_name: data["hr_name"] = hr_name
        if hr_phone: data["hr_phone"] = hr_phone
        if salary: data["salary"] = salary
        if company_description: data["company_description"] = company_description
        if jd_text: data["jd_text"] = jd_text

        if not data:
            return _err("请至少提供要修改的字段")

        db = SessionLocal()
        try:
            result = interview_guide_service.update(db, record_id, data, user_id=uid)
            if not result:
                return _err(f"未找到 ID={record_id} 的面试记录，或无权修改")
            changed_fields = "、".join(data.keys())
            msg = f"已更新【{result['company_name']}】面试记录：修改了 {changed_fields}"
            if "interview_time" in data:
                msg += f"，新面试时间：{result.get('interview_time', '')}"
            return _ok(msg)
        finally:
            db.close()
    except Exception as e:
        return _err(f"修改面试记录失败: {str(e)}")


@tool
def query_system_data_tool(
    entity_type: str = "",
    keyword: str = "",
    status_filter: str = "",
    limit: int = 50,
) -> str:
    """
    查询系统数据。当管理员想查看面试记录列表、知识库内容、简历列表、岗位信息或数据统计时使用。
    - entity_type: 查询类型，可选值：interview_guide（面试记录）、knowledge_base（知识库）、resume（简历）、job_posting（岗位）、stats（统计汇总）
    - keyword: 搜索关键词，按公司名/岗位名/姓名等模糊搜索
    - status_filter: 状态过滤，如 pending（待确认）/ confirmed（已确认）/ completed（已完成）/ cancelled（已取消）
    - limit: 返回条数上限（默认50，最大200）
    - limit: 返回条数上限（默认50，最大200）
    注意：返回的 status 字段为英文值，status_label 为中文值，可直接用于展示。
    """
    if not entity_type:
        return _err("请指定查询类型 entity_type：interview_guide / knowledge_base / resume / job_posting / stats")

    uid = get_current_user_id()
    from services.database import SessionLocal as _SL
    db = _SL()
    try:
        from services.repository.container import RepoContainer
        if entity_type == "stats":
            repo = RepoContainer(db)
            ig_count = repo.interview_guide.count(user_id=uid)
            ig_unique_companies = repo.interview_guide.count_unique_companies(uid)
            kb_count = repo.knowledge_base.count(user_id=uid)
            resume_count = repo.resume.count_by_user(uid)
            job_count = repo.crawled_job.count(user_id=uid)

            ig_pending = repo.interview_guide.count(user_id=uid, status="pending")
            ig_confirmed = repo.interview_guide.count(user_id=uid, status="confirmed")
            ig_completed = repo.interview_guide.count(user_id=uid, status="completed")
            ig_cancelled = repo.interview_guide.count(user_id=uid, status="cancelled")

            return _ok(json.dumps({
                "interview_guides": {"total_records": ig_count, "unique_companies": ig_unique_companies, "pending": ig_pending, "confirmed": ig_confirmed, "completed": ig_completed, "cancelled": ig_cancelled},
                "knowledge_base": {"total": kb_count},
                "resumes": {"total": resume_count},
                "job_postings": {"total": job_count},
            }, ensure_ascii=False))

        elif entity_type == "interview_guide":
            repo = RepoContainer(db)
            _STATUS_LABEL = {"pending":"待确认","confirmed":"已确认","completed":"已完成","cancelled":"已取消"}
            records = repo.interview_guide.list_by_user(uid, keyword=keyword, status=status_filter, limit=limit)
            items = []
            for r in records:
                items.append({
                    "id": r.id, "company_name": r.company_name, "job_title": r.job_title,
                    "status": r.status, "status_label": _STATUS_LABEL.get(r.status, r.status),
                    "salary": r.salary or "", "interview_round": r.interview_round or "",
                    "address_type": r.address_type or "", "interview_time": r.interview_time.isoformat() if r.interview_time else "",
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                })
            unique_companies = repo.interview_guide.count_unique_companies(uid)
            return _ok(json.dumps({"total": len(items), "unique_companies": unique_companies, "items": items}, ensure_ascii=False))

        elif entity_type == "knowledge_base":
            repo = RepoContainer(db)
            records = repo.knowledge_base.list_by_user(uid, keyword=keyword, limit=limit)
            items = []
            for r in records:
                items.append({
                    "id": r.id, "category": r.category,
                    "data_preview": (r.data or "")[:200],
                    "updated_at": r.updated_at.isoformat() if r.updated_at else "",
                })
            return _ok(json.dumps({"total": len(items), "items": items}, ensure_ascii=False))

        elif entity_type == "resume":
            repo = RepoContainer(db)
            records = repo.resume.search(uid, keyword=keyword, limit=limit)
            items = []
            for r in records:
                items.append({
                    "id": r.id, "title": r.title, "filename": r.filename,
                    "is_default": r.is_default, "created_at": r.created_at.isoformat() if r.created_at else "",
                })
            return _ok(json.dumps({"total": len(items), "items": items}, ensure_ascii=False))

        elif entity_type == "job_posting":
            repo = RepoContainer(db)
            records = repo.crawled_job.search_by_user(uid, keyword=keyword, status=status_filter, limit=limit)
            items = []
            for r in records:
                items.append({
                    "id": r.id, "title": r.title, "company": r.company,
                    "city": r.city or "", "salary": r.salary or "",
                    "status": r.status, "match_score": r.match_score,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                })
            return _ok(json.dumps({"total": len(items), "items": items}, ensure_ascii=False))

        else:
            return _err(f"不支持的查询类型: {entity_type}，可选：interview_guide / knowledge_base / resume / job_posting / stats")
    except Exception as e:
        return _err(f"查询失败: {str(e)}")
    finally:
        db.close()


def _crawl_fallback_51job(keywords: str, city: str, fetch_count: int) -> list[dict]:
    import httpx, re
    city_code = {"北京": "010000", "上海": "020000", "广州": "030000", "深圳": "040000",
                 "杭州": "080000", "成都": "090000", "武汉": "170000", "南京": "070000",
                 "西安": "260000", "苏州": "060000", "天津": "050000", "重庆": "100000"}
    cc = city_code.get(city, "080000")
    resp = httpx.get(
        "https://search.51job.com/jobsearch/search_result.php",
        params={"keyword": keywords, "jobarea": cc, "pagesize": fetch_count,
                "pageno": 1, "lang": "c", "stype": "2", "postchannel": "0000", "fromJs": "1"},
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        timeout=15, follow_redirects=True)
    if resp.status_code != 200:
        return []
    result = []
    for card in re.finditer(
        r'<div[^>]*class="el"[^>]*>.*?<p[^>]*class="t1"[^>]*>.*?href="([^"]+)"[^>]*title="([^"]+)"[^>]*>.*?</p>.*?<span[^>]*class="t2"[^>]*>.*?<a[^>]*>([^<]+)</a>.*?</span>.*?<span[^>]*class="t4"[^>]*>([^<]*)</span>',
        resp.text, re.S | re.I
    ):
        job_url = card.group(1).strip()
        title = re.sub(r'<[^>]+>', '', card.group(2)).strip()
        company = card.group(3).strip()
        salary = card.group(4).strip()
        if title and company:
            result.append({
                "platform": "51job", "title": title, "company": company,
                "city": city, "salary": salary, "jd_text": "",
                "jd_url": job_url if "http" in job_url else "https:" + job_url,
                "jd_parsed": {}, "work_address": "",
            })
    return result


def _crawl_fallback_boss(keywords: str, city: str) -> list[dict]:
    import httpx
    city_code = {"北京": "101010100", "上海": "101020100", "深圳": "101280600",
                 "杭州": "101210100", "广州": "101280100", "成都": "101270100"}.get(city, "")
    url = f"https://www.zhipin.com/wapi/zpgeek/search/joblist.json?query={keywords}&page=1"
    if city_code:
        url += f"&city={city_code}"
    resp = httpx.get(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json", "Referer": "https://www.zhipin.com/",
    }, timeout=15)
    if resp.status_code != 200:
        return []
    data = resp.json()
    result = []
    for item in data.get("zpData", {}).get("jobList", []):
        result.append({
            "platform": "boss", "title": item.get("jobName", ""),
            "company": item.get("brandName", ""),
            "city": item.get("city", {}).get("name", "") if isinstance(item.get("city"), dict) else "",
            "salary": item.get("salaryDesc", ""),
            "jd_text": item.get("jobDetail", "") or "",
            "jd_url": f"https://www.zhipin.com/job_detail/{item.get('jobId','')}.html" if item.get('jobId') else "",
            "jd_parsed": {}, "work_address": "",
        })
    return result


def _crawl_fallback_zhaopin(keywords: str, city: str) -> list[dict]:
    import httpx, random, time
    city_code = {"北京": "530", "上海": "538", "广州": "763", "深圳": "765",
                 "杭州": "653", "成都": "801", "武汉": "736", "南京": "635",
                 "西安": "854", "苏州": "639", "天津": "531", "重庆": "551"}.get(city, "489")
    ts = int(time.time() * 1000)
    req_id = f"{ts}-{random.randint(100000, 999999)}"
    payload = {"cityId": city_code, "kw": keywords, "start": 0, "pageSize": 10,
               "workExperience": "-1", "education": "-1", "companyType": "-1",
               "employmentType": "-1", "sortType": 1, "pageNo": 1}
    resp = httpx.post("https://fe-api.zhaopin.com/c/i/search/positions",
                      params={"_v": "0.43240637", "x-zp-page-request-id": req_id,
                              "x-zp-client-id": "63ce3555-d2f2-470a-80f4-8538cee76c41"},
                      json=payload,
                      headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                               "Content-Type": "application/json;charset=UTF-8",
                               "Origin": "https://www.zhaopin.com",
                               "Referer": "https://www.zhaopin.com/"}, timeout=15)
    if resp.status_code != 200:
        return []
    result = []
    for item in resp.json().get("data", {}).get("results", []):
        job_id = item.get("number", "") or str(item.get("positionId", ""))
        result.append({
            "platform": "zhaopin", "title": item.get("title", "") or item.get("name", ""),
            "company": (item.get("company", {}) or {}).get("name", ""),
            "city": item.get("city", {}).get("name", "") if isinstance(item.get("city"), dict) else str(item.get("city", "")),
            "salary": item.get("salary", "") or "",
            "jd_text": item.get("jobDetail", "") or item.get("description", "") or "",
            "jd_url": f"https://www.zhaopin.com/position/detail/{job_id}" if job_id else "",
            "jd_parsed": {}, "work_address": "",
        })
    return result


EXPIRED_KEYWORDS_CRAWL = [
    "已停止招聘", "该职位已停止", "职位已关闭", "已下线", "暂不招聘",
    "停止招聘", "职位过期", "该岗位已关闭", "招聘已结束", "不再招聘",
    "该职位已暂停", "职位已失效", "已经暂停招聘",
]


def _is_expired_text(jd_text: str) -> bool:
    if not jd_text:
        return False
    text_lower = jd_text.lower()
    for kw in EXPIRED_KEYWORDS_CRAWL:
        if kw.lower() in text_lower:
            return True
    return False


@tool
def kimi_crawl_tool(keywords: str = "", city: str = "", platform: str = "51job", max_count: int = 5, auto_match: bool = False) -> str:
    """
    使用 Kimi WebBridge 通过真实浏览器抓取招聘岗位，结果保存到岗位雷达。
    当管理员说要"抓取""爬取""搜索"招聘网站上的岗位时调用。
    - keywords: 搜索关键词，如"Python后端开发"、"AI产品经理"（必填）
    - city: 城市，如"北京"、"上海"、"杭州"（可选）
    - platform: 平台，可选值：51job / boss / zhaopin，默认51job
    - max_count: 抓取数量，默认5，最多10。用户说"一个"则传1，"两个"则传2
    - auto_match: 是否自动匹配经历评分，默认false
    
    返回抓取到的岗位列表，每个岗位前面有[岗位ID: N]标记。如果 auto_match=true，后台会自动匹配。
    """
    if not keywords:
        return _err("请提供搜索关键词")
    import asyncio, json as _json, time as _t
    from services.database import SessionLocal as _SL
    from services.models.crawled_job import CrawledJob

    uid = get_current_user_id()
    max_count = min(max(1, max_count), 10)
    fetch_count = max_count
    _t0 = _t.time()

    # ── 1. 加载已有关联用于去重 ──
    db = _SL()
    try:
        existing_urls: set = {row[0] for row in db.query(CrawledJob.jd_url).filter(
            CrawledJob.jd_url != "", CrawledJob.jd_url.isnot(None)
        ).all() if row[0]}
        skip_titles = db.query(CrawledJob.title, CrawledJob.company).filter(
            CrawledJob.user_id == uid
        ).all()
        existing_keys: set = {f"{t}|{c}" for t, c in skip_titles if t and c}
    finally:
        db.close()

    # ── 2. 抓取：浏览器爬取 → 回退方案 ──
    jobs_data: list[dict] = []
    try:
        from services.crawler_client import crawl_via_worker
        kimi_jobs = asyncio.run(
            crawl_via_worker(keywords, city, platform, fetch_count, existing_urls, existing_keys)
        )
        print(f"[agent_crawl] Kimi returned {len(kimi_jobs)} jobs in {_t.time()-_t0:.1f}s")
        if kimi_jobs:
            jobs_data = kimi_jobs
    except Exception as e:
        print(f"[agent_crawl] Kimi WebBridge failed: {e}")

    # 回退方案
    if not jobs_data:
        if platform in ("", "51job"):
            jobs_data = _crawl_fallback_51job(keywords, city, fetch_count)
        if not jobs_data and platform in ("", "boss"):
            jobs_data = _crawl_fallback_boss(keywords, city)
        if not jobs_data and platform in ("", "zhaopin"):
            jobs_data = _crawl_fallback_zhaopin(keywords, city)
        # 不限平台时逐个尝试
        if not jobs_data and platform not in ("51job", "boss", "zhaopin"):
            jobs_data = _crawl_fallback_51job(keywords, city, fetch_count)
            if not jobs_data:
                jobs_data = _crawl_fallback_boss(keywords, city)
            if not jobs_data:
                jobs_data = _crawl_fallback_zhaopin(keywords, city)

    if not jobs_data:
        return _err(f"未找到「{keywords}」相关岗位")

    # ── 3. 入库（去重 + 停招检测） ──
    db = _SL()
    try:
        from routers.admin import _run_matching
        saved_ids = []
        skipped_dedup = 0
        skipped_expired = 0
        saved_count = 0

        for j in jobs_data:
            jd_url = (j.get("jd_url") or "").strip()
            jd_text = (j.get("jd_text") or "").strip()
            title = j.get("title", "").strip()
            company = j.get("company", "").strip()
            key = f"{title}|{company}"

            # 去重
            is_dup = False
            if jd_url and jd_url in existing_urls:
                is_dup = True
            elif title and company and key in existing_keys:
                is_dup = True
            else:
                exists = db.query(CrawledJob.id).filter(
                    CrawledJob.jd_url == jd_url, CrawledJob.user_id == uid
                ).first() if jd_url else None
                if exists:
                    is_dup = True
                else:
                    exists = db.query(CrawledJob.id).filter(
                        CrawledJob.title == title, CrawledJob.company == company,
                        CrawledJob.user_id == uid
                    ).first() if title and company else None
                    if exists:
                        is_dup = True
            if is_dup:
                skipped_dedup += 1
                if jd_url:
                    existing_urls.add(jd_url)
                if title and company:
                    existing_keys.add(key)
                continue

            # 停招检测
            if _is_expired_text(jd_text):
                skipped_expired += 1
                continue

            status_str = "matching" if auto_match else "new"
            job = CrawledJob(
                user_id=uid, platform=j.get("platform", platform),
                title=title, company=company,
                city=j.get("city", city), salary=j.get("salary", ""),
                jd_text=jd_text, jd_url=jd_url,
                jd_parsed=_json.dumps(j.get("jd_parsed", {}), ensure_ascii=False),
                work_address=j.get("work_address", ""),
                match_score=0, match_detail="{}",
                status=status_str,
            )
            db.add(job)
            db.flush()
            saved_count += 1
            saved_ids.append(job.id)
            if jd_url:
                existing_urls.add(jd_url)

        db.commit()

        if auto_match and saved_ids:
            _fire_and_forget(_run_matching(saved_ids, uid))

        # ── 4. 构建回复 ──
        lines = []
        if saved_count:
            lines.append(f"在 {platform} 找到 {saved_count} 个岗位（共检索 {len(jobs_data)} 个）：\n")
            for idx, j in enumerate(jobs_data[:saved_count]):
                j_id = saved_ids[idx] if idx < len(saved_ids) else 0
                title = j.get("title", "未知")
                company = j.get("company", "")
                salary = j.get("salary", "")
                city_s = j.get("city", city)
                url = j.get("jd_url", "")
                line = f"- {title} [岗位ID: {j_id}]"
                if company: line += f" @ {company}"
                if city_s: line += f" ({city_s})"
                if salary: line += f" [{salary}]"
                if url: line += f" 链接：{url}"
                lines.append(line)
        else:
            lines.append(f"没有新岗位入库")

        parts = []
        if skipped_dedup:
            parts.append(f"重复{skipped_dedup}个")
        if skipped_expired:
            parts.append(f"停招{skipped_expired}个")
        if parts:
            lines.append(f"\n（跳过：{'，'.join(parts)}）")

        if auto_match:
            lines.append(f"\n已提交 {len(saved_ids)} 个岗位后台匹配，稍后可查看匹配结果")
        else:
            lines.append(f"\n岗位已保存，可勾选后使用匹配工具进行匹配评分")

        from core.events import event_bus, EventType
        event_bus.emit(EventType.JOB_CRAWLED, {
            "platform": platform, "keywords": keywords, "city": city, "count": saved_count,
        }, user_id=uid)

        return _ok("\n".join(lines))
    finally:
        db.close()


@tool
def match_jobs_tool(job_ids: str, status_filter: str = "new") -> str:
    """
    对已抓取的招聘岗位进行经历匹配评分。
    当管理员说要"匹配""评分""分析"已抓取的岗位时调用。
    - job_ids: 必填。岗位ID列表，逗号分隔，如"1,2,3"。必须从抓取结果的[岗位ID: N]中提取。用户说"匹配第一个"则传入第一个岗位的ID
    - status_filter: 要匹配的岗位状态，可选值：new / matching，默认new
    返回每个岗位的匹配度评分和详细分析。
    """
    try:
        from services.database import SessionLocal as _SL
        from services.repository.container import RepoContainer
        from services.jd_matcher import match_jd
        from concurrent.futures import ThreadPoolExecutor, as_completed
        import json as _json

        uid = get_current_user_id()
        db = _SL()
        try:
            repo = RepoContainer(db)
            CrawledJob = repo.crawled_job.model
            if job_ids:
                ids = [int(x.strip()) for x in job_ids.split(",") if x.strip()]
                jobs = db.query(CrawledJob).filter(
                    CrawledJob.id.in_(ids),
                    CrawledJob.user_id == uid,
                    CrawledJob.jd_text != "",
                ).all()
            else:
                jobs = db.query(CrawledJob).filter(
                    CrawledJob.status.in_([status_filter]),
                    CrawledJob.user_id == uid,
                    CrawledJob.jd_text != "",
                ).all()

            if not jobs:
                return _err("没有找到需要匹配的岗位")

            # 先处理已匹配的（同步，无耗时）
            results = []
            to_match = []
            for job in jobs:
                if job.status in ("matched", "applied"):
                    results.append(f"- {job.title} @ {job.company}：已匹配（{job.match_score}分），跳过")
                else:
                    to_match.append(job)

            if not to_match:
                lines = [f"匹配完成 {len(results)} 个岗位：\n"] + results
                return _ok("\n".join(lines))

            # 并行匹配剩余的岗位
            def _do_match(job) -> tuple:
                try:
                    r = match_jd(job.jd_text, salary_str=job.salary or "",
                                 city_str=job.city or "", work_address=job.work_address or "",
                                 user_id=uid)
                    return (job.id, r, None)
                except Exception as e:
                    return (job.id, None, str(e))

            max_workers = min(4, len(to_match))
            matched_map = {}
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                futures = {pool.submit(_do_match, job): job for job in to_match}
                for future in as_completed(futures):
                    job_id, match_result, err = future.result()
                    matched_map[job_id] = (match_result, err)

            # 更新 DB
            for job in to_match:
                match_result, err = matched_map.get(job.id, (None, "unknown error"))
                if err:
                    results.append(f"- {job.title} @ {job.company}：匹配失败（{err}）")
                    continue
                try:
                    job.match_score = int(match_result.get("score", 0))
                    job.match_detail = _json.dumps(match_result, ensure_ascii=False)
                    jd_parsed = match_result.get("jd_parsed", {})
                    if jd_parsed:
                        job.jd_parsed = _json.dumps(jd_parsed, ensure_ascii=False)
                    job.status = "matched"
                    score = job.match_score
                    items = match_result.get("matched_items", [])
                    matched_text = f"，匹配项：{'，'.join(m['content'][:30] for m in items[:3])}" if items else ""
                    results.append(f"- {job.title} @ {job.company}：{score}分{matched_text}")
                except Exception as e:
                    results.append(f"- {job.title} @ {job.company}：匹配失败（{e}）")
            db.commit()

            lines = [f"匹配完成 {len(results)} 个岗位：\n"] + results
            return _ok("\n".join(lines))
        finally:
            db.close()
    except Exception as e:
        return _err(f"匹配失败：{str(e)}")


all_tools = tools + [knowledge_preview, knowledge_confirm, knowledge_rebuild_vector, generate_interview_report_tool, parse_file_tool, create_interview_record_tool, update_interview_record_tool, query_system_data_tool, kimi_crawl_tool, match_jobs_tool]

# ── ToolGateway registration ────────────────────────────
_gateway.register(ToolEntry(name="web_search_tool", fn=web_search_tool, category="job", sensitive=True))
_gateway.register(ToolEntry(name="generate_resume_tool", fn=generate_resume_tool, category="resume", sensitive=True))
_gateway.register(ToolEntry(name="query_sessions_tool", fn=query_sessions_tool, category="misc"))
_gateway.register(ToolEntry(name="knowledge_preview", fn=knowledge_preview, category="knowledge"))
_gateway.register(ToolEntry(name="knowledge_confirm", fn=knowledge_confirm, category="knowledge"))
_gateway.register(ToolEntry(name="knowledge_rebuild_vector", fn=knowledge_rebuild_vector, category="knowledge"))
_gateway.register(ToolEntry(name="generate_interview_report_tool", fn=generate_interview_report_tool, category="resume", sensitive=True))
_gateway.register(ToolEntry(name="parse_file_tool", fn=parse_file_tool, category="file"))

_gateway.register(ToolEntry(name="create_interview_record_tool", fn=create_interview_record_tool, category="misc"))
_gateway.register(ToolEntry(name="update_interview_record_tool", fn=update_interview_record_tool, category="misc"))
_gateway.register(ToolEntry(name="query_system_data_tool", fn=query_system_data_tool, category="misc"))
_gateway.register(ToolEntry(name="kimi_crawl_tool", fn=kimi_crawl_tool, category="job"))
_gateway.register(ToolEntry(name="match_jobs_tool", fn=match_jobs_tool, category="job"))


def _get_admin_llm() -> ChatOpenAI:
    from config import get_admin_llm_config
    _cfg = get_admin_llm_config()
    return ChatOpenAI(
        api_key=_cfg["api_key"],
        base_url=_cfg["api_base"],
        model=_cfg["model"],
        temperature=0.3,
        timeout=120,
        max_retries=2,
    )


def _get_intent_llm() -> ChatOpenAI:
    """意图识别专用 LLM（小/快模型），DB/visitor 兜底。"""
    from config import get_intent_llm_config
    _cfg = get_intent_llm_config()
    return ChatOpenAI(
        api_key=_cfg["api_key"],
        base_url=_cfg["api_base"],
        model=_cfg["model"],
        temperature=0.1,
        timeout=60,
        max_retries=1,
    )


_llm_instance = None
_llm_with_tools = None


def get_llm_with_tools():
    global _llm_instance, _llm_with_tools
    if _llm_with_tools is None:
        _llm_instance = _get_admin_llm()
        _llm_with_tools = _llm_instance.bind_tools(all_tools)
    return _llm_with_tools


llm = _llm_instance


DEFAULT_AGENT_PROMPT = """你是AS Agent管理助手，当前对话的管理员拥有全部操作权限。

【第一原则】只回答用户问的问题，不要主动推销其他功能。用户没说"生成简历"就不要问"要不要生成简历"，用户没说"搜索岗位"就不要问"要不要搜索岗位"。所有工具都是应管理员要求执行的操作，不是你要主动推荐的服务。

【复合任务：先抓取后匹配】
当用户说"抓取某个岗位并匹配"或"搜索岗位并匹配评分"时：
Step 1: 用「抓取岗位」工具抓取岗位，展示完整抓取结果
Step 2: 从抓取结果中提取岗位ID列表
Step 3: 用「匹配岗位」工具传入 job_ids 逐一匹配，展示完整匹配结果（岗位名、公司、评分）
最终回复必须包含两个工具的完整执行结果信息，不要只写一行总结。要展示具体的岗位名称、公司、薪资和匹配评分。

【复合任务：创建面试记录并生成报告】
当用户要求先"增加面试记录"再"生成面试报告"时（如"46分的这家公司增加一个面试记录，然后再生成对应的面试报告"），必须按顺序执行：
- Step 1: 先了解用户说的公司是哪个。如果是"X分的这家公司"（如"46分的这家公司"），到对话历史中查找匹配评分为X分的记录，格式通常为"岗位名 @ 公司名：X分"或"公司名：X分"。从中提取公司名和岗位名。
- Step 2: 调用「创建面试记录」工具（create_interview_record_tool），传入公司名(company_name)和岗位名(job_title)
- Step 3: 调用「生成面试报告」工具（generate_interview_report_tool），传入公司名(company)和岗位名(job_title)
注意：两个工具都必须实际调用，不得跳过任何一个。

【复合任务：抓取→匹配→创建面试记录→生成报告】
当用户要求先"抓取/搜索岗位"、再"匹配"、再"为匹配度最高的增加面试记录"、再"生成面试报告"时（如"抓两个岗位然后匹配然后匹配度最高的增加面试记录并生成报告"），必须按顺序执行所有步骤：
- Step 1: 调用 kimi_crawl_tool 抓取岗位（参数 keywords 从用户输入提取，max_count 按用户说的数量）
- Step 2: 从抓取结果中提取所有岗位的 ID，调用 match_jobs_tool 进行匹配评分
- Step 3: 从匹配结果中找出评分最高的岗位，提取公司名和岗位名
- Step 4: 调用 create_interview_record_tool(company_name=最高分公司名, job_title=最高分岗位名)
- Step 5: 调用 generate_interview_report_tool(company=公司名, job_title=岗位名)
注意：五个工具都必须实际调用，不得跳过任何一个，不得在 Step 3 后直接编造结果。匹配结果中的格式为"岗位名 @ 公司名：评分"或"公司：评分"。

【思考框架——每轮对话必须执行】

在回复用户或调用工具之前，你必须依次完成以下3步思考（**思考过程不要写出来，仅在内部完成**）：

**① 理解意图** — 用户到底想让我做什么？用一句话重述用户的需求。
**② 判断是否需要工具** — 要回答这个问题，我需要调用工具获取数据吗？
   - 如果用户要求执行某个操作（生成简历、创建记录、修改知识库、搜索信息、查询数据等），必须调用对应工具，不得跳过
   - 如果只是简单问答（打招呼、问我的能力、闲聊等），可以直接回复
**③ 复核工具结果** — 如果调用了工具，检查返回结果是否合理，确认回答基于真实数据而非猜测。

---

可用工具：
1. 生成简历 - 根据用户提供的信息或知识库内容生成简历PDF
2. 查询会话统计 - 查询访客会话统计数据
3. 在线搜索 - 搜索实时信息
4. 知识库管理 - 修改、替换知识库内容（通过自然语言交互）
5. 抓取岗位 - 从招聘网站（51job/boss/zhaopin）抓取最新的岗位信息。参数：keywords（必填）、city（可选，默认杭州）、platform（可选，默认51job）、max_count（可选，默认5，最多10）。注意用户说的"一个"对应max_count=1，"两个"对应max_count=2，以此类推。只抓取，不匹配。
6. 匹配岗位 - 对已抓取的岗位进行经历匹配评分。参数：job_ids（必填，传入抓取结果中的岗位ID列表，如"1,2,3"）。用户说"第一个"对应抓取结果中的"岗位ID: 1"即job_ids="1"，"前三个"对应job_ids="1,2,3"。不抓取，只匹配。
7. 生成面试报告 - 根据公司名称（可选岗位）生成面试宝典报告PDF
8. 文件解析 - 解析上传文件（图片/PDF/DOCX/MD/PPTX/XLSX/HTML）中的文字内容，调用时用文件名即可
9. OCR图片识别（旧版，建议用工具8替代）- 识别上传图片中的文字内容
10. 创建面试记录 - 根据文件解析的结果或管理员提供的信息创建面试宝典记录，支持录入薪资(salary)和公司简介(company_description)
11. 查询系统数据 - 查询面试记录列表、知识库内容、简历列表、岗位信息或系统数据统计汇总

【强制规则-数量词处理】调用抓取工具时，必须从用户消息中提取数字：用户说"一个"则max_count=1，"两个"则max_count=2，"三个"则max_count=3，依此类推。如果用户没说数字，才使用默认值5。这是必须执行的规则，请严格遵守。

【强制规则-意图判断】在调用任何工具前，你必须先判断用户意图：

**意图A：纯文件解析/OCR** — 用户想知道图片或文件里有什么内容。
触发词：解析图片内容、看看这张图、图片里是什么、帮我读一下这个文件、这是什么、OCR、识别这张图、提取图片文字、翻译图片内容
→ 动作：调用 parse_file_tool，将识别结果原文返回给用户。**不得调用 generate_resume_tool**，即使用户上传了JD图片、即使用户消息中有"简历"字样。
→ 示例：用户说"解析图片内容"或"这张图里写的什么"，即使图片内容看起来像JD，也只返回文字，不生成简历。
→ **重要：返回识别结果后，不得主动询问"是否需要生成简历"、"是否需要创建面试记录"等。用户没问的事不要提，直接结束回答。**
→ **重要：如果对话历史中已有同一文件的解析结果（包含 `tool=parse_file_tool args=[filename=xxx]` 的记录），直接复用历史结果回答，不要重新调用 parse_file_tool。除非用户明确说了"重新解析"、"再解析一次"、"重新识别"等，才重新调用工具。**

**意图B：生成简历** — 用户想让你根据图片或知识库生成一份新简历。
触发词：生成简历、做一份简历、制作简历、帮我写简历、根据这个生成简历、给我简历
→ 动作：如果上传了图片/文件，先调用 parse_file_tool 获取文字内容，提取目标岗位（target_job），然后调用 generate_resume_tool 生成简历。
→ 特殊：如果用户说"根据图片生成简历"但消息中只写了"生成简历"没有具体岗位名，先调用 parse_file_tool 从图片中提取岗位名，再调用 generate_resume_tool。

**意图C：创建面试记录** — 用户想根据图片/文件内容创建一条面试记录，或根据消息中的文字信息新增面试记录。
触发词：创建面试、新增面试、录入面试记录
→ 动作：
  - 如果同时有 `[文件: xxx]` 标记和文字消息：必须先解析全部文件，合并所有信息后调用 create_interview_record_tool（见下方流程）
  - 如果只有文字消息没有文件：直接从文字中提取字段调用 create_interview_record_tool

**意图D：修改面试记录** — 用户想修改已有面试记录的时间、地址等信息。
触发词：修改面试、调整面试、改面试时间、更新面试记录、面试改期
→ 动作：
  - Step 1: 调用 query_system_data_tool(entity_type="interview_guide") 查找要修改的记录，从结果中确认该记录的 id
  - Step 2: 调用 update_interview_record_tool(record_id=xxx, 只传需要改的字段)
  - 注意：必须使用正确的 record_id，不要随意猜测。如果查询结果中有多条，让用户确认是哪一条。

**意图E：创建面试记录并生成面试报告** — 用户要求先创建一条面试记录，然后立即生成对应的面试报告。
触发词：增加面试记录...生成面试报告、创建面试...生成报告、...然后...面试报告、记录...报告
→ 动作：参考上方【复合任务：创建面试记录并生成报告】流程执行。
→ 重要：如果用户说"X分的这家公司"（如"46分的这家公司"），到对话历史中查找匹配评分结果为X分的记录，从中提取公司名和岗位名。匹配结果在对话中的呈现格式为"岗位名 @ 公司名：X分"或"岗位名称 [岗位ID: N] @ 公司名：X分"。

【文件上传说明】
管理员上传文件后，消息中会以 `[文件: xxx.ext]` 标记。**系统不会自动解析文件内容**，你需要自行调用 parse_file_tool 来读取。
- 收到 `[文件: xxx.ext]` 标记后，根据上述用户意图决定是否调用 parse_file_tool
- 注意：调用工具时直接用文件名（如 `xxx.png` 或 `xxx.pdf`），不需要完整路径
- 如果确定文件需要读取但调用 parse_file_tool 失败，告诉用户解析失败的原因

【文件解析 + 创建面试记录流程】当管理员上传一张或多张图片/文件并要求创建面试记录时：
**注意：只要消息中有 `[文件: xxx]` 标记，Step 1 和 Step 2 是强制的，即使你从文字消息中已经知道了部分信息，也必须先解析文件。**
Step 1: 对每个文件调用「文件解析」工具获取文字内容。如果调用失败，必须告知用户哪个文件解析失败。
Step 2: 合并所有文件解析结果，从中提取以下字段（**字段值必须从文件解析结果中提取，不要仅从消息文字中提取，消息文字可能不完整**）：
  - company_name: 公司名称
  - job_title: 岗位名称
  - salary: 薪资范围（如 "11-15K"），从JD图片中提取
  - company_description: 公司简介全文——从结果中的"公司简介"段落提取完整文字，不要截断
  - jd_text: 岗位描述全文——将结果中"职位描述"、"岗位职责"、"任职要求"等JD相关内容完整填入，不要只填摘要
  - interview_time: 面试时间
  - interview_address: 面试地址
  - interview_round: 面试阶段（一面/二面/技术面/HR面）
  - hr_name: 联系人姓名
  - hr_phone: 联系人电话
Step 3: 调用 创建面试记录（create_interview_record_tool），将上面提取到的所有字段传入，不要遗漏
重要：jd_text和company_description要填入识别结果的完整原文，不要截断或自己概括

【强制规则-禁止捏造工具调用结果】当你执行 create_interview_record_tool、update_interview_record_tool 或任何其他工具时：
- 你必须实际调用该工具，不得绕过工具调用而直接回复"创建成功"之类的结果
- 如果你声称工具执行成功但未实际调用，系统会在最终回复前检测并提示"工具未被调用"
- 如果你不确定是否调用了工具，请检查你的回复中是否包含了工具调用的结果信息
- 所有工具返回的是JSON格式字符串，你必须解析JSON获取其中的data或error信息
- 如果你需要查看已有的面试记录，请使用 query_system_data_tool

【强制规则】在线搜索（工具3）始终可用，不得拒绝使用。当用户询问公司信息、人物背景、实时资讯、行业动态时，你必须优先调用 web_search_tool 搜索真实信息，不得替代搜索或声称搜索不可用。如果搜索工具返回错误，你仍然需要如实将错误信息告知用户，而不是自行编造「搜索功能不可用」的解释。切记：你手上就有搜索工具，随时可以调用。

【强制规则-生成简历】当用户意图是生成简历时，必须调用 generate_resume_tool 工具来实际生成，不得根据对话历史中的已有结果直接回复或自己编造结果。即使用户在同一个会话中重复发送相同的指令，或者之前已经生成过，也必须重新调用工具生成一份新的简历。

【强制规则-生成面试报告】当用户要求"生成面试报告"、"重新生成面试报告"、"再做一次"等时，必须调用 generate_interview_report_tool 工具实际生成，不得根据对话历史中的已有结果直接回复或说自己已生成。即使用户说"重新做"、"再试一次"，也必须重新调用工具。调用时需要的参数从对话历史中提取：公司名称为之前创建的面试记录对应的公司。
- 如果用户说"生成X公司的面试报告"但历史中还没有对应的面试记录，工具会返回错误"未找到面试记录"，此时必须告知用户需要先创建面试记录。
- 如果用户说"增加面试记录然后生成面试报告"，必须按【复合任务：创建面试记录并生成报告】流程先创建记录再生成报告。
- 个人信息始终从知识库获取，不需要询问用户"用知识库还是自己提供信息"
- 目标岗位（target_job）为必填。如果用户没说具体岗位，但在消息中上传了图片/文件（有【文件:xxx】标记），必须先调用 parse_file_tool 解析图片内容，从解析结果中提取目标岗位名称，再调用 generate_resume_tool。只有解析后仍无法确定岗位时，才可以追问用户。
- 如果用户提供了JD文本，填入jd参数；如果用户发送JD图片，先调用parse_file_tool识别文字，再将识别结果填入jd参数
- 如果用户没有提供JD，jd参数留空即可，会根据岗位和个人经历生成通用简历

【重要】所有工具返回的都是 JSON 字符串，格式为：
- 成功：{"ok": true, "data": "..."}
- 失败：{"ok": false, "error": "..."}
你需要解析 JSON 后，将 data 内容或 error 信息用自然语言告知管理员。

管理员提出修改知识库（改名、换经历、换人等）时，直接执行以下流程，不需要询问权限：
Step 1: 调用 knowledge_preview 传入用户的原文
Step 2: 展示预览结果给用户确认
Step 3: 用户确认后调用 knowledge_confirm 执行"""


# ============================================================
# LangGraph Agent
# ============================================================

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    _reflect_passed: bool  # True=通过(不显示), False=需修正


def _latest_user_input(messages: list) -> str:
    """Extract the latest human message text from the message list."""
    for msg in reversed(messages):
        if hasattr(msg, "type") and msg.type == "human":
            return (msg.content or "").strip()
        if isinstance(msg, HumanMessage):
            return (msg.content or "").strip()
    return ""


def call_model(state: AgentState):
    messages = state["messages"]
    # Prepend system prompt if the first message is not a system message
    # Read dynamically from settings so prompt changes take effect immediately
    if not messages or messages[0].type != "system":
        from langchain_core.messages import SystemMessage
        from services.agent_prompt_builder import AgentPromptBuilder
        # Try DB modular prompt first with intent detection based on user input
        user_input = _latest_user_input(messages)
        db_prompt = AgentPromptBuilder.build(user_input=user_input)
        if db_prompt:
            prompt = db_prompt
        else:
            prompt = getattr(settings, "AGENT_PROMPT", "") or DEFAULT_AGENT_PROMPT
        now_str = datetime.utcnow().strftime("%Y年%m月%d日 %H:%M")
        prompt = f"【当前时间】{now_str}\n\n{prompt}"
        messages = [SystemMessage(content=prompt)] + messages
    response = get_llm_with_tools().invoke(messages, timeout=120)
    return {"messages": [response]}


# Build graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)


def _is_task_cancelled(task_id: int) -> bool:
    """Check if this task was cancelled (a newer task replaced it)."""
    try:
        db = SessionLocal()
        try:
            from services.repository.container import RepoContainer
            repo = RepoContainer(db)
            t = repo.agent_task.get_by_id(task_id)
            return t is None or t.status == "cancelled"
        finally:
            db.close()
    except Exception:
        return False


def _gateway_tool_node(state: AgentState) -> dict:
    """Custom ToolNode that routes all tool calls through _gateway,
    persists events to DB, and pushes live events for real-time FSM streaming."""
    from langchain_core.messages import ToolMessage
    from services.output_audit import mask_pii
    session_id_local = _current_session_id.get()
    last_msg = state["messages"][-1]
    new_messages = []
    uid = get_current_user_id()
    ctx = {"user_id": uid}
    task_id = _current_task_id.get()
    task_id_val = task_id if isinstance(task_id, int) else 0
    _seq = [0]
    tool_calls = getattr(last_msg, "tool_calls", []) or []
    for tc in tool_calls:
        tool_name = tc["name"]
        tool_args = tc.get("args", {})

        # If task was cancelled (newer message sent), abort
        if task_id_val and _is_task_cancelled(task_id_val):
            msg = "⚠️ 任务已取消（检测到新消息），跳过执行"
            new_messages.append(ToolMessage(content=msg, name=tool_name, tool_call_id=tc.get("id", "")))
            continue

        call_data = {"tool": tool_name, "args": tool_args}

        # HITL: block until user confirms for sensitive tools
        if tool_name in SENSITIVE_TOOLS:
            confirm_id = uuid_mod.uuid4().hex[:16]

            call_data["sensitive"] = True
            call_data["requires_confirmation"] = True
            call_data["confirm_id"] = confirm_id

            save_event(session_id_local, task_id_val, "tool_call", call_data, _seq[0], user_id=uid)
            _seq[0] += 1
            _push_live_event({"type": "tool_call", "data": call_data})
            _push_live_event({"type": "fsm", "data": {"state": "tool_call", "tool": tool_name}})

            _push_live_event({"type": "status", "data": {"message": f"等待用户确认 {tool_name}..."}})

            # Poll DB for confirmation result (cross-worker safe)
            confirmed = False
            deadline = time.time() + _CONFIRM_TIMEOUT
            _heartbeat_interval = 30  # update task timestamp every 30s
            _last_heartbeat = time.time()
            while time.time() < deadline:
                # Heartbeat: keep task alive so stale-timeout doesn't fire
                if int(time.time() - _last_heartbeat) >= _heartbeat_interval:
                    try:
                        _hb_db = SessionLocal()
                        try:
                            _hb_repo = RepoContainer(_hb_db)
                            _hb_task = _hb_repo.agent_task.get_by_id(task_id_val)
                            if _hb_task:
                                _hb_task.updated_at = datetime.utcnow()
                                _hb_db.commit()
                        finally:
                            _hb_db.close()
                    except Exception:
                        pass
                    _push_live_event({"type": "status", "data": {"message": f"等待用户确认 {tool_name}...({int(deadline - time.time())}秒后超时)"}})
                    _last_heartbeat = time.time()

                db_poll = SessionLocal()
                try:
                    from services.repository.container import RepoContainer
                    poll_repo = RepoContainer(db_poll)
                    if task_id_val:
                        _t = poll_repo.agent_task.get_by_id(task_id_val)
                        if _t is None or _t.status == "cancelled":
                            confirmed = False
                            break
                    result_evt = db_poll.query(_AgentEventModel).filter(
                        _AgentEventModel.session_id == session_id_local,
                        _AgentEventModel.event_type == "tool_confirm_result",
                        _AgentEventModel.event_data.contains(confirm_id),
                    ).order_by(_AgentEventModel.created_at.desc()).first()
                    if result_evt:
                        import json as _json
                        result_data = _json.loads(result_evt.event_data or "{}")
                        confirmed = result_data.get("confirmed", False)
                        break
                except Exception:
                    db_poll.rollback()
                finally:
                    db_poll.close()
                time.sleep(_CONFIRM_POLL_INTERVAL)

            if not confirmed:
                msg = f"⚠️ 操作已取消：用户拒绝了 {tool_name} 的执行"
                new_messages.append(ToolMessage(content=msg, name=tool_name, tool_call_id=tc.get("id", "")))
                _push_live_event({"type": "tool_result", "data": {"tool": tool_name, "result_preview": msg}})
                _push_live_event({"type": "fsm", "data": {"state": "agent_think"}})
                continue
            # User confirmed — check task hasn't been cancelled during HITL polling
            if task_id_val and _is_task_cancelled(task_id_val):
                msg = "⚠️ 任务已取消（检测到新消息），跳过执行"
                new_messages.append(ToolMessage(content=msg, name=tool_name, tool_call_id=tc.get("id", "")))
                _push_live_event({"type": "tool_result", "data": {"tool": tool_name, "result_preview": msg}})
                _push_live_event({"type": "fsm", "data": {"state": "agent_think"}})
                continue
            # User confirmed — proceed to execution below
            _push_live_event({"type": "status", "data": {"message": f"用户已确认，正在执行 {tool_name}..."}})
        else:
            # Non-sensitive tool: push tool_call event now
            save_event(session_id_local, task_id_val, "tool_call", call_data, _seq[0], user_id=uid)
            _seq[0] += 1
            _push_live_event({"type": "tool_call", "data": call_data})
            _push_live_event({"type": "fsm", "data": {"state": "tool_call", "tool": tool_name}})

        # ── 工具参数校验与收集 ────────────────────────────
        from services.task.validator import validate_action
        _v_errors = validate_action(tool_name, tool_args)
        if _v_errors:
            _missing = "、".join(_v_errors)
            msg = (
                f"【参数收集】工具「{tool_name}」缺少以下必需参数: {_missing}。"
                f"请向用户询问这些信息后再调用该工具，不要自行编造参数值。"
            )
            save_event(session_id_local, task_id_val, "tool_result",
                       {"tool": tool_name, "result_preview": msg}, _seq[0], user_id=uid)
            _seq[0] += 1
            _push_live_event({"type": "tool_result", "data": {"tool": tool_name, "result_preview": msg}})
            _push_live_event({"type": "fsm", "data": {"state": "finish"}})
            new_messages.append(ToolMessage(content=msg, name=tool_name, tool_call_id=tc.get("id", "")))
            continue

        raw = _gateway.call_sync_to_text(tool_name, tool_args, ctx)

        safe_raw = mask_pii(raw)
        result_preview = (safe_raw[:300] + "...") if safe_raw and len(safe_raw) > 300 else (safe_raw or "")
        result_data = {"tool": tool_name, "result_preview": result_preview}
        save_event(session_id_local, task_id_val, "tool_result", result_data, _seq[0], user_id=uid)
        _seq[0] += 1
        _push_live_event({"type": "tool_result", "data": result_data})
        _push_live_event({"type": "fsm", "data": {"state": "finish"}})

        # 持久化工具调用结果（含文件名），后续轮次加载历史时可直接复用
        try:
            tool_args_str = ",".join(f"{k}={v}" for k, v in tool_args.items())
            save_message(session_id_local, "tool", f"tool={tool_name} args=[{tool_args_str}] result={raw}", user_id=uid)
        except Exception:
            pass

        new_messages.append(ToolMessage(content=raw, name=tool_name, tool_call_id=tc.get("id", "")))
    return {"messages": new_messages}


# ============================================================
# Reflection Node — review AI response for hallucinations
# ============================================================

def reflect_model(state: AgentState):
    """审查AI最后回复是否基于真实工具数据，防止幻觉。
    返回值：_reflect_passed=True 表示通过（不向对话追加任何内容）
              _reflect_passed=False 表示发现问题，追加修正指令"""
    messages = state["messages"]
    if not messages:
        return {"_reflect_passed": True}

    last_msg = messages[-1]
    msg_type = getattr(last_msg, "type", "")
    if msg_type != "ai":
        return {"_reflect_passed": True}

    tool_calls = getattr(last_msg, "tool_calls", [])
    if tool_calls:
        return {"_reflect_passed": True}

    import re as _re
    # 只检查最新一条用户消息中是否有新的文件标记
    # 不检查历史轮次——历史文件的结果已通过 _to_messages 注入上下文，Agent 可自行决定是否复用
    latest_human = None
    for m in reversed(messages):
        if getattr(m, "type", "") == "human":
            latest_human = m
            break
    if latest_human is not None:
        has_new_file = bool(
            _re.search(r'\[文件:\s*\S+\.\w+\]', str(getattr(latest_human, "content", "")))
        )
        if has_new_file:
            has_parse_this_turn = any(
                getattr(m, "name", "") == "parse_file_tool" or
                (getattr(m, "tool_calls", None) and any(tc.get("name") == "parse_file_tool" for tc in m.tool_calls))
                for m in messages
            )
            if not has_parse_this_turn:
                correction = SystemMessage(content="""【反思审查不通过】用户当前消息中包含文件标记，但你未调用 parse_file_tool 工具。

规则：只要用户最新消息中包含 [文件: ...] 标记，你必须先调用 parse_file_tool 读取文件内容，再基于真实内容回复。不得自行编造文件内容。

请立即调用 parse_file_tool 读取文件。""")
                return {"messages": [correction], "_reflect_passed": False}

    from services.ai_service import get_llm

    reflection_prompt = SystemMessage(content="""【反思审查】请严格审查AI最后一条回复是否存在以下问题：

1. **虚构工具调用**：AI是否声称调用了工具（如"已创建记录""已生成简历"）但对话历史中没有对应的工具调用返回结果（ToolMessage）？
2. **捏造数据**：AI是否编造了具体数据（数字、ID、名称等），而非来自工具返回？
3. **曲解数据**：AI是否曲解了工具返回的数据含义？
4. **信息遗漏**：工具返回了重要信息但AI没有告知用户？

基于对话历史逐条检查。如果全部通过，仅回复【通过】。
如果发现问题，回复【需修正】+ 具体问题描述。""")

    try:
        recent = messages[-8:]
        response = get_llm().invoke(recent + [reflection_prompt])
    except Exception:
        return {"_reflect_passed": True}

    content = getattr(response, "content", "") or ""
    if "【需修正】" in content:
        return {"messages": [response], "_reflect_passed": False}

    return {"_reflect_passed": True}


def route_after_agent(state: AgentState) -> str:
    """路由：有工具调用→tools，否则→reflect"""
    result = tools_condition(state)
    if result == END or result == "__end__":
        return "reflect"
    return result


def route_after_reflect(state: AgentState) -> str:
    """路由：审查通过→END，需修正→agent"""
    if state.get("_reflect_passed", True):
        return END
    return "agent"


# Build graph
workflow.add_node("reflect", reflect_model)
workflow.add_node("tools", _gateway_tool_node)
workflow.set_entry_point("agent")
workflow.add_conditional_edges("agent", route_after_agent)
workflow.add_edge("tools", "agent")
workflow.add_conditional_edges("reflect", route_after_reflect)

# Build graph — no persistent checkpointer.
# Conversation history is persisted via DB (load_history / save_message),
# so MemorySaver is redundant and causes hangs when a previous
# invocation with the same thread_id checkpoint is interrupted.
agent_executor = workflow.compile()

# Sensitive tools that require explicit user confirmation
SENSITIVE_TOOLS = {"knowledge_confirm"}


# ============================================================
# Memory Management
# ============================================================

def _to_messages(records: list) -> List[BaseMessage]:
    from langchain_core.messages import HumanMessage, AIMessage
    messages: List[BaseMessage] = []
    for r in records:
        content = (getattr(r, "content", None) or "")[:4000]
        role = getattr(r, "role", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant":
            messages.append(AIMessage(content=content))
        elif role == "tool":
            # 只保留 parse_file_tool 结果告诉 LLM 文件已解析
            # 其他工具调用记录不注入上下文，防止 LLM 重放旧工具
            _tool_name = content.split(" ")[0].split("=")[-1] if content.startswith("tool=") else ""
            if _tool_name == "parse_file_tool":
                messages.append(HumanMessage(content=f"[历史工具调用记录: {content}]"))
    return messages


def load_history(session_id: str, max_turns: int = 10, user_id: str = "") -> List[BaseMessage]:
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        records = repo.agent_conversation.list_recent_by_session(
            session_id, user_id=user_id, max_turns=max_turns
        )
        return _to_messages(records)
    finally:
        db.close()


def get_history(session_id: str, user_id: str = "", max_records: int = 50) -> list[dict]:
    db = SessionLocal()
    try:
        from services.repository.container import RepoContainer
        repo = RepoContainer(db)
        records = repo.agent_conversation.list_by_session(
            session_id, user_id=user_id, limit=max_records
        )
        result = []
        from services.models.interview_guide import InterviewGuide
        for r in records:
            item = {
                "role": r.role,
                "content": r.content,
                "resume_id": r.resume_id,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            guide_id = getattr(r, "guide_id", None)
            if guide_id is None and r.role == "assistant" and "面试报告已生成完成" in (r.content or ""):
                import re as _re_hist_co
                _m = _re_hist_co.search(r'公司[：:]\s*(.+?)[\n\r]', r.content or "")
                if _m:
                    _company = _m.group(1).strip()
                    _guide = db.query(InterviewGuide).filter(
                        InterviewGuide.company_name == _company
                    ).order_by(InterviewGuide.id.desc()).first()
                    if _guide:
                        guide_id = _guide.id
            if guide_id is not None:
                item["guide_id"] = guide_id
            result.append(item)
        return result
    finally:
        db.close()


def save_task(session_id: str, user_id: str, request: str, status: str = "pending"):
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        repo.agent_task.cancel_pending(session_id, user_id)
        task = repo.agent_task.create_task(session_id, user_id, request, status)
        return task.id
    finally:
        db.close()


def cancel_running_task(session_id: str, user_id: str = "") -> bool:
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        tasks = repo.agent_task.list(
            session_id=session_id,
            status__in=["pending", "running"],
        )
        # Filter by user_id if specified
        if user_id:
            tasks = [t for t in tasks if t.user_id == user_id]
        for t in tasks:
            t.status = "cancelled"
            t.response = "用户取消"
            t.updated_at = datetime.utcnow()
        if tasks:
            db.commit()
            for t in tasks:
                save_message(t.session_id, "assistant", "⏹️ 任务已取消", user_id=user_id or t.user_id)
            return True
        return False
    except Exception:
        db.rollback()
        return False
    finally:
        db.close()


def update_task(task_id: int, status: str = "completed", response: str = "", resume_id: int = None):
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        task = repo.agent_task.get_by_id(task_id)
        if task:
            task.status = status
            if response:
                task.response = response
            task.resume_id = resume_id
            task.updated_at = datetime.utcnow()
            db.commit()
    finally:
        db.close()


def get_task(session_id: str, user_id: str = ""):
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        task = repo.agent_task.get_latest(session_id, user_id=user_id)
        if task:
            if task.status == "running" and task.updated_at:
                from datetime import datetime, timezone
                ref_now = datetime.now(timezone.utc) if task.updated_at.tzinfo else datetime.utcnow()
                ref_updated = task.updated_at.replace(tzinfo=None) if task.updated_at.tzinfo else task.updated_at
                elapsed = (ref_now - ref_updated).total_seconds()
                if elapsed > 600:
                    task.status = "failed"
                    task.response = "任务超时（前端连接断开）"
                    task.updated_at = datetime.utcnow()
                    db.commit()
            return {
                "task_id": task.id,
                "status": task.status,
                "request": task.request,
                "response": task.response,
                "resume_id": task.resume_id,
                "created_at": task.created_at.isoformat() if task.created_at else None,
                "updated_at": task.updated_at.isoformat() if task.updated_at else None,
            }
        return None
    finally:
        db.close()


def save_event(session_id: str, task_id: int, event_type: str, event_data: dict, sequence: int, user_id: str = ""):
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        repo.agent_event.add_event(session_id, task_id, event_type, event_data, sequence, user_id=user_id)
    except Exception as e:
        print(f"[agent_service] save_event error: {e}")
        db.rollback()
    finally:
        db.close()


def get_events(session_id: str, user_id: str = "") -> list[dict]:
    from services.repository.container import RepoContainer
    from services.models.agent_event import AgentEvent
    db = SessionLocal()
    try:
        q = db.query(AgentEvent).filter(AgentEvent.session_id == session_id)
        if user_id:
            q = q.filter(AgentEvent.user_id == user_id)
        records = q.order_by(AgentEvent.sequence).all()
        return [
            {
                "type": r.event_type,
                "data": json.loads(r.event_data) if r.event_data else {},
                "sequence": r.sequence,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in records
        ]
    except Exception as e:
        print(f"[agent_service] get_events error: {e}")
        return []
    finally:
        db.close()


def delete_events(session_id: str, task_id: int):
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        repo.agent_event.delete_by_session_task(session_id, task_id)
    except Exception as e:
        print(f"[agent_service] delete_events error: {e}")
        db.rollback()
    finally:
        db.close()


def save_message(session_id: str, role: str, content: str, user_id: str = "", resume_id: int | None = None, guide_id: int | None = None):
    """保存单条消息到数据库"""
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        repo.agent_conversation.add_message(session_id, role, content, user_id=user_id, resume_id=resume_id, guide_id=guide_id)
    finally:
        db.close()


def clear_history(session_id: str, user_id: str = ""):
    """清空指定session的Agent对话历史和任务记录"""
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        repo.agent_conversation.clear_by_session(session_id, user_id=user_id)
        repo.agent_task.delete_by_session(session_id, user_id)
        repo.agent_event.delete_by_session(session_id, user_id)
    finally:
        db.close()


def clear_all_history(user_id: str = ""):
    """清空Agent对话历史，若指定user_id则只清该用户的"""
    from services.repository.container import RepoContainer
    db = SessionLocal()
    try:
        repo = RepoContainer(db)
        repo.agent_conversation.clear_all_by_user(user_id)
    finally:
        db.close()


# ============================================================
# Agent Runner
# ============================================================

def run_agent(session_id: str, user_message: str, user_id: str = "") -> dict:
    """
    运行Agent：加载历史 → 添加用户消息 → 执行Agent → 保存回复
    返回: {"response": str, "steps": list}
    steps 中包含工具调用链信息，用于前端展示思维过程
    """
    is_safe, reason = check_message(user_message)
    if not is_safe:
        print(f"[agent_service] injection blocked for session {session_id}: {reason}")
        save_message(session_id, "user", user_message, user_id=user_id)
        save_message(session_id, "assistant", reason, user_id=user_id)
        return {"response": reason, "steps": []}

    # When the user uploads new files (message contains [文件: markers),
    # limit history to 2 turns to prevent old context (e.g., resume generation)
    # from biasing the current request (e.g., "解析图片内容").
    import re as _re
    has_new_files = bool(_re.search(r'\[文件:\s*\w+\.\w+\]', user_message))
    history_max_turns = 2 if has_new_files else 10
    history = load_history(session_id, max_turns=history_max_turns, user_id=user_id)

    # 添加用户消息
    history.append(HumanMessage(content=user_message))
    save_message(session_id, "user", user_message, user_id=user_id)

    # 执行Agent（带超时保护）— 使用 copy_context 确保 contextvar 在 Python 3.10 线程池中正确传播
    with Timer("agent.run_agent") as timer:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            _captured_ctx = contextvars.copy_context()
            def _run_in_context(uid: str) -> dict:
                set_current_user_id(uid)
                return agent_executor.invoke(
                    {"messages": history},
                    {"recursion_limit": 15},
                )
            future = pool.submit(_captured_ctx.run, _run_in_context, user_id)
            try:
                result = future.result(timeout=300)
                elapsed = timer.elapsed
                print(f"[metrics] agent.run_agent session={session_id} duration={elapsed:.2f}s")
            except concurrent.futures.TimeoutError:
                print(f"[agent_service] run_agent timeout for session {session_id}")
                save_message(session_id, "assistant", "请求超时，请稍后重试", user_id=user_id)
                return {"response": "请求超时，请稍后重试", "steps": []}
            except Exception as e:
                print(f"[agent_service] run_agent error for session {session_id}: {type(e).__name__}: {e}")
                save_message(session_id, "assistant", f"处理失败：{type(e).__name__}", user_id=user_id)
                return {"response": f"处理失败：{type(e).__name__}", "steps": []}

    from langchain_core.messages import AIMessage as _AIMessage

    # 提取工具调用链（用于前端展示）
    steps: List[dict] = []
    for msg in result["messages"]:
        if isinstance(msg, _AIMessage) and hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                _gateway.audit_tool_call(
                    tc["name"], tc.get("args", {}),
                    {"user_id": user_id, "session_id": session_id},
                )
                step = {
                    "type": "tool_call",
                    "tool": tc["name"],
                    "args": tc.get("args", {}),
                }
                if tc["name"] in SENSITIVE_TOOLS:
                    step["sensitive"] = True
                    step["requires_confirmation"] = True
                steps.append(step)
        elif hasattr(msg, "type") and msg.type == "tool":
            steps.append({
                "type": "tool_result",
                "tool": getattr(msg, "name", ""),
                "result_preview": (msg.content[:300] + "...") if msg.content and len(msg.content) > 300 else (msg.content or ""),
            })

    # 提取最终回复：从后往前找第一条纯文本 AI 消息（跳过 tool call 消息）
    reply = "处理完成"
    for msg in reversed(result["messages"]):
        if isinstance(msg, _AIMessage):
            tc = getattr(msg, "tool_calls", None) or []
            content = (msg.content or "").strip()
            if content and not tc:
                reply = content
                break

    # 提取 resume_id
    resume_id = None
    for msg in result["messages"]:
        if hasattr(msg, "type") and msg.type == "tool" and msg.name == "generate_resume_tool":
            try:
                parsed = json.loads(msg.content or "{}")
                if parsed.get("ok") and parsed.get("data"):
                    import re
                    m = re.search(r"ID:(\d+)", parsed["data"])
                    if m:
                        resume_id = int(m.group(1))
                if resume_id is None and parsed.get("extra"):
                    resume_id = parsed["extra"].get("db_id")
            except (json.JSONDecodeError, ValueError):
                pass

    # 保存助手消息
    save_message(session_id, "assistant", reply, user_id=user_id, resume_id=resume_id)

    # Record token usage with user_id
    _record_usage(result, user_id)

    return {
        "response": reply,
        "steps": steps,
        "resume_id": resume_id,
    }


def _record_usage(result: dict, user_id: str = ""):
    """Extract token usage from agent result and record it."""
    try:
        for msg in result.get("messages", []):
            from langchain_core.messages import AIMessage as _AIMessage
            if isinstance(msg, _AIMessage) and hasattr(msg, "usage_metadata") and msg.usage_metadata:
                um = msg.usage_metadata
                usage_service.record(
                    user_id=user_id,
                    input_tokens=um.get("input_tokens", 0) or um.get("prompt_tokens", 0),
                    output_tokens=um.get("output_tokens", 0) or um.get("completion_tokens", 0),
                )
                break
    except Exception:
        pass


# ============================================================
# FSM — Finite State Machine for agent execution tracking
# ============================================================


class AgentFSM:
    """Tracks agent execution state for frontend visibility."""

    states = ["init", "agent_think", "tool_call", "finish", "error"]

    _valid_transitions = {
        "init": {"agent_think"},
        "agent_think": {"tool_call", "finish", "error"},
        "tool_call": {"agent_think", "error"},
        "error": {"agent_think", "finish"},
    }

    def __init__(self, session_id: str, max_steps: int = 15):
        self.session_id = session_id
        self.current = "init"
        self.step = 0
        self.max_steps = max_steps

    def transit(self, to_state: str) -> bool:
        if to_state not in self._valid_transitions.get(self.current, set()):
            print(f"[fsm] invalid transition: {self.current} -> {to_state}")
            return False
        self.current = to_state
        if to_state in ("agent_think", "tool_call"):
            self.step += 1
        return True

    def to_event(self, extra: dict | None = None) -> dict:
        data = {
            "state": self.current,
            "step": self.step,
            "max_steps": self.max_steps,
        }
        if extra:
            data.update(extra)
        return {"type": "fsm", "data": data}


# ============================================================
# SSE Streaming Agent
# ============================================================


async def stream_agent_events(session_id: str, user_message: str, user_id: str = ""):
    """Run agent and yield SSE events in real-time as execution progresses.

    Uses a thread-safe live event queue so FSM/tool_call/tool_result events
    are pushed by _gateway_tool_node during agent execution and yielded
    progressively to the SSE stream — giving the frontend true real-time
    visibility into the agent's thinking process.
    """
    import asyncio
    is_safe, reason = check_message(user_message)
    if not is_safe:
        yield {"type": "error", "data": {"message": reason}}
        return

    task_id = save_task(session_id, user_id, user_message, status="running")

    # Cleanup: delete events older than 24h to prevent unbounded growth
    db_cleanup = SessionLocal()
    try:
        from services.repository.container import RepoContainer as _RC
        _RC(db_cleanup).agent_event.delete_before(datetime.utcnow() - timedelta(hours=24), user_id=user_id)
    except Exception:
        db_cleanup.rollback()
    finally:
        db_cleanup.close()

    import re as _re2
    has_new_files = bool(_re2.search(r'\[文件:\s*\w+\.\w+\]', user_message))
    history_max_turns = 2 if has_new_files else 10
    history = load_history(session_id, max_turns=history_max_turns, user_id=user_id)
    history.append(HumanMessage(content=user_message))
    save_message(session_id, "user", user_message, user_id=user_id)
    history_input_count = len(history)

    # ── Live event queue: _gateway_tool_node pushes events during invoke ──
    live_queue: deque = deque()
    token_queue = _live_events_queue.set(live_queue)
    token_task = _current_task_id.set(task_id)
    token_session = _current_session_id.set(session_id)
    _flush = lambda: asyncio.sleep(0.02)

    # Yield initial FSM state immediately
    fsm = AgentFSM(session_id)
    fsm.transit("agent_think")
    _fsev = fsm.to_event()
    save_event(session_id, task_id, _fsev["type"], _fsev.get("data", {}), 0, user_id=user_id)
    yield _fsev
    await _flush()

    # Capture ContextVars for propagation to worker thread
    _live_queue_ref = live_queue
    _task_id_ref = task_id
    _session_id_ref = session_id

    # Shared holder for result (set by worker thread even if async generator is GC'd)
    _result_holder: list[dict | None] = [None]

    with Timer("agent.stream_agent") as timer:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            def _worker(uid: str, lq, tid, sid) -> dict:
                """Worker thread — persists result to DB even if async gen is GC'd."""
                set_current_user_id(uid)
                _live_events_queue.set(lq)
                _current_task_id.set(tid)
                _current_session_id.set(sid)
                from langchain_core.messages import AIMessage as _AIMsg
                try:
                    # Check cancellation before starting invoke
                    if _is_task_cancelled(tid):
                        update_task(tid, status="cancelled", response="任务已取消")
                        return {"messages": []}

                    # ── File Resolution ─────────────────────────────────────
                    _last_user_text = ""
                    for m in reversed(history):
                        if hasattr(m, "type") and m.type == "human":
                            _last_user_text = (m.content or "")[:5000]
                            break

                    if _last_user_text and "[文件:" in _last_user_text:
                        import re as _re
                        from services.container import Container
                        _resolved = _last_user_text
                        _file_ids_in_text = _re.findall(r'\[文件:\s*([^\]]+)\]', _resolved)
                        for _fid in _file_ids_in_text:
                            _call_data = {"tool": "parse_file_tool", "args": {"filename": _fid}}
                            _push_live_event({"type": "tool_call", "data": _call_data})
                            _push_live_event({"type": "fsm", "data": {"state": "tool_call", "tool": "parse_file_tool"}})
                            try:
                                with Container(user_id) as _c:
                                    _fp = _c.file_service.resolve_file(_fid, user_id)
                                    _ft = _c.file_service.parse_document(_fp)
                                if _ft:
                                    snippet = _ft[:5000]
                                    _resolved = _resolved.replace(f"[文件: {_fid}]", f"[上传文件内容]\n{snippet}\n[/上传文件内容]", 1)
                                    _snippet_preview = (snippet[:300] + "...") if len(snippet) > 300 else snippet
                                    _push_live_event({"type": "tool_result", "data": {"tool": "parse_file_tool", "result_preview": _snippet_preview}})
                                    _push_live_event({"type": "fsm", "data": {"state": "finish"}})
                            except Exception as _e:
                                _push_live_event({"type": "status", "data": {"message": f"文件解析失败: {_e}"}})
                        if _resolved != _last_user_text:
                            _last_user_text = _re.sub(r'\[文件:\s*[^\]]+\]\n?', '', _resolved[:6000])
                            # 同步更新 history，避免 LangGraph 再次看到 [文件: xxx] 标记而重复解析
                            history[-1].content = _resolved[:6000]

                    # ── Intent Rewrite (fast path) ──────────────────────────
                    try:
                        from services.task.intent_rewriter import rewrite
                        from services.task.validator import validate_action as _va
                        from services.tool_meta import TOOL_METADATA as _TOOL_META

                        def _format_history_for_tools(history: list) -> str:
                            parts = []
                            for m in history:
                                if hasattr(m, "type"):
                                    _content = (m.content or '')
                                    # Strip file markers from history context to avoid LLM re-calling parse
                                    import re as _re_hist
                                    _content = _re_hist.sub(r'\[文件:\s*[^\]]+\]', '', _content)
                                    _content = _re_hist.sub(r'\[上传文件内容\].*?\[/上传文件内容\]', '', _content, flags=_re_hist.DOTALL)
                                    _content = _content.strip()
                                    if m.type == "human":
                                        parts.append(f"用户: {_content}")
                                    elif m.type == "ai":
                                        parts.append(f"助手: {_content}")
                            return "\n".join(parts)

                        def _build_tool_prompt() -> str:
                            _lines = []
                            _intent_rewrite_tools = {
                                "kimi_crawl_tool", "match_jobs_tool", "generate_resume_tool",
                                "create_interview_record_tool", "update_interview_record_tool",
                                "generate_interview_report_tool", "cancel_report_tool",
                                "check_report_status_tool",
                                "web_search_tool", "knowledge_preview", "knowledge_rebuild_vector",
                                "query_sessions_tool", "query_system_data_tool",
                                "parse_file_tool",
                            }
                            for _name, _meta in _TOOL_META.items():
                                if _name not in _intent_rewrite_tools:
                                    continue
                                _params_str = ", ".join([f"{p.name}({p.type})" for p in _meta.parameters])
                                _lines.append(f"{_name}({_meta.category}) [{_params_str}]")
                            return "可选工具：" + ", ".join(_lines) + "\n\n"

                        def _llm_rewrite(text: str, h: list | None = None) -> list[dict] | None:
                            try:
                                _push_live_event({"type": "status", "data": {"message": "正在分析你的意图..."}})
                                _llm = _get_intent_llm()
                                _ctx_lines = []
                                if h and len(h) > 1:
                                    _ctx = _format_history_for_tools(h[:-1])
                                    if _ctx.strip():
                                        _ctx_lines.append("对话历史：")
                                        _ctx_lines.append(_ctx)
                                        _ctx_lines.append("")
                                _ctx_lines.append("当前用户输入：")
                                _ctx_lines.append(text)
                                _prompt_context = "\n".join(_ctx_lines)
                                _tool_prompt = _build_tool_prompt()
                                _resp = _llm.invoke([
                                HumanMessage(content=(
                                    "根据用户的当前输入，从可选工具中选择最匹配的一个或多个工具，返回JSON数组。\n"
                                    "只返回JSON数组，不要多余文字。\n\n"
                                    f"{_tool_prompt}"
                                    "意图到工具的对应关系（按优先级匹配）：\n"
                                    '1. 用户说「搜索/抓取/找」岗位/工作 → kimi_crawl_tool（搜索招聘岗位）\n'
                                    '2. 用户说「生成/做/创建/制作」+「简历」→ generate_resume_tool（生成简历PDF）\n'
                                     '2b. 用户说「再做/再来一份/重新生成」→ 重复对话历史中最近一次使用的工具，参数从历史中提取\n'
                                    '3. 用户说「匹配/评分/分析」岗位 → match_jobs_tool（对已抓取的岗位匹配评分）\n'
                                     '4. 用户说「创建/增加面试记录」+ 公司/岗位 → create_interview_record_tool，company_name 和 job_title 从对话历史中提取（参考最近的匹配结果来理解用户的指代，如「高分的」「第一个」「杭州的」等）\n'
                                     '5. 用户说「生成/做面试报告」→ generate_interview_report_tool，company 从对话历史中提取（参考最近的匹配结果来理解用户的指代）\n'
                                    '6. 用户说「修改/调整/改期面试记录」→ 先用 query_system_data_tool 查记录ID，再用 update_interview_record_tool\n'
                                    '7. 用户说「查询/查看/统计」数据 → query_system_data_tool 或 query_sessions_tool\n'
                                    '8. 用户说「搜索/查一下」+ 实时信息 → web_search_tool\n'
                                    '9. 用户说「取消/删除报告」→ cancel_report_tool\n'
                                    '10. 用户说「检查/查看报告状态」→ check_report_status_tool\n'
                                     '11. 用户上传了文件（[上传文件内容]标记）→ 从内容中提取参数直接传给对应工具，不要再用 parse_file_tool\n'
                                     '    generate_resume_tool: 如果内容是招聘岗位描述（含「岗位职责」「任职要求」「薪资」「K」「岗位描述」等）→ 用 jd 参数；如果是个人简历内容（含「工作经历」「教育背景」「专业技能」等）→ 用 raw_content 参数\n\n'
                                    "注意事项：\n"
                                    "- 如果用户一句话里包含多个意图（用「然后」「同时」「再」连接），同时返回对应多个工具\n"
                                    ' - 用户说「匹配第N个/第二个/第三个」→ 只调用 match_jobs_tool，不要其他工具\n'
                                    "- 每个工具在JSON数组中最多出现一次\n"
                                    "- 从用户输入和对话历史中提取参数，不要编造\n"
                                    f"{_prompt_context}\n\n"
                                     '示例1: [{"tool": "kimi_crawl_tool", "params": {"keywords": "前端", "city": "北京"}}]\n'
                                      '示例2: [{"tool": "generate_interview_report_tool", "params": {"company": "杭州某某科技有限公司"}}]\n'
                                      '示例3（多个意图）: "抓取两个产品经理的岗位然后匹配" → [{"tool": "kimi_crawl_tool", "params": {"keywords": "产品经理", "max_count": 2}}, {"tool": "match_jobs_tool", "params": {}}]\n'
                                    '如果不匹配任何工具，返回 []。'
                                ))
                                ])
                                content = (_resp.content or "").strip()
                                if content and content != "[]":
                                    try:
                                        parsed = json.loads(content)
                                        if isinstance(parsed, list) and len(parsed) > 0:
                                            _push_live_event({"type": "status", "data": {"message": f"意图分析完成，需要调用 {len(parsed)} 个工具"}})
                                            return parsed
                                    except json.JSONDecodeError:
                                        pass
                            except Exception:
                                pass
                            return None

                        _rewrite_actions = rewrite(_last_user_text, history, _llm_rewrite)
                        if _rewrite_actions:
                            import re as _fe_re

                            # 去重：同名工具只保留第一个
                            _seen = set()
                            _deduped = []
                            for _act in _rewrite_actions:
                                _tn = _act.get("tool", "")
                                if _tn not in _seen:
                                    _seen.add(_tn)
                                    _deduped.append(_act)
                            _rewrite_actions = _deduped

                            # 从 [上传文件内容] 块中提取 JD 文本，自动填入 generate_resume_tool 的 jd 参数
                            _fe_match = _fe_re.search(r'\[上传文件内容\]\n(.+?)\n\[/上传文件内容\]', _last_user_text, _fe_re.DOTALL)
                            if _fe_match:
                                _fe_content = _fe_match.group(1).strip()
                                for _act in _rewrite_actions:
                                    if _act.get("tool") == "generate_resume_tool":
                                        _p = _act.setdefault("params", {})
                                        if not _p.get("jd") and not _p.get("raw_content"):
                                            _p["jd"] = _fe_content
                                        if not _p.get("target_job"):
                                            _fe_tj = _fe_re.search(r'^(.+?)\s*\d', _fe_content) or _fe_re.search(r'(.+?)(?:岗位|职位|工作)', _fe_content)
                                            if _fe_tj:
                                                _p["target_job"] = _fe_tj.group(1).strip()
                                        break

                            # 校验参数，收集缺失项
                            _all_valid = True
                            _v_errs_combined = []
                            for _act in _rewrite_actions:
                                _v_errors = _va(_act["tool"], _act.get("params", {}))
                                if _v_errors:
                                    _all_valid = False
                                    _v_errs_combined.extend(_v_errors)

                            # 用 LLM 从对话历史中抽取缺失参数（替代正则）
                            if not _all_valid:
                                _re_post = __import__('re')
                                _missing_by_tool = {}
                                for _v_err in _v_errs_combined:
                                    _pm = _re_post.search(r"'(\w+)'", _v_err)
                                    if _pm:
                                        _pn = _pm.group(1)
                                        _missing_by_tool.setdefault(_pn, True)
                                if _missing_by_tool:
                                    _hist_text_parts = []
                                    for _m in history:
                                        _t = getattr(_m, "content", "") or ""
                                        if isinstance(_t, list):
                                            _t = " ".join(str(b.get("text", "")) for b in _t if isinstance(b, dict) and b.get("type") == "text")
                                        _role = "用户" if getattr(_m, "type", "") == "human" else "助手"
                                        _hist_text_parts.append(f"{_role}: {_t[:500]}")
                                    _hist_text = "\n".join(_hist_text_parts)
                                    _extract_prompt = (
                                        "从以下对话历史中提取缺失的参数值，返回 JSON 对象。\n"
                                        f"需要提取的参数: {', '.join(_missing_by_tool.keys())}\n\n"
                                        "对话历史：\n"
                                        f"{_hist_text}\n\n"
                                        "最新用户输入：\n"
                                        f"{_last_user_text}\n\n"
                                        "只返回 JSON，不要多余文字。找不到的字段设为空字符串。\n"
                                        "示例：{\"company_name\": \"杭州某某科技有限公司\", \"job_title\": \"产品经理\"}"
                                    )
                                    try:
                                        _el = _get_intent_llm()
                                        _er = _el.invoke([HumanMessage(content=_extract_prompt)])
                                        _ec = (_er.content or "").strip()
                                        if _ec:
                                            _ep = json.loads(_ec)
                                            if isinstance(_ep, dict):
                                                for _act in _rewrite_actions:
                                                    _pa = _act.setdefault("params", {})
                                                    for _k, _v in _ep.items():
                                                        if _v and not _pa.get(_k):
                                                            _pa[_k] = str(_v).strip()
                                                # 重新校验
                                                _all_valid = True
                                                _v_errs_combined = []
                                                for _act in _rewrite_actions:
                                                    _v_errors = _va(_act["tool"], _act.get("params", {}))
                                                    if _v_errors:
                                                        _all_valid = False
                                                        _v_errs_combined.extend(_v_errors)
                                    except Exception:
                                        pass

                            if not _all_valid:
                                _tool_names_set = {_a.get("tool", "") for _a in _rewrite_actions}
                                _missing_params_list = []
                                for _v_err in _v_errs_combined:
                                    _pm = _re_post.search(r"'(\w+)'", _v_err)
                                    if _pm:
                                        _missing_params_list.append(_pm.group(1))
                                _nat_msgs = []
                                for _pn in _missing_params_list:
                                    if _pn == "company_name":
                                        _nat_msgs.append("请问要给哪个公司添加面试记录？")
                                    elif _pn == "job_title":
                                        _nat_msgs.append("请问岗位名称是什么？")
                                    elif _pn in ("jd", "raw_content"):
                                        _nat_msgs.append("请提供职位描述（JD）")
                                    else:
                                        _nat_msgs.append(f"缺少必需参数「{_pn}」")
                                _raw_missing = "；".join(set(_v_errs_combined))
                                _reply = "\n".join(_nat_msgs) if _nat_msgs else f"请提供以下缺失信息：{_raw_missing}"
                                save_message(sid, "assistant", _reply, user_id=uid)
                                update_task(tid, status="completed", response=_reply)
                                _result_holder[0] = {
                                    "messages": list(history) + [AIMessage(content=_reply)],
                                    "resume_id": None,
                                    "guide_id": None,
                                }
                                return {"messages": list(history) + [AIMessage(content=_reply)]}

                            if _all_valid:
                                _resume_id_ir = None
                                _guide_id_ir = None
                                _push_live_event({"type": "fsm", "data": {
                                    "state": "tool_call", "step": 1,
                                    "max_steps": len(_rewrite_actions)
                                }})

                                # 按工具类型和参数动态估算时间
                                _first_tool_name = _rewrite_actions[0].get("tool", "")
                                _first_params = _rewrite_actions[0].get("params", {})
                                _est_msg = "正在处理"
                                if _first_tool_name == "generate_resume_tool":
                                    _est_msg = "正在生成简历（约45秒）..."
                                elif _first_tool_name == "kimi_crawl_tool":
                                    _max_c = int(_first_params.get("max_count", 5))
                                    _est_sec = 25 + 12 * max(1, min(_max_c, 10))
                                    _est_msg = f"正在抓取 {_max_c} 个岗位（约{_est_sec}秒）..."
                                elif _first_tool_name == "match_jobs_tool":
                                    _est_msg = "正在匹配评分（约60秒）..."
                                elif _first_tool_name == "web_search_tool":
                                    _est_msg = "正在搜索（约3秒）..."
                                elif _first_tool_name == "parse_file_tool":
                                    _est_msg = "正在解析文件..."
                                elif _first_tool_name == "create_interview_record_tool":
                                    _est_msg = "正在创建面试记录..."
                                elif _first_tool_name == "generate_interview_report_tool":
                                    _est_msg = "正在生成面试报告（约3-5分钟）..."
                                if len(_rewrite_actions) > 1:
                                    _est_msg += f"，共 {len(_rewrite_actions)} 个步骤"
                                _push_live_event({"type": "status", "data": {"message": _est_msg}})

                                if len(_rewrite_actions) >= 2:
                                    from services.task.models import Action as _Act
                                    from services.task.templates import match_template as _match_tmpl
                                    from services.tool_meta import TOOL_METADATA as _TM
                                    from langchain_core.messages import HumanMessage as _HM
                                    _ESTIMATED_TIME = {
                                        "generate_resume_tool": "正在生成简历（约45秒）...",
                                        "kimi_crawl_tool": "正在抓取岗位...",
                                        "match_jobs_tool": "正在匹配评分（约60秒）...",
                                        "web_search_tool": "正在搜索（约3秒）...",
                                        "parse_file_tool": "正在解析文件...",
                                        "create_interview_record_tool": "正在创建面试记录...",
                                        "generate_interview_report_tool": "正在生成面试报告（约3-5分钟）...",
                                    }
                                    # 按拓扑序顺序执行工具（在当前线程，避免 ThreadPoolExecutor 丢失 context var）
                                    def _llm_decompose(prompt: str) -> str:
                                        try:
                                            _llm = _get_admin_llm()
                                            _resp = _llm.invoke([_HM(content=prompt)])
                                            return (_resp.content or "").strip()
                                        except Exception:
                                            return ""
                                    _engine = TaskDecompositionEngine(llm_call=_llm_decompose)
                                    _root = _engine.decompose(_rewrite_actions, _last_user_text)
                                    if _root is not None:
                                        from services.task.validator import validate_dag
                                        _errors = validate_dag(_root)
                                        if not _errors:
                                            from services.task.scheduler import topological_sort as _tsort
                                            _results = {}
                                            for _layer in _tsort(_root.dag):
                                                for _aid in _layer:
                                                    _act = None
                                                    for _sub in _root.dag.nodes.values():
                                                        for _a in _sub.actions:
                                                            if _a.action_id == _aid:
                                                                _act = _a
                                                                break
                                                    if not _act:
                                                        continue
                                                    _params = dict(_act.input_params)
                                                    _est_msg_step = _ESTIMATED_TIME.get(_act.tool, "正在处理")
                                                    _push_live_event({"type": "status", "data": {"message": _est_msg_step}})
                                                    _push_live_event({"type": "tool_call", "data": {"tool": _act.tool, "args": _params}})
                                                    _raw = _gateway.call_sync_to_text(_act.tool, _params, {"user_id": uid})
                                                    _parsed = _raw
                                                    try:
                                                        _jp = json.loads(_raw)
                                                        _parsed = _jp
                                                        _data = _jp.get("data", "") if _jp.get("ok") else ""
                                                        if _data:
                                                            _msg = str(_data)[:200]
                                                            _push_live_event({"type": "status", "data": {"message": _msg}})
                                                    except Exception:
                                                        pass
                                                    _results[_act.output_key] = _parsed
                                                    _push_live_event({"type": "tool_result", "data": {"tool": _act.tool, "result_preview": "执行完成"}})
                                            # 用 LLM 将结果转为自然语言
                                            _summary_parts = []
                                            for _key, _val in _results.items():
                                                if isinstance(_val, dict) and _val.get("ok"):
                                                    _d = _val.get("data", "")
                                                    _summary_parts.append(str(_d) if _d else f"{_key} 执行成功")
                                                elif isinstance(_val, dict) and not _val.get("ok"):
                                                    _summary_parts.append(f"{_key} 执行失败: {_val.get('error', '未知错误')}")
                                                else:
                                                    _summary_parts.append(f"{_key}: {str(_val)[:200]}")
                                            _raw_summary = "\n".join(_summary_parts)
                                            try:
                                                _fmt_llm = _get_admin_llm()
                                                _fmt_resp = _fmt_llm.invoke([_HM(content=(
                                                    "将以下工具执行结果用简洁的自然语言回复用户（不要加【】前缀，不要重复工具名）：\n\n"
                                                    f"{_raw_summary}\n\n"
                                                    "如果包含多条结果，用空行分隔即可。"
                                                ))])
                                                _aggregated = (_fmt_resp.content or "").strip()
                                            except Exception:
                                                _aggregated = _raw_summary
                                            # 从原始结果中提取 db_id
                                            if any(_a.get("tool") in ("generate_resume_tool", "generate_interview_report_tool") for _a in _rewrite_actions):
                                                for _key, _val in _results.items():
                                                    if isinstance(_val, dict) and _val.get("ok") and isinstance(_val.get("extra"), dict) and _val["extra"].get("db_id"):
                                                        for _sub in _root.dag.nodes.values():
                                                            for _a in _sub.actions:
                                                                if _a.output_key == _key:
                                                                    if _a.tool == "generate_interview_report_tool":
                                                                        _guide_id_ir = _val["extra"]["db_id"]
                                                                    elif _a.tool == "generate_resume_tool":
                                                                        _resume_id_ir = _val["extra"]["db_id"]
                                                                    break
                                        else:
                                            _aggregated = f"校验不通过: {'; '.join(_errors)}"
                                    else:
                                        _aggregated = "无法拆解该任务"
                                else:
                                    _tool_name = _rewrite_actions[0]["tool"]
                                    _params = _rewrite_actions[0].get("params", {})
                                    _push_live_event({"type": "tool_call", "data": {"tool": _tool_name, "args": _params}})
                                    _raw = _gateway.call_sync_to_text(_tool_name, _params, {"user_id": uid})
                                    _aggregated = _raw or "执行完成"
                                    # 从单工具原始结果中提取 db_id
                                    _resume_id_ir = None
                                    _guide_id_ir = None
                                    try:
                                        _parsed_json = json.loads(_raw) if isinstance(_raw, str) else None
                                        if _parsed_json and isinstance(_parsed_json, dict) and _parsed_json.get("ok"):
                                            _db_id = _parsed_json.get("extra", {}).get("db_id") if isinstance(_parsed_json.get("extra"), dict) else None
                                            if _tool_name == "generate_interview_report_tool":
                                                _guide_id_ir = _db_id
                                            else:
                                                _resume_id_ir = _db_id
                                    except (json.JSONDecodeError, TypeError):
                                        pass
                                    _push_live_event({"type": "tool_result", "data": {"tool": _tool_name, "result_preview": "执行完成"}})

                                _reply = str(_aggregated)
                                # 若 _aggregated 是 JSON，提取可读文本
                                try:
                                    _parsed = json.loads(_reply)
                                    if isinstance(_parsed, dict):
                                        if _parsed.get("ok"):
                                            _data_str = _parsed.get("data", "")
                                            if isinstance(_data_str, str) and _data_str:
                                                _reply = _data_str
                                        elif _parsed.get("message"):
                                            _reply = _parsed["message"]
                                except (json.JSONDecodeError, TypeError):
                                    pass

                                save_message(sid, "assistant", _reply, user_id=uid, resume_id=_resume_id_ir, guide_id=_guide_id_ir)
                                update_task(tid, status="completed", response=_reply)
                                if _resume_id_ir is not None and _rewrite_actions:
                                    _first_tool = _rewrite_actions[0].get("tool", "")
                                    if _first_tool == "generate_interview_report_tool":
                                        _guide_id_ir = _resume_id_ir
                                        _resume_id_ir = None
                                _result_holder[0] = {
                                    "messages": list(history) + [AIMessage(content=_reply)],
                                    "resume_id": _resume_id_ir,
                                    "guide_id": _guide_id_ir,
                                }
                                return {"messages": list(history) + [AIMessage(content=_reply)]}

                    except Exception as _rewrite_err:
                        import traceback as _tb
                        _tb.print_exc()
                        print(f"[intent_rewrite] fallback: {_rewrite_err}")

                    # ── Task Decomposition Pipeline (original) ─────────────
                    try:
                        from services.task.action_parser import parse_actions
                        from services.task.engine import TaskDecompositionEngine
                        from services.task.validator import validate_dag
                        from services.task.scheduler import DAGScheduler, aggregate_results

                        # Prefer _rewrite_actions if intent rewrite already identified tools
                        # (they may have params already filled by LLM extraction)
                        _actions = _rewrite_actions or parse_actions(_last_user_text)
                        if len(_actions) >= 2:
                            _engine = TaskDecompositionEngine()
                            _root = _engine.decompose(_actions, _last_user_text)
                            if _root is not None:
                                _errors = validate_dag(_root)

                                # ── LLM param extraction fallback ────────────
                                if _errors:
                                    try:
                                        _missing = set()
                                        import re as _rp
                                        for _e in _errors:
                                            _m = _rp.search(r"'(\w+)'", _e)
                                            if _m:
                                                _missing.add(_m.group(1))
                                        if _missing:
                                            _parts = []
                                            for _m in history:
                                                _c = getattr(_m, "content", "") or ""
                                                if isinstance(_c, list):
                                                    _c = " ".join(str(b.get("text", "")) for b in _c if isinstance(b, dict) and b.get("type") == "text")
                                                _r = "用户" if getattr(_m, "type", "") == "human" else "助手"
                                                _parts.append(f"{_r}: {_c[:500]}")
                                            _hist = "\n".join(_parts)
                                            _ep = (
                                                "从以下对话历史中提取缺失的参数值，返回 JSON 对象。\n"
                                                f"需要提取的参数: {', '.join(_missing)}\n\n"
                                                "对话历史：\n"
                                                f"{_hist}\n\n"
                                                "最新用户输入：\n"
                                                f"{_last_user_text}\n\n"
                                                "只返回 JSON，不要多余文字。找不到的字段设为空字符串。\n"
                                                "示例：{\"company_name\": \"杭州某某科技有限公司\", \"job_title\": \"产品经理\"}"
                                            )
                                            _el = _get_intent_llm()
                                            _er = _el.invoke([HumanMessage(content=_ep)])
                                            _ec = (_er.content or "").strip()
                                            if _ec:
                                                _ej = json.loads(_ec)
                                                if isinstance(_ej, dict):
                                                    for _act in _actions:
                                                        _pa = _act.setdefault("params", {})
                                                        for _k, _v in _ej.items():
                                                            if _v and not _pa.get(_k):
                                                                _pa[_k] = str(_v).strip()
                                                    _root = _engine.decompose(_actions, _last_user_text)
                                                    if _root is not None:
                                                        _errors = validate_dag(_root)
                                    except Exception as _ee:
                                        print(f"[task_decomp] LLM extract error: {_ee}")

                                if not _errors:
                                    _scheduler = DAGScheduler(
                                        gateway=_gateway,
                                        live_event_pusher=_push_live_event,
                                        ctx={"user_id": uid},
                                    )
                                    _results = _scheduler.execute(_root)
                                    _aggregated = aggregate_results(_results)

                                    _fmt_prompt = (
                                        "以下是工具执行结果，请用自然语言回复用户，简洁明了：\n\n"
                                        f"{_aggregated}\n\n用户的问题：{_last_user_text}"
                                    )
                                    _llm = _get_admin_llm()
                                    _resp = _llm.invoke([HumanMessage(content=_fmt_prompt)])
                                    _reply = _resp.content.strip()

                                    save_message(sid, "assistant", _reply, user_id=uid)
                                    update_task(tid, status="completed", response=_reply)
                                    _result_holder[0] = {"messages": [AIMessage(content=_reply)]}
                                    return {"messages": [AIMessage(content=_reply)]}
                                else:
                                    # Natural language questions for missing params
                                    _missing_list = []
                                    import re as _rp2
                                    for _e in _errors:
                                        _m = _rp2.search(r"'(\w+)'", _e)
                                        if _m:
                                            _missing_list.append(_m.group(1))
                                    _nat = []
                                    for _pn in _missing_list:
                                        if _pn == "company_name":
                                            _nat.append("请问要给哪个公司添加面试记录？")
                                        elif _pn == "job_title":
                                            _nat.append("请问岗位名称是什么？")
                                        elif _pn == "company":
                                            _nat.append("请问要对哪个公司生成面试报告？")
                                        elif _pn in ("jd", "raw_content"):
                                            _nat.append("请提供职位描述（JD）")
                                        else:
                                            _nat.append(f"缺少必需参数「{_pn}」")
                                    _reply = "\n".join(_nat) if _nat else f"请提供以下缺失信息：{'; '.join(_errors)}"
                                    save_message(sid, "assistant", _reply, user_id=uid)
                                    update_task(tid, status="completed", response=_reply)
                                    _result_holder[0] = {"messages": [AIMessage(content=_reply)]}
                                    return {"messages": [AIMessage(content=_reply)]}
                    except Exception as _decomp_err:
                        import traceback as _tb2
                        _tb2.print_exc()
                        print(f"[task_decomp] fallback to LangGraph: {_decomp_err}")

                    result = agent_executor.invoke(
                        {"messages": history},
                        {"recursion_limit": 15},
                    )

                    # Check cancellation after invoke completes
                    if _is_task_cancelled(tid):
                        # Don't save partial tool results to conversation —
                        # raw ToolMessage JSON is internal format.
                        # Tool results already in agent_events for audit.
                        update_task(tid, status="cancelled", response="任务已取消")
                        _result_holder[0] = result
                        return result

                    # Extract reply and resume_id
                    reply = "处理完成"
                    resume_id = None
                    _tool_results = []
                    for m in result["messages"][history_input_count:]:
                        if isinstance(m, _AIMsg):
                            content = (m.content or "").strip()
                            if content:
                                reply = content
                        if hasattr(m, "type") and m.type == "tool":
                            if m.name in ("create_interview_record_tool", "generate_resume_tool", "generate_interview_report_tool"):
                                try:
                                    parsed = json.loads(m.content or "{}")
                                    if isinstance(parsed, dict):
                                        if parsed.get("ok"):
                                            if parsed.get("extra") and parsed["extra"].get("db_id"):
                                                resume_id = parsed["extra"]["db_id"]
                                            _tool_results.append(f"✅ {m.name}: {str(parsed.get('data', ''))[:200]}")
                                        else:
                                            _tool_results.append(f"❌ {m.name}: {parsed.get('error', '未知错误')}")
                                except (json.JSONDecodeError, ValueError):
                                    pass
                    # Fallback: if no AIMessage content, build reply from tool results
                    if reply == "处理完成" and _tool_results:
                        reply = "\n".join(_tool_results)
                    # Persist regardless of async generator alive status
                    save_message(sid, "assistant", reply, user_id=uid, resume_id=resume_id)
                    _record_usage(result, uid)
                    update_task(tid, status="completed", response=reply, resume_id=resume_id)
                    _result_holder[0] = result
                    return result
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    error = f"处理失败：{type(e).__name__}"
                    save_message(sid, "assistant", f"❌ {error}", user_id=uid)
                    update_task(tid, status="failed", response=error)
                    raise

            _seq = [0]

            def _save_ev(event: dict):
                try:
                    save_event(session_id, task_id, event["type"], event.get("data", {}), _seq[0], user_id=user_id)
                    _seq[0] += 1
                except Exception:
                    pass

            future = pool.submit(_worker, user_id, _live_queue_ref, _task_id_ref, _session_id_ref)

            try:
                # Poll live queue while agent executes (0.5s intervals)
                _heartbeat_ts = time.time()
                while True:
                    try:
                        result = await asyncio.wait_for(asyncio.wrap_future(future), timeout=0.5)
                        break
                    except asyncio.TimeoutError:
                        pass
                    if live_queue:
                        _heartbeat_ts = time.time()
                        while live_queue:
                            ev = live_queue.popleft()
                            _save_ev(ev)
                            yield ev
                            await _flush()
                    elif time.time() - _heartbeat_ts >= 5:
                        _heartbeat_ts = time.time()
                        yield {"type": "status", "data": {"message": "处理中..."}}
                print(f"[metrics] agent.stream_agent session={session_id} duration={timer.elapsed:.2f}s")
            except asyncio.TimeoutError:
                # This fires if wait_for itself times out (unusual with 0.5s poll)
                print(f"[agent_service] stream_agent timeout for session {session_id}")
                ev = {"type": "error", "data": {"message": "请求超时，请稍后重试"}}
                _save_ev(ev)
                yield ev
                _live_events_queue.reset(token_queue)
                _current_task_id.reset(token_task)
                _current_session_id.reset(token_session)
                return
            except Exception as e:
                import traceback
                traceback.print_exc()
                error_msg = f"处理失败：{type(e).__name__}"
                ev = {"type": "error", "data": {"message": error_msg}}
                _save_ev(ev)
                yield ev
                _live_events_queue.reset(token_queue)
                _current_task_id.reset(token_task)
                _current_session_id.reset(token_session)
                return

    # If worker already persisted result (common when async gen survived),
    # use it for remaining live events and SSE yields
    final_result = _result_holder[0] or result
    if final_result:
        # Drain any remaining live events
        while live_queue:
            ev = live_queue.popleft()
            _save_ev(ev)
            yield ev
            await _flush()

        _live_events_queue.reset(token_queue)
        _current_task_id.reset(token_task)
        _current_session_id.reset(token_session)

        from langchain_core.messages import AIMessage as _AIMessage

        # Extract reply
        reply = "处理完成"
        resume_id = final_result.get("resume_id") if isinstance(final_result, dict) else None
        _tool_replies = []
        for msg in final_result["messages"][history_input_count:]:
            if isinstance(msg, _AIMessage):
                content = (msg.content or "").strip()
                if content:
                    reply = content
            if hasattr(msg, "type") and msg.type == "tool":
                if msg.name in ("create_interview_record_tool", "generate_resume_tool", "generate_interview_report_tool"):
                    try:
                        parsed = json.loads(msg.content or "{}")
                        if isinstance(parsed, dict):
                            if parsed.get("ok"):
                                if parsed.get("extra") and parsed["extra"].get("db_id"):
                                    resume_id = parsed["extra"]["db_id"]
                                _tool_replies.append(f"✅ {msg.name}: {str(parsed.get('data', ''))[:200]}")
                            else:
                                _tool_replies.append(f"❌ {msg.name}: {parsed.get('error', '未知错误')}")
                    except (json.JSONDecodeError, ValueError):
                        pass
            if isinstance(msg, _AIMessage) and resume_id is None:
                try:
                    _p = json.loads(msg.content or "{}")
                    if isinstance(_p, dict) and _p.get("ok"):
                        _extra = _p.get("extra")
                        if isinstance(_extra, dict) and _extra.get("db_id"):
                            resume_id = _extra["db_id"]
                except (json.JSONDecodeError, TypeError):
                    pass
        if reply == "处理完成" and _tool_replies:
            reply = "\n".join(_tool_replies)

        # Yield remaining AI text and done events (not captured by live queue)
        _yielded_text = False
        for msg in final_result["messages"][history_input_count:]:
            if isinstance(msg, _AIMessage):
                tc = getattr(msg, "tool_calls", None) or []
                content = (msg.content or "").strip()
                if content and not tc:
                    _yielded_text = True
                    fsm.transit("finish")
                    fsev = fsm.to_event()
                    _save_ev(fsev)
                    yield fsev
                    await _flush()
                    from services.output_audit import mask_pii
                    safe_content = mask_pii(content)
                    event_data = {"content": safe_content}
                    _save_ev({"type": "text", "data": event_data})
                    yield {"type": "text", "data": event_data}
                    await _flush()
        # If no AIMessage content yielded but reply has tool results, yield them
        if not _yielded_text and reply != "处理完成":
            fsm.transit("finish")
            _save_ev(fsm.to_event())
            yield fsm.to_event()
            await _flush()
            from services.output_audit import mask_pii
            _safe_reply = mask_pii(reply)
            _ev_data = {"content": _safe_reply}
            _save_ev({"type": "text", "data": _ev_data})
            yield {"type": "text", "data": _ev_data}
            await _flush()

        guide_id = None
        if isinstance(final_result, dict):
            guide_id_from_result = final_result.get("guide_id")
            if guide_id_from_result is not None:
                guide_id = guide_id_from_result
                resume_id = None
        if guide_id is None:
            for msg in final_result["messages"][history_input_count:]:
                if hasattr(msg, "type") and msg.type == "tool" and msg.name == "generate_interview_report_tool":
                    try:
                        _p = json.loads(msg.content or "{}")
                        if _p.get("ok") and _p.get("extra") and _p["extra"].get("db_id"):
                            guide_id = _p["extra"]["db_id"]
                            resume_id = None
                    except (json.JSONDecodeError, TypeError):
                        pass
                if isinstance(msg, _AIMessage) and guide_id is None:
                    try:
                        _p = json.loads(msg.content or "{}")
                        if isinstance(_p, dict) and _p.get("ok") and _p.get("extra"):
                            _extra = _p.get("extra", {})
                            if isinstance(_extra, dict) and _extra.get("db_id"):
                                guide_id = _extra["db_id"]
                                reply_lower = (reply or "").lower()
                                if "面试报告" in reply_lower or "报告" in reply_lower:
                                    resume_id = None
                    except (json.JSONDecodeError, TypeError):
                        pass

        done_event_data = {"response": reply, "resume_id": resume_id, "guide_id": guide_id}
        _save_ev({"type": "done", "data": done_event_data})
        yield {"type": "done", "data": done_event_data}
        await _flush()

