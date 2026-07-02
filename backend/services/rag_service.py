import os
import json
import asyncio
import time
import re
import httpx
from langchain_community.document_loaders import TextLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_core.messages import SystemMessage, HumanMessage
from langchain.tools import tool
from config import settings
from services.prompt_injection import check_message
from services.metrics import Timer
from services.prompt_manager import prompt_manager
from services.usage_service import usage_service

_KB_INTENT_SEARCH_HINT = {
    "personal_info": "已识别你在询问个人信息（姓名、年龄、所在地等）",
    "education": "已识别你在询问教育背景",
    "work_experience": "已识别你在询问工作经历",
    "project_experience": "已识别你在询问项目经历",
    "skills": "已识别你在询问技能栈",
}
_INTENT_NAMES = {
    "greeting": "打招呼", "personal_info": "个人信息", "education": "教育背景",
    "work_experience": "工作经历", "project_experience": "项目经历", "skills": "技能栈",
    "faq": "标准问答", "salary": "薪资待遇", "company_match": "公司匹配",
    "schedule_interview": "面试安排", "other": "其他",
}

def _build_visitor_system_prompt(kb_intent: str | None = None, user_id: str = "") -> str:
    """Build visitor system prompt with candidate name and schedule info.

    If kb_intent is provided, appends a hint about which search_candidate_info category to prefer.
    """
    from config import get_candidate_name, settings
    candidate_name = get_candidate_name(user_id)
    # Get available schedule from DB
    schedule_info = "工作日09:00-18:00"
    try:
        from services.database import SessionLocal
        from services.models import ApplicantProfile
        db = SessionLocal()
        query = db.query(ApplicantProfile)
        if user_id:
            query = query.filter(ApplicantProfile.user_id == user_id)
        else:
            query = query.filter(ApplicantProfile.id == 1)
        profile = query.first()
        if profile and profile.workday_start and profile.workday_end:
            schedule_info = f"工作日{profile.workday_start}-{profile.workday_end}"
        db.close()
    except Exception:
        pass

    # 从 PromptManager 读取（DB 持久化，支持版本管理）
    template = prompt_manager.get("visitor_system_prompt")
    if template:
        try:
            prompt = template.format(candidate_name=candidate_name, schedule_info=schedule_info)
        except (KeyError, ValueError) as e:
            print(f"[rag_service] prompt template format failed: {e}")
            prompt = ""
    else:
        prompt = ""

    if not prompt:
        prompt = f'你是{candidate_name}，正在和HR对话。用第一人称\u201c我\u201d自然交流。可用面试时间段：{schedule_info}'

    # 追加意图定向搜索提示
    if kb_intent:
        _intent_name = _INTENT_NAMES.get(kb_intent, kb_intent)
        hint = _KB_INTENT_SEARCH_HINT.get(kb_intent)
        if hint:
            prompt += f'\n\n## 当前对话方向\n{hint}。如果该类别未搜到足够信息，可以换其他类别重试。'
        elif kb_intent != "greeting":
            prompt += f'\n\n## 当前对话方向\n已识别当前对话方向为：{_intent_name}。如需补充信息，可以直接回答或询问更具体的问题。'

    return prompt





def _looks_like_tool_call_text(content: str) -> bool:
    """Detect when model outputs tool call as text instead of structured field."""
    if not content:
        return False
    c = content.strip()
    if c.startswith(("search_candidate_info", "search_knowledge_base", "suggest_available_slots", "look_aside")):
        return True
    if "<longcat_arg_key>" in c or "<longcat_arg_value>" in c:
        return True
    return False


class RAGService:
    def __init__(self, llm=None, visitor_llm=None, embeddings=None):
        self.embeddings = embeddings
        self.vector_store = None
        self.llm = llm
        self.visitor_llm = visitor_llm
        self.visitor_qa_chain = None
        self.visitor_tools = None
        self.visitor_llm_with_tools = None
        self._retrieval_cache: dict[str, str] = {}
        self._faq_cache: dict[str, str] = {}
        self._vector_stores: dict[str, FAISS] = {}
        self._visitor_llm_ready = visitor_llm is not None
        self._init_embeddings()

    def _ensure_visitor_llm(self):
        if not self._visitor_llm_ready:
            self.visitor_llm = self._create_visitor_llm()
            self._visitor_llm_ready = True
        return self.visitor_llm

    async def _detect_company_intent(self, query: str) -> tuple[bool, str]:
        """用 LLM 判断 HR 是否在询问/提及某个具体公司，并提取公司名。
        返回 (has_company, company_name)。"""
        if not self.visitor_llm:
            return False, ""
        classify_prompt = prompt_manager.get("company_detection_prompt", "").format(query=query)
        if not classify_prompt:
            return False, ""
        try:
            resp = await self.visitor_llm.ainvoke([HumanMessage(content=classify_prompt)])
            text = resp.content.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[-1]
                text = text.rsplit("```", 1)[0]
            text = text.strip()
            data = json.loads(text)
            has = data.get("has_company", False)
            company = data.get("company", "")
            return bool(has), company
        except Exception as e:
            print(f"[rag_service] intent detection error: {e}")
            return False, ""

    async def _search_company_info(self, company_name: str, user_id: str = "") -> str:
        """对公司名进行在线搜索，返回格式化结果摘要。"""
        api_key = getattr(settings, "TAVILY_API_KEY", "")
        if not api_key:
            return ""
        _search_query = f"{company_name} 是做什么的"
        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    lambda: httpx.post(
                        "https://api.tavily.com/search",
                        headers={
                            "Authorization": f"Bearer {api_key}",
                            "Content-Type": "application/json",
                        },
                        json={
                            "query": _search_query,
                            "search_depth": "basic",
                            "topic": "general",
                            "max_results": 5,
                            "include_answer": True,
                        },
                        timeout=15,
                    )
                ),
                timeout=20,
            )
            if resp.status_code != 200:
                print(f"[rag_service] company_search HTTP {resp.status_code} for '{company_name}'")
                return ""
            data = resp.json()
            results = data.get("results", [])
            answer = data.get("answer", "")
            if not results:
                return ""
            lines = []
            if answer:
                lines.append(f"【AI摘要】{answer}")
            for i, r in enumerate(results[:3], 1):
                title = r.get("title", "")
                snippet = r.get("content", "")[:300]
                lines.append(f"{i}. {title}\n   {snippet}")
            print(f"[rag_service] company_search OK for '{company_name}': {len(results)} results")
            usage_service.record(user_id=user_id or "visitor", event_type="search_api",
                                 model="tavily", search_calls=1)
            return "\n\n".join(lines)
        except Exception as e:
            print(f"[rag_service] company_search error for '{company_name}': {e}")
            return ""

    def _get_raw_work_experience(self, user_id: str = "") -> str:
        docs = self.load_single_category("work_experience", user_id=user_id or None)
        if not docs:
            return ""
        parts = []
        for d in docs:
            content = d.page_content.strip()
            if len(content) < 30:
                continue
            parts.append(content)
        return "\n\n---\n\n".join(parts)

    def clear_cache(self):
        """Clear retrieval caches (call after KB update)."""
        self._retrieval_cache.clear()
        self._faq_cache.clear()
        self._vector_stores.clear()

    def _get_vector_store(self, user_id: str = ""):
        """Get vector store for a user, falling back to self.vector_store.
        
        Uses per-user cache to avoid singleton race conditions between concurrent requests.
        """
        if user_id:
            vs = self._vector_stores.get(user_id)
            if vs is not None:
                return vs
            vs_dir = self._get_vector_store_dir(user_id)
            try:
                vs = FAISS.load_local(vs_dir, self.embeddings, allow_dangerous_deserialization=True)
                self._vector_stores[user_id] = vs
                return vs
            except Exception:
                return None
        return self.vector_store

    def _retrieve_context(self, question: str, k: int = 12, category: str | None = None, user_id: str = "") -> str:
        cache_key = f"ctx:{user_id}:{question}:{k}:{category}"
        cached = self._retrieval_cache.get(cache_key)
        if cached is not None:
            return cached
        vs = self._get_vector_store(user_id)
        if not vs:
            return ""
        try:
            if category:
                docs = vs.similarity_search(question, k=999)
                cat_docs = [d for d in docs if d.metadata.get("category") == category]
                if not cat_docs:
                    self._retrieval_cache[cache_key] = ""
                    return ""
                # company_name 类型的 anchor chunk 放最前面，确保 LLM 首先看到公司名
                anchors = [d.page_content[:1000] for d in cat_docs if d.metadata.get("type") == "company_name" and len(d.page_content.strip()) >= 30]
                others = [d.page_content[:1000] for d in cat_docs if d.metadata.get("type") != "company_name" and len(d.page_content.strip()) >= 30]
                merged = anchors + others
                result = "\n\n---\n\n".join(merged[:k])
                self._retrieval_cache[cache_key] = result
                return result

            docs = vs.similarity_search(question, k=k)
            if not docs:
                self._retrieval_cache[cache_key] = ""
                return ""
            filtered = []
            for d in docs:
                content = d.page_content.strip()
                if len(content) < 30:
                    continue
                filtered.append(d.page_content[:1000])
            if not filtered:
                filtered = [d.page_content[:1000] for d in docs[:5]]
            result = "\n\n---\n\n".join(filtered[:12])
            self._retrieval_cache[cache_key] = result
            return result
        except Exception:
            return ""

    def _match_single_faq(self, question: str, faq_list: list) -> str:
        """Match a single question against FAQ list. Returns matched result or ''."""
        q_normalized = question.strip().rstrip("？?")
        if not q_normalized:
            return ""
        _q_clean = q_normalized
        for _suffix in ["是什么", "是什么的", "是做什么", "是干什么", "是啥", "有哪些",
                        "怎么样", "怎么", "什么", "哪个", "哪些", "吗", "呢", "吧", "啊"]:
            if _q_clean.endswith(_suffix):
                _q_clean = _q_clean[:-len(_suffix)]
                break
        q_keywords = set()
        if len(_q_clean) >= 2:
            q_keywords.add(_q_clean)
            for k_start in range(len(_q_clean) - 1):
                for k_end in range(k_start + 2, min(k_start + 6, len(_q_clean) + 1)):
                    w = _q_clean[k_start:k_end]
                    if len(w) >= 2:
                        q_keywords.add(w)

        best_match = None
        best_score = 0
        best_kw_count = -1
        for item in faq_list:
            faq_q = item.get("question", "").strip().rstrip("？?")
            if not faq_q:
                continue
            faq_a = item.get("answer", "").strip()
            if faq_q in q_normalized:
                return f"问题：{faq_q} 回答：{faq_a}"[:1000]
            kw_matches = sum(1 for kw in q_keywords if kw in faq_q)
            shared = len(set(q_normalized) & set(faq_q))
            score = shared / max(len(q_normalized), len(faq_q), 1)
            if kw_matches > best_kw_count or (kw_matches == best_kw_count and score > best_score):
                best_kw_count = kw_matches
                best_score = score
                best_match = (faq_q, faq_a)
        if best_match and best_score >= 0.25:
            return f"问题：{best_match[0]} 回答：{best_match[1]}"[:1000]
        return ""

    def _retrieve_faq_context(self, question: str, intent: str = "", user_id: str = "") -> str:
        """从 knowledge_base.faq 表中检索匹配的 FAQ 条目。

        改进点：
        1. 匹配阈值降至 0.25（之前 0.35 太严，长问题匹配不上）
        2. 复合问题按标点拆分后再逐个匹配
        3. 已知 intent=salary 时兜底匹配薪资相关 FAQ
        """
        cache_key = f"faq:{user_id}:{question}"
        cached = self._faq_cache.get(cache_key)
        if cached is not None:
            return cached
        try:
            from services.database import SessionLocal
            from services.models import KnowledgeBase
            import json
            db = SessionLocal()
            try:
                query = db.query(KnowledgeBase).filter(KnowledgeBase.category == "faq")
                if user_id:
                    query = query.filter(KnowledgeBase.user_id == user_id)
                faq_kb = query.first()
                if not faq_kb or not faq_kb.data:
                    return ""
                faq_list = json.loads(faq_kb.data).get("faq_list", [])
                if not faq_list:
                    return ""
            finally:
                db.close()

            # 1) 整体匹配
            result = self._match_single_faq(question, faq_list)
            if result:
                self._faq_cache[cache_key] = result
                return result

            # 2) 复合问题分拆：按 。？！; 分割后逐个匹配
            import re as _re
            sub_questions = [sq.strip() for sq in _re.split(r'[；;。！？\n]', question) if len(sq.strip()) >= 2]
            if len(sub_questions) > 1:
                seen_answers = set()
                parts = []
                for sq in sub_questions:
                    sq_result = self._match_single_faq(sq.strip().rstrip("？?"), faq_list)
                    if sq_result and sq_result not in seen_answers:
                        seen_answers.add(sq_result)
                        parts.append(sq_result)
                if parts:
                    combined = "\n\n".join(parts)[:2000]
                    self._faq_cache[cache_key] = combined
                    return combined

            # 3) intent 兜底：比如 salary 类问题没匹配到，手动查薪资相关 FAQ
            if intent == "salary" or "薪" in question:
                salary_keywords = ["期望薪资", "薪资", "薪酬", "工资", "待遇", "薪"]
                for item in faq_list:
                    faq_q = item.get("question", "").strip()
                    faq_a = item.get("answer", "").strip()
                    if any(kw in faq_q for kw in salary_keywords):
                        result = f"问题：{faq_q} 回答：{faq_a}"[:1000]
                        self._faq_cache[cache_key] = result
                        return result

            self._faq_cache[cache_key] = ""
            return ""
        except Exception:
            return ""

    def _create_visitor_llm(self) -> ChatOpenAI:
        """Create visitor LLM from DB → env fallback."""
        from config import get_visitor_llm_config
        _vcfg = get_visitor_llm_config()
        if not _vcfg["api_key"]:
            raise ValueError(
                "VISITOR_API_KEY is not configured. "
                "Go to admin panel → System Config → Visitor LLM to set it."
            )
        print(f"[rag_service] visitor LLM using {_vcfg['model']}")
        return ChatOpenAI(
            api_key=_vcfg["api_key"],
            base_url=_vcfg["api_base"],
            model=_vcfg["model"],
            temperature=0.1,
            max_tokens=1024,
            streaming=True,
            timeout=120,
            max_retries=0,
        )

    def _init_visitor_llm(self):
        self.visitor_llm = self._create_visitor_llm()

    def _invoke_visitor_llm_with_retry(self, messages, user_id: str = ""):
        model_name = getattr(self.visitor_llm, 'model_name', '') or getattr(self.visitor_llm, 'model', '')
        llm = self.visitor_llm if 'deepseek' in model_name.lower() else self.visitor_llm_with_tools
        response = llm.invoke(messages)
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage_service.record(
                user_id=user_id or "visitor",
                event_type="visitor_llm",
                model=model_name,
                input_tokens=response.usage_metadata.get("input_tokens", 0),
                output_tokens=response.usage_metadata.get("output_tokens", 0),
            )
        return response

    def _init_embeddings(self):
        self.embeddings = OpenAIEmbeddings(
            api_key=settings.SILICONFLOW_API_KEY,
            base_url=settings.SILICONFLOW_API_BASE,
            model=settings.SILICONFLOW_EMBEDDING_MODEL,
            chunk_size=32
        )

    CATEGORY_FILE_MAP = {
        "personal_info": "01_个人信息",
        "education": "02_教育背景",
        "work_experience": "03_工作经历",
        "projects": "04_项目经历",
        "skills": "05_专业技能栈",
        "faq": "06_HR高频问答库",
    }

    def _split_docs(self, docs):
        result = []
        from langchain_core.documents import Document
        for doc in docs:
            cat = doc.metadata.get("category", "")
            content = doc.page_content
            if "HR高频问答库" in cat or "06_HR" in cat:
                if content.startswith("##"):
                    content = "\n".join(content.split("\n")[1:]).strip()
                pairs = content.split("**Q:")
                for p in pairs:
                    p = p.strip()
                    if not p:
                        continue
                    q_text = p.split("\n")[0].strip().rstrip("？?*# ").strip()
                    a_start = p.find("\nA:")
                    if a_start > 0:
                        answer = p[a_start+3:].strip().rstrip("？?*# ")
                        p = f"问题：{q_text} 回答：{answer}"
                    result.append(Document(page_content=p, metadata=dict(doc.metadata)))
            elif "工作经历" in cat:
                parts = content.split("\n### ")
                for i, part in enumerate(parts):
                    part = part.strip()
                    if not part:
                        continue
                    if i > 0:
                        part = f"### {part}"
                    result.append(Document(page_content=part, metadata=dict(doc.metadata)))
                    # 对工作经历 chunk 额外提取首行（公司名+时间）作为一个独立小chunk，
                    # 使「在哪些公司工作过」类查询能直接命中公司名
                    if i > 0:
                        lines = part.split("\n")
                        # 取前3行（公司名+职位+核心职责）作为搜索锚点，
                        # 太短的 chunk（仅公司名）LLM 会当成无意义标题跳过
                        anchor_text = "\n".join(lines[:min(3, len(lines))]).strip()
                        if len(anchor_text) > 15:
                            result.append(Document(
                                page_content=anchor_text,
                                metadata={**doc.metadata, "type": "company_name"}
                            ))
            elif "项目经历" in cat:
                parts = content.split("\n### ")
                for i, part in enumerate(parts):
                    part = part.strip()
                    if not part:
                        continue
                    if i > 0:
                        part = f"### {part}"
                    result.append(Document(page_content=part, metadata=dict(doc.metadata)))
            else:
                result.append(doc)
        # Split by paragraph for files still over chunk_size
        if result:
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=30)
            return text_splitter.split_documents(result)
        return result

    def _get_knowledge_dir(self, user_id):
        return os.path.join(settings.USER_DATA_DIR, str(user_id), "knowledge")

    def _ensure_knowledge_dir(self, user_id):
        kb_dir = self._get_knowledge_dir(user_id)
        os.makedirs(kb_dir, exist_ok=True)
        return kb_dir

    def _get_vector_store_dir(self, user_id):
        return os.path.join(settings.USER_DATA_DIR, str(user_id), "vector_store")

    def _ensure_vector_store_dir(self, user_id):
        vs_dir = self._get_vector_store_dir(user_id)
        os.makedirs(vs_dir, exist_ok=True)
        return vs_dir

    def load_knowledge(self, user_id=None):
        kb_dir = self._ensure_knowledge_dir(user_id)
        md_files = []
        for f in os.listdir(kb_dir):
            if f.endswith('.md') and "07_高频问题统计" not in f:
                md_files.append(os.path.join(kb_dir, f))
        
        documents = []
        for filepath in md_files:
            try:
                loader = TextLoader(filepath, encoding='utf-8')
                docs = loader.load()
                basename = os.path.basename(filepath).replace('.md', '')
                for doc in docs:
                    doc.metadata["source_type"] = "main"
                    doc.metadata["category"] = basename
                documents.extend(docs)
            except Exception as e:
                print(f"Error loading {filepath}: {e}")
        
        return self._split_docs(documents)

    def load_single_category(self, category: str, user_id=None):
        kb_dir = self._ensure_knowledge_dir(user_id)
        filename = self.CATEGORY_FILE_MAP.get(category, category)
        filepath = os.path.join(kb_dir, f"{filename}.md")
        if not os.path.exists(filepath):
            return []
        try:
            loader = TextLoader(filepath, encoding='utf-8')
            docs = loader.load()
            for doc in docs:
                doc.metadata["source_type"] = "main"
                doc.metadata["category"] = filename
            return self._split_docs(docs)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return []

    def load_appendix_knowledge(self, dir_path: str):
        """Recursively load all .md files from a directory as appendix docs."""
        if not os.path.isdir(dir_path):
            return []
        
        documents = []
        for root, dirs, files in os.walk(dir_path):
            for f in files:
                if f.endswith('.md'):
                    filepath = os.path.join(root, f)
                    try:
                        loader = TextLoader(filepath, encoding='utf-8')
                        docs = loader.load()
                        for doc in docs:
                            doc.metadata["source_type"] = "appendix"
                            doc.metadata["source_dir"] = os.path.basename(dir_path)
                            doc.metadata["original_path"] = os.path.relpath(filepath, dir_path)
                        documents.extend(docs)
                    except Exception as e:
                        print(f"Error loading appendix {filepath}: {e}")
        
        if not documents:
            return []
        
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=200,
            chunk_overlap=30,
            length_function=len
        )
        return text_splitter.split_documents(documents)

    def _build_user_vector_store(self, user_id: str):
        from services.ai_service import _sync_db_to_md
        _sync_db_to_md(user_id)
        documents = self.load_knowledge(user_id)
        if documents:
            self.build_vector_store(documents, user_id)

    def build_vector_store(self, documents, user_id=None):
        if not documents:
            return
        vs_dir = self._ensure_vector_store_dir(user_id)
        self.vector_store = FAISS.from_documents(documents, self.embeddings)
        self.vector_store.save_local(vs_dir)
        if user_id:
            self._vector_stores[user_id] = self.vector_store

    def build_main_with_mapping(self, db, user_id=None):
        kb_dir = self._ensure_knowledge_dir(user_id)
        documents = self.load_knowledge(user_id)
        if not documents:
            return
        vs_dir = self._ensure_vector_store_dir(user_id)
        self.vector_store = FAISS.from_documents(documents, self.embeddings)
        self.vector_store.save_local(vs_dir)
        if user_id:
            self._vector_stores[user_id] = self.vector_store
        all_ids = list(self.vector_store.index_to_docstore_id.values())
        cat_map = {}
        for i, doc in enumerate(documents):
            cat = doc.metadata.get("category", "unknown")
            if i < len(all_ids):
                cat_map.setdefault(cat, []).append(all_ids[i])
        # Persist mapping — scoped to user_id when provided
        from services.models import KnowledgeBase
        import json
        q = db.query(KnowledgeBase).filter(KnowledgeBase.category == "main_kb_ids")
        if user_id:
            q = q.filter(KnowledgeBase.user_id == str(user_id))
        else:
            q = q.filter(KnowledgeBase.user_id.is_(None))
        kb = q.first()
        if not kb:
            kb = KnowledgeBase(category="main_kb_ids", data=json.dumps(cat_map), user_id=str(user_id) if user_id else None)
            db.add(kb)
        else:
            kb.data = json.dumps(cat_map)
        db.commit()
        return cat_map

    def update_category(self, category: str, db, user_id=None):
        from services.models import KnowledgeBase
        import json
        kb_entry = db.query(KnowledgeBase).filter(
            KnowledgeBase.category == "main_kb_ids",
            KnowledgeBase.user_id == str(user_id) if user_id else KnowledgeBase.user_id.is_(None),
        ).first()
        cat_map = json.loads(kb_entry.data) if kb_entry else {}
        filename = self.CATEGORY_FILE_MAP.get(category, category)
        old_ids = cat_map.pop(filename, [])
        vs_dir = self._get_vector_store_dir(user_id)
        try:
            vs = FAISS.load_local(vs_dir, self.embeddings, allow_dangerous_deserialization=True)
        except Exception:
            vs = None
        if old_ids and vs is not None:
            vs.delete(old_ids)
        new_docs = self.load_single_category(category, user_id)
        if new_docs:
            if vs is None:
                vs = FAISS.from_documents(new_docs, self.embeddings)
            else:
                vs.add_documents(new_docs)
            new_ids = [vs.index_to_docstore_id[i] for i in range(len(new_docs))]
            cat_map[filename] = new_ids
            vs.save_local(vs_dir)
            self._vector_stores[user_id] = vs
        # Update KB mapping
        kb_entry2 = db.query(KnowledgeBase).filter(
            KnowledgeBase.category == "main_kb_ids",
            KnowledgeBase.user_id == str(user_id) if user_id else KnowledgeBase.user_id.is_(None),
        ).first()
        if not kb_entry2:
            kb_entry2 = KnowledgeBase(category="main_kb_ids", data=json.dumps(cat_map), user_id=str(user_id) if user_id else None)
            db.add(kb_entry2)
        else:
            kb_entry2.data = json.dumps(cat_map)
        db.commit()

    def add_appendix_to_store(self, appendix_docs, user_id=None):
        if not appendix_docs:
            return []
        vs_dir = self._get_vector_store_dir(user_id)
        os.makedirs(vs_dir, exist_ok=True)
        try:
            self.vector_store = FAISS.load_local(vs_dir, self.embeddings, allow_dangerous_deserialization=True)
            doc_ids = self.vector_store.add_documents(appendix_docs)
        except Exception:
            self.vector_store = FAISS.from_documents(appendix_docs, self.embeddings)
            doc_ids = list(self.vector_store.index_to_docstore_id.values())[-len(appendix_docs):]
        self.vector_store.save_local(vs_dir)
        if user_id:
            self._vector_stores[user_id] = self.vector_store
        return doc_ids

    def remove_by_ids(self, doc_ids: list, user_id=None):
        if not doc_ids:
            return
        vs_dir = self._get_vector_store_dir(user_id)
        try:
            vs = FAISS.load_local(vs_dir, self.embeddings, allow_dangerous_deserialization=True)
            vs.delete(doc_ids)
            vs.save_local(vs_dir)
            if user_id:
                self._vector_stores[user_id] = vs
        except Exception:
            pass

    def get_appendix_info(self, user_id=None):
        vs_dir = self._get_vector_store_dir(user_id)
        try:
            vs = FAISS.load_local(vs_dir, self.embeddings, allow_dangerous_deserialization=True)
            return {"count": vs.index.ntotal}
        except Exception:
            return {"count": 0}

    def load_vector_store(self, user_id=None):
        vs_dir = self._get_vector_store_dir(user_id)
        try:
            self.vector_store = FAISS.load_local(
                vs_dir,
                self.embeddings,
                allow_dangerous_deserialization=True
            )
            if user_id:
                self._vector_stores[user_id] = self.vector_store
            return True
        except Exception:
            return False

    def retrieve_relevant(self, query: str, k: int = 10, user_id=None):
        vs_dir = self._get_vector_store_dir(user_id)
        try:
            vs = FAISS.load_local(
                vs_dir,
                self.embeddings,
                allow_dangerous_deserialization=True
            )
        except Exception:
            return []
        results = vs.similarity_search_with_score(query, k=50)
        docs = [r[0] for r in results]
        scores = [r[1] for r in results]
        reranked = self._keyword_rerank(query, docs, scores, k=k)
        score_map = {d.page_content[:200]: s for d, s in zip(docs, scores)}
        out = []
        for d in reranked:
            key = d.page_content[:200]
            s = 1.0 / (1.0 + score_map.get(key, 1.0))
            out.append((d, s))
        return out

    def _keyword_rerank(self, query: str, docs, vec_scores, k=8):
        query_lower = query.lower()
        import re
        # Extract meaningful terms (English words, Chinese bigrams)
        query_terms = set(re.findall(r'[a-zA-Z]+|[\u4e00-\u9fff]{2,}', query_lower))
        # Also extract individual English letters for cases like "github"
        query_chars = set(re.findall(r'[a-z]+', query_lower))
        scored = []
        for doc, vec_score in zip(docs, vec_scores):
            content = doc.page_content.lower()
            # Term overlap score
            term_matches = sum(1 for t in query_terms if t in content)
            term_score = term_matches / max(len(query_terms), 1) if query_terms else 0
            # English word direct match bonus
            eng_bonus = 0
            for w in query_chars:
                if len(w) >= 3 and w in content:
                    eng_bonus += 0.3
            eng_bonus = min(eng_bonus, 0.9)
            final = (1.0 / (1.0 + vec_score)) * 0.4 + term_score * 0.3 + eng_bonus * 0.3
            scored.append((final, doc))
        scored.sort(key=lambda x: -x[0])
        return [d for _, d in scored[:k]]

    def init_qa_chain(self, user_id=None):
        self._ensure_visitor_llm()
        if user_id and str(user_id).strip():
            vs_dir = self._get_vector_store_dir(user_id)
            try:
                self.vector_store = FAISS.load_local(
                    vs_dir, self.embeddings,
                    allow_dangerous_deserialization=True
                )
                print(f"[rag_service] init_qa_chain loaded vector_store for user={user_id[:20]} size={self.vector_store.index.ntotal}")
            except Exception:
                self._ensure_vector_store_dir(user_id)
                self._build_user_vector_store(user_id)
                try:
                    self.vector_store = FAISS.load_local(
                        vs_dir, self.embeddings,
                        allow_dangerous_deserialization=True
                    )
                except Exception:
                    self.vector_store = None
            if self.vector_store:
                self._vector_stores[user_id] = self.vector_store
            else:
                return False
        
        # --- Visitor ReAct Agent ---
        @tool
        def search_candidate_info(query: str, category: str = "auto") -> str:
            """placeholder"""
            _uid = user_id
            vs = self._get_vector_store(_uid)
            if not vs:
                return json.dumps({"ok": False, "error": "知识库未加载"})
            try:
                filter_dict = None
                if category == "appendix":
                    filter_dict = {"source_type": "appendix"}
                elif category != "auto":
                    filename = self.CATEGORY_FILE_MAP.get(category, category)
                    filter_dict = {"category": filename}
                docs = vs.similarity_search(query, k=8, filter=filter_dict)
                if not docs:
                    return json.dumps({"ok": False, "error": "未找到相关信息", "source": category})
                result = "\n\n---\n\n".join([d.page_content[:800] for d in docs])
                return json.dumps({"ok": True, "data": result, "source": category})
            except Exception as e:
                return json.dumps({"ok": False, "error": str(e), "source": category})

        @tool
        def suggest_available_slots() -> str:
            """placeholder2"""
            try:
                from services.database import SessionLocal
                from services.models import InterviewGuide, ApplicantProfile
                from datetime import datetime, date, timedelta
                db = SessionLocal()
                q = db.query(ApplicantProfile)
                if user_id:
                    q = q.filter(ApplicantProfile.user_id == user_id)
                else:
                    q = q.filter(ApplicantProfile.id == 1)
                profile = q.first()
                workday_start = profile.workday_start if profile and profile.workday_start else "09:00"
                workday_end = profile.workday_end if profile and profile.workday_end else "18:00"
                duration = profile.interview_duration_min if profile else 60
                gap = profile.min_gap_min if profile else 120
                max_daily = profile.max_daily_interviews if profile else 3
                # Count today's scheduled interviews
                today_start = datetime.combine(date.today(), datetime.min.time())
                today_end = today_start + timedelta(days=1)
                today_count = db.query(InterviewGuide).filter(
                    InterviewGuide.interview_time >= today_start,
                    InterviewGuide.interview_time < today_end,
                    InterviewGuide.status.in_(["pending", "confirmed"]),
                ).count()
                db.close()
                remaining = max(0, max_daily - today_count)
                if remaining == 0:
                    result = f"今天的工作时间（{workday_start}-{workday_end}）内面试已约满，建议与候选人沟通其他日期。"
                else:
                    result = f"我一般的工作日{workday_start}-{workday_end}可以安排面试（每场约{duration}分钟，间隔{gap}分钟）。今天最多还能安排{remaining}场。周末也可以协调。"
                return json.dumps({"ok": True, "data": result})
            except Exception:
                return json.dumps({"ok": True, "data": "我一般的工作日09:00-18:00可以安排面试，周末也可以协调。如有具体日期偏好可以进一步沟通确认。"})
        
        # 从 PromptManager 动态加载工具描述（支持版本管理）
        _si_desc = prompt_manager.get("tool_search_candidate_info")
        if _si_desc:
            search_candidate_info.__doc__ = _si_desc
        _slot_desc = prompt_manager.get("tool_suggest_available_slots")
        if _slot_desc:
            suggest_available_slots.__doc__ = _slot_desc

        self.visitor_tools = [search_candidate_info, suggest_available_slots]
        self.visitor_llm_with_tools = self.visitor_llm.bind_tools(self.visitor_tools)
        
        self.visitor_qa_chain = True  # signal that visitor chain is ready
        return True

    async def answer_stream(self, question, conversation_history: str = "", use_visitor_llm: bool = False, user_id: str = ""):
        self._ensure_visitor_llm()
        if user_id:
            self.init_qa_chain(user_id)
        is_safe, reason = check_message(question)
        if not is_safe:
            print(f"[rag_service] injection blocked: {reason}")
            yield f"消息被拦截：{reason}"
            return

        if use_visitor_llm:
            if not self.visitor_qa_chain:
                yield "知识库尚未加载，请联系管理员"
                return
            timer = Timer("visitor.answer_stream")
            timer.start()
            _t0 = time.monotonic()
            try:
                if len(conversation_history) > 8000:
                    conversation_history = conversation_history[-8000:]
                expanded = self._expand_short_question(question)
                history_text = f"【对话历史】\n{conversation_history}\n\n" if conversation_history else ""

                # KB 意图分类 → 定向检索，替换一把梭的向量搜索
                from services.intent_detector import classify_kb_intent, CATEGORY_KB_FILE_MAP
                kb_intent = await classify_kb_intent(expanded)
                _t1 = time.monotonic()
                print(f"[metrics] visitor.classify_kb_intent duration={_t1-_t0:.3f}s")
                print(f"[rag_service] kb_intent={kb_intent} query='{expanded}'")

                faq_context = ""
                general_context = ""
                _company_search_result = ""

                if kb_intent == "greeting":
                    system_parts = [_build_visitor_system_prompt(kb_intent, user_id)]
                    system_prompt = "\n\n".join(system_parts)
                    user_message = f"{history_text}用户：{expanded}"
                    messages = [SystemMessage(content=system_prompt), HumanMessage(content=user_message)]
                    model_name = getattr(self.visitor_llm, 'model_name', '') or getattr(self.visitor_llm, 'model', '')
                    is_deepseek = 'deepseek' in model_name.lower()
                    if is_deepseek:
                        async for chunk in self.visitor_llm.astream(messages):
                            if chunk and chunk.content:
                                yield chunk.content
                        # Record usage for deepseek streaming output
                        try:
                            response = self.visitor_llm.invoke(messages)
                            if hasattr(response, "usage_metadata") and response.usage_metadata:
                                usage_service.record(
                                    user_id=user_id or "visitor",
                                    event_type="visitor_llm",
                                    model=model_name,
                                    input_tokens=response.usage_metadata.get("input_tokens", 0),
                                    output_tokens=response.usage_metadata.get("output_tokens", 0),
                                )
                        except Exception:
                            pass
                    else:
                        _t_greet0 = time.monotonic()
                        response = self._invoke_visitor_llm_with_retry(messages, user_id=user_id)
                        _t_greet1 = time.monotonic()
                        print(f"[metrics] visitor.greeting_llm_invoke duration={_t_greet1-_t_greet0:.3f}s")
                        content = response.content if hasattr(response, 'content') else ""
                        if content:
                            for i in range(0, len(content), 3):
                                yield content[i:i+3]
                    print(f"[metrics] visitor.answer_stream_total duration={timer.elapsed:.2f}s")
                    return

                # 定向检索
                if kb_intent in CATEGORY_KB_FILE_MAP:
                    kb_file = CATEGORY_KB_FILE_MAP[kb_intent]
                    general_context = self._retrieve_context(expanded, k=12, category=kb_file, user_id=user_id)
                    # work_experience 单独用原始文件内容兜底（向量搜索可能漏掉第二家公司）
                    if kb_intent == "work_experience":
                        _raw_exp = self._get_raw_work_experience(user_id)
                        if _raw_exp:
                            if general_context:
                                general_context = _raw_exp + "\n\n---\n\n" + general_context
                            else:
                                general_context = _raw_exp
                    if not general_context:
                        general_context = self._retrieve_context(expanded, k=12, user_id=user_id)
                elif kb_intent == "salary":
                    faq_context = self._retrieve_faq_context(expanded, intent=kb_intent, user_id=user_id)
                    general_context = self._retrieve_context(expanded, k=12, user_id=user_id)

                # faq intent: 同时走向量库（general_context）和 DB 精确匹配（faq_context）
                if kb_intent == "faq":
                    faq_context = self._retrieve_faq_context(expanded, intent=kb_intent, user_id=user_id)
                    if not faq_context and not general_context:
                        general_context = self._retrieve_context(expanded, k=12, user_id=user_id)
                elif kb_intent == "company_match":
                    _has_company, _company_name = await self._detect_company_intent(expanded)
                    if _has_company and _company_name:
                        _kb_has_exp = False
                        _exp_ctx = self._retrieve_context(expanded, k=5, category="03_工作经历", user_id=user_id)
                        if _exp_ctx and _company_name in _exp_ctx:
                            _kb_has_exp = True
                            general_context = _exp_ctx
                        if not _kb_has_exp:
                            _company_search_result = await self._search_company_info(_company_name, user_id=user_id)
                    if not general_context and not _company_search_result:
                        general_context = self._retrieve_context(expanded, k=12, user_id=user_id)
                elif kb_intent == "schedule_interview":
                    general_context = self._retrieve_context(expanded, k=5, user_id=user_id)
                else:
                    # "other" 意图：逐个分类定向检索（前面类型匹配不上才去匹配通用）
                    _parts = []
                    for _k, _cat in CATEGORY_KB_FILE_MAP.items():
                        _ctx = self._retrieve_context(expanded, k=6, category=_cat, user_id=user_id)
                        if _ctx:
                            _parts.append(_ctx)
                    if _parts:
                        general_context = "\n\n---\n\n".join(_parts)
                    else:
                        faq_context, general_context = await asyncio.gather(
                            asyncio.to_thread(self._retrieve_faq_context, expanded, "", user_id),
                            asyncio.to_thread(self._retrieve_context, expanded, 12, user_id=user_id),
                        )

                # 短查询兜底
                if not faq_context and not general_context and len(expanded.strip()) < 5:
                    _greetings = ["你好", "您好", "在吗", "在不在", "hi", "hello", "你是谁", "你叫什么"]
                    if expanded.strip() in _greetings:
                        fallback = self._retrieve_context("个人信息", k=3, user_id=user_id)
                        if fallback:
                            general_context = fallback

                system_parts = [_build_visitor_system_prompt(kb_intent, user_id)]

                # 公司信息在线搜索结果注入
                if _company_search_result:
                    system_parts.append(
                        '## 网络搜索结果（你不是这家公司的员工，以下信息仅作参考，可以说\u201c我查了一下\u201d）\n'
                        + _company_search_result
                    )

                # 相关性检查：检索结果中必须包含用户问题中的实质性词汇，否则跳过（防幻觉）
                # 注：对 intent 定向检索跳过此检查——意图分类已保证类别正确，ngram 子串匹配
                #    对「在哪些公司做过」这类 query 会误杀正确 context（ngram 无法匹配公司名）
                _gc_match = True
                # FAQ 上下文的 n-gram 检查跳过——FAQ 检索已有自己的匹配逻辑
                if not (faq_context or (kb_intent in CATEGORY_KB_FILE_MAP and kb_intent != "other")):
                    _raw = expanded.strip()
                    # 生成 n-gram：中文关键信息常在 2 字词（如"项目"），含中文时需覆盖 2-12 长度
                    _min_ngram = 2 if any('\u4e00' <= c <= '\u9fff' for c in _raw) else 3
                    _query_ngrams = set()
                    for i in range(len(_raw)):
                        for j in range(i + _min_ngram, min(i + 12, len(_raw) + 1)):
                            _chunk = _raw[i:j]
                            _query_ngrams.add(_chunk)
                    # 对英文/混合查询，也按空格分词
                    if ' ' in _raw:
                        _query_ngrams.update(t for t in _raw.split() if len(t) >= 3)
                    _faq_match = faq_context and any(t in faq_context for t in _query_ngrams)
                    _gc_match = general_context and any(t in general_context for t in _query_ngrams)
                    print(f"[rag_service] ctx_check query='{_raw}' ngrams={len(_query_ngrams)} faq_match={_faq_match} gc_match={_gc_match}")
                    if _query_ngrams:
                        if faq_context and not _faq_match:
                            print(f"[rag_service] skip faq: no ngram match")
                            faq_context = ""
                        if general_context and not _gc_match:
                            print(f"[rag_service] skip gc: no ngram match")
                            general_context = ""

                if faq_context:
                    system_parts.append(
                        '## 高频问答库预设答案（最高优先级——当用户问题与以下问答匹配时，必须完全以此为准回答，不得改用其他信息）\n'
                        + faq_context
                    )
                if general_context:
                    system_parts.append(
                        '## 其他参考信息（这是你的背景资料，必须基于此回答）\n'
                        + general_context
                    )
                system_prompt = "\n\n".join(system_parts)

                # 检索为空时的兜底逻辑
                if (not faq_context and not general_context and not _company_search_result
                    and any(kw in expanded for kw in ["工作", "公司", "经历", "毕业", "学校", "项目", "技能", "电话", "邮箱", "姓名", "简历", "介绍", "背景", "经验", "做过", "会的"])):
                    # 换精准查询词重试，有可能用户问法 vs 知识库片段向量匹配不上
                    fallback_queries = ["工作经历", "项目经历", "教育经历", "个人信息"]
                    retried = ""
                    for fq in fallback_queries:
                        retried = self._retrieve_context(fq, k=5, user_id=user_id)
                        if retried:
                            print(f"[rag_service] retry hit for '{fq}' on '{expanded}'")
                            break
                    if not retried:
                        retried = self._get_raw_work_experience(user_id)
                        if retried:
                            print(f"[rag_service] raw file fallback for '{expanded}'")
                    if retried:
                        system_parts.append('## 其他参考信息\n' + retried)
                        system_prompt = "\n\n".join(system_parts)
                        general_context = retried
                    else:
                        print(f"[rag_service] no KB data for personal query '{expanded}'")
                        yield "我不太清楚"
                        return

                user_message = f"{history_text}用户：{expanded}"

                # 防幻觉：从上下文中提取实体名，追加显性约束到用户消息中
                if general_context:
                    _known_entities = set()
                    for line in general_context.split("\n"):
                        line = line.strip()
                        if line.startswith("### "):
                            _known_entities.add(line[4:].split("(")[0].split("（")[0].strip())
                        if line.startswith("问题："):
                            _known_entities.add(line[3:].split(" 回答：")[0].strip())
                    if _known_entities:
                        user_message += (
                            "\n\n【注意】你的资料中实际存在的实体：" + str(_known_entities)
                            + "。绝对不能说这些之外的公司名、项目名、产品名。"
                        )
                        if kb_intent == "work_experience":
                            user_message += "\n你必须在回答中逐一列出以上所有公司，不得遗漏。"

                messages = [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_message),
                ]

                _t_before_stream = time.monotonic()
                print(f"[metrics] visitor.pre_stream duration={_t_before_stream-_t0:.3f}s (classify={_t1-_t0:.3f}s)")
                print(f"[rag_service] inject to LLM: has_faq={bool(faq_context)} has_general={bool(general_context)} has_search={bool(_company_search_result)} total_len={len(system_prompt)} query='{expanded}'")

                # Pure astream — no tool binding to avoid streaming interruptions.
                # Context retrieval already executed above, tool calls are unnecessary
                # and cause multi-second pauses mid-response.
                _ttfc = None
                llm_timer = Timer("visitor.llm_direct")
                llm_timer.start()
                _ts = 0
                _chunk_i = 0
                _success = False
                _last_err = None
                _accumulated_content = []
                _last_chunk = None
                for attempt in range(2):
                    try:
                        _ts = 0
                        _chunk_i = 0
                        _accumulated_content = []
                        _last_chunk = None
                        async for chunk in self.visitor_llm.astream(messages):
                            if chunk and chunk.content:
                                _chunk_i += 1
                                _now = time.monotonic()
                                if _ttfc is None:
                                    _ttfc = _now
                                    print(f"[metrics] visitor.ttfc duration={_ttfc-_t0:.3f}s")
                                if _ts and (_now - _ts) > 0.3:
                                    print(f"[rag_service] stream_gap={_now-_ts:.2f}s chunk#{_chunk_i} len={len(chunk.content)}")
                                _ts = _now
                                _accumulated_content.append(chunk.content)
                                yield chunk.content
                            _last_chunk = chunk
                        _success = True
                        break
                    except Exception as e:
                        err_str = str(e).lower()
                        if '429' in str(e) or 'rate_limit' in err_str or 'timeout' in err_str or 'connection' in err_str:
                            print(f"[rag_service] visitor LLM astream attempt {attempt} failed: {type(e).__name__}")
                            _last_err = e
                            continue
                        raise
                if not _success:
                    raise _last_err or Exception("visitor LLM unavailable")
                # Record usage after successful stream (non-blocking)
                try:
                    _usage = getattr(_last_chunk, "usage_metadata", None) if _last_chunk else None
                except Exception:
                    pass
                print(f"[metrics] visitor.llm_direct duration={llm_timer.elapsed:.2f}s")
                print(f"[metrics] visitor.answer_stream_total duration={timer.elapsed:.2f}s")
            except Exception as e:
                yield f"回答失败: {str(e)}"
    def _expand_short_question(self, question: str) -> str:
        """Expand short/referential questions based on common patterns."""
        q = question.strip()
        if q.isdigit():
            return f"请详细说明第{q}项，展开讲讲"
        if q in ("这个", "那个", "这家", "这家公司", "这个项目"):
            return f"{q}是什么？请详细介绍"
        if q in ("为什么", "为啥", "原因呢", "理由"):
            return f"{q}？请说明原因"
        return question

    def _chunk_text(self, text, chunk_size=50):
        for i in range(0, len(text), chunk_size):
            yield text[i:i+chunk_size]

rag_service = RAGService()
