# AnswerResume — Agent Knowledge Base

## 最新成果（2026-06-24）

### 岗位雷达抓取已完成
- **51job 完整抓取**：搜索列表 → 卡片提取(jobId/title/company/salary) → 自动构造详情页URL → 导航到详情页提取完整JD文本
- **支持「最新优先」排序**：自动点击排序按钮
- **支持翻页**：btn-next 翻页继续抓取
- **全部入库**：不管匹配分数高低，所有岗位都会保存到 crawled_jobs 表
- **JD详情页URL**：存入 jd_url 字段，前端可点击标题跳转到岗位详情
- **去重**：按 jd_url 去重，已存在的跳过

### 详情页改进（2026-06-24）
- **自动滚动**：进入详情页后逐次滚动触发懒加载，确保所有内容加载完毕
- **工作地址提取**：从详情页底部"工作地址"后提取完整街道地址（替代原来仅从卡片取区域名）
- **公司信息提取**：从详情页底部"公司信息"段提取公司描述（存入 company_info 字段）
- **JD文本更完整**：滚动后提取，长度上限 3000 字符

### JWT 认证要点
- `get_token_user_id()` 用 `settings.SECRET_KEY` 解码 JWT
- SECRET_KEY 取自环境变量（当前值：`hr-agent-secret-key-2026`），非 config.py 默认值
- JWT payload 必须含 `user_id` 字段（不是 `sub`）
- 解码失败时静默返回 `""`（空字符串），导致数据存到空 user_id → 用户看不到数据
- Python 模块名：`import jwt`（PyJWT），不是 `python-jose`

### 已知问题
- BOSS/智联的抓取未经完整测试（51job 已验证通过）

### 数据丢失记录（不要重犯）
- 6月24日：因 DATABASE_PATH 为 `/data/app.db`（不在 volume 挂载 `/app/data/`），重建容器导致6月8日~23日数据丢失
- 已永久修复：DATABASE_PATH = `/app/data/app.db`（在 volume 挂载点上）
- 安全协议：详见下方强制协议

## ⚠️ 强制安全协议（任何 AI 改代码前必须执行）

### 第0步：先确认「改什么」
- 一句话说清楚要改什么、解决什么问题
- 如果不确定，问用户，不要猜

### 第1步：代码备份
```bash
git add -A && git commit -m "BACKUP: before <改动简述>"
```
如果当前有未跟踪的新文件，先 `git add` 再 commit。
确保 HEAD 是干净的、可回退的。

### 第2步：数据备份
```bash
# PostgreSQL 数据库 + 用户数据 + 向量库 一键备份
bash scripts/backup.sh

# 或手动备份 PostgreSQL
docker compose exec postgres pg_dump -U gery -d answeragent \
  --format=custom -f /tmp/pre_change.dump
docker compose cp postgres:/tmp/pre_change.dump \
  backups/pre_change_$(date +%Y%m%d_%H%M%S).dump

# 手动备份 SQLite（如存在）
cp hr-agent/backend/data/app.db hr-agent/backend/data/app.db.$(date +%Y%m%d_%H%M%S)
```
保留多份备份，不要覆盖。备份文件命名格式：`backups/YYYYMMDD_HHMMSS/` 或 `app.db.YYYYMMDD_HHMMSS`

### 第3步：影响分析
- 要改的文件：列出文件名
- 谁引用了它：用 `grep -r` 或 `dep-graph` 技能分析依赖
- 改错了会怎样：比如改 DATABASE_PATH → 数据读不到；改 model 字段 → 数据库迁移失败
- 涉及数据库 schema 变更的：必须先检查 `database.py` 的迁移逻辑和数据表现有结构

### 第4步：改动原则
- **只改一个功能/修一个 bug**，不要顺手修不相关的东西
- 不要动 `config.py` 里的路径（除非用户明确要求，且必须验证 volume 挂载点）
- 不要动 `docker-compose.yml` 的 volume 映射
- 不要在数据库迁移脚本之外改表结构
- 改 prompt 模板先 `SELECT content FROM prompt_templates WHERE key='xxx'` 看现有内容，再 UPDATE

### 第5步：部署生效（关键！）

**改完代码不等于改完。** 必须确认代码运行在哪个进程/容器中，然后重启对应服务。

| 改了什么文件 | 需要重启谁 | 命令 |
|-------------|-----------|------|
| `services/*.py`, `routers/*.py`, `config/*.py` 等后端 Python | `answerresume-backend-1` | `docker cp` 改的文件 → `docker restart answerresume-backend-1` |
| `file_worker/main.py` | `answerresume-file-worker-1` | `docker cp` → `docker restart answerresume-file-worker-1` |
| `visitor_app.py` | `answerresume-visitor-1` | `docker restart answerresume-visitor-1` |
| `frontend/admin/src/*`（前端 TSX/TS） | 需要完整构建 | `npm run build` → 重启 gateway（挂载卷自动生效） |
| `deploy/nginx.conf`（gateway 的 nginx 配置） | `answerresume-gateway-1` | `docker restart answerresume-gateway-1` |

**原则：编辑任何 .py 文件后，除非确认容器有 `--reload` 或 volume mount 了源码目录，否则必须手动重启容器。不会自动生效。**

验证：
```bash
docker restart answerresume-backend-1
# 检查日志无报错
docker logs answerresume-backend-1 --tail 10
# 检查关键 API 正常
```

### 🔴 执行纪律（血泪教训，永远遵守）

1. **绝不跑 `docker compose down`** — 这会停掉所有容器（包括数据库），只能用 `docker stop` / `docker rm` 操作单个容器
2. **删东西前先问** — 任何 rm/stop/down 操作前，先确认被删的是什么、有没有其他服务依赖它
3. **只动要改的** — 用户问 A 问题，不要顺手修 B、删 C、改 D。一件事做完再做下一件
4. **改完旧的同步清理** — 修改代码/配置后，检查旧文件、旧服务、旧容器、旧端口是否还有引用。比如：改 docker-compose → 检查旧 docker-compose.yml 是否还在；改端口 → 检查旧端口是否还被其他地方引用；改前端入口 → 检查旧容器是否还在跑
5. **任务完成总结用中文** — 每个任务完成后，用中文总结改了哪些文件、每处改了什么、为什么改，以及验证结果。不要用英文写总结。

### 第6步：回滚方案
- `git revert HEAD` 回退代码
- `cp app.db.YYYYMMDD_HHMMSS app.db` 恢复数据
- `docker compose up --build -d` 重建容器

## 已知陷阱（补充）

### 9. visitor 服务端口映射

`deploy/nginx.conf` 中 `upstream visitor` 的端口（51670）必须与 `frontend/Dockerfile.visitor` 中 `gunicorn --bind` 的端口（51667）一致。

改 Dockerfile 的端口声明后，必须同步修改 `deploy/nginx.conf` 的 upstream 端口，然后 restart gateway 容器。

## 服务架构（Docker Compose）

| 服务 | 容器名 | 内部端口 | 宿主机端口 | 技术栈 |
|------|--------|----------|------------|--------|
| backend | `answerresume-backend-1` | 51666 | 51666 | FastAPI + Uvicorn, SQLAlchemy, LangChain, FAISS |
| visitor | `answerresume-visitor-1` | 51670 | 51670 | Flask |
| admin-frontend | `answerresume-admin-frontend-1` | 80 (nginx) | 51668 | React + Vite + Nginx |
| searxng | `searxng` | 8080 | 51669 | SearXNG |
| natapp | `answerresume-natapp-1` | — | — | 内网穿透 → asagent.me:51668 |

`hr-agent/docker-compose.yml`

### 重要路径映射（backend 容器）

| 宿主机 | 容器内 |
|--------|--------|
| `hr-agent/backend` | `/app` |
| `hr-agent/backend/data/app.db` | `/app/data/app.db`（SQLite，volume 持久化） |
| `hr-agent/backend/user_data/{uid}/` | `/app/user_data/{uid}/`（用户知识库、向量库、简历） |
| `hr-agent/backend/knowledge/` | `/app/knowledge/` |
| `hr-agent/frontend` | `/app/hr-agent/frontend`（visitor_app.py 所在） |

**⚠️ 数据库路径历史（血泪教训，永远不要搞错）：**
- 旧代码（init ~ 2026-06-24）：`DATABASE_PATH = os.path.join(__file__, "..", "data", "app.db")` → `/data/app.db`
  - ❌ **不在 volume 挂载点 `/app/data/` 上**
  - ❌ 每次重建容器数据就丢
  - ❌ 这个 bug 从第一个 commit `4f1d126`（5月12日）就有
- 修复后（2026-06-24）：`DATABASE_PATH = os.path.join(__file__, "data", "app.db")` → `/app/data/app.db`
  - ✅ **在 volume 挂载点 `/app/data/` 上**
  - ✅ 容器重建后数据不丢
  - ✅ volume 映射：`./hr-agent/backend/data:/app/data`
- **验证方法**：`stat /app/data/app.db` 的 device 必须和 `stat /app/data` 一致，且不同于 `stat /`

---

## 数据库

SQLite: `hr-agent/data/app.db`

关键表：

| 表 | 用途 | 关键字段 |
|----|------|---------|
| `users` | 用户 | id, username, password_hash (bcrypt), role (user/super_admin) |
| `user_configs` | 用户级配置 | user_id, config_key (visitor_password/visitor_enabled), config_value |
| `knowledge_base` | 结构化知识库 | user_id, category, data (JSON), 每个用户每种分类一条 |
| `conversations` | 访客对话记录 | session_id, role (user/ai), content, user_id |
| `sessions` | 访客会话 | id (即session_id), user_id, is_active |
| `portfolio_configs` | 个人主页配置 | user_id, style, blocks_order, contact_enabled (JSON) |
| `portfolio_contents` | 个人主页缓存 | user_id, content_json (JSON), built_at |
| `prompt_templates` | 系统提示词 | key, content, version |
| `applicant_profile` | 申请人配置 | user_id, workday_start/end, interview_duration_min 等 |

---

## Nginx 路由（admin-frontend 容器）

```
/             → React SPA (dist)
/admin/*      → proxy_pass ${BACKEND_URL}/admin/      (FastAPI)
/api/*        → proxy_pass ${BACKEND_URL}/api/        (FastAPI)
/visitor/*    → proxy_pass ${VISITOR_URL}/            (Flask, SSE)
```

开发环境用 Vite proxy（`vite.config.ts`），模拟相同路由。`npm run dev` 时访问 `localhost:51668`。

**SSE 关键设置**：`/visitor/` location 必须有 `proxy_buffering off; proxy_read_timeout 300s;`，否则 AI 对话流被 nginx 缓冲导致 504。

---

## 访客端内部路由（visitor_app.py，路径去掉 `/visitor/` 前缀后）

| 路径 | 方法 | 用途 |
|------|------|------|
| `/` | GET | 首页 |
| `/&lt;username&gt;` | GET | 用户访客页面 |
| `/verify` | POST | 访客口令验证（校验 user_configs.visitor_password） |
| `/chat` | POST | AI 对话（SSE stream） |
| `/api/welcome-config` | GET | 欢迎配置 + quick questions |
| `/api/check-session` | GET | 会话有效性检查 |
| `/portfolio-preview` | GET | 个人主页预览（调 backend `/admin/portfolio/visitor-preview`） |
| `/resume-preview` | GET | 简历预览 |
| `/download-resume` | GET | PDF 下载 |

JS 中 `VB` 变量自动适配前缀（有 `/visitor/` 时 VB=`/visitor`，否则 `''`）。

---

## 核心文件

### 后端
| 文件 | 职责 |
|------|------|
| `routers/admin.py` | Admin API（知识库 CRUD、简历、向量重建等），~2450 行 |
| `routers/visitor.py` | 访客 API（口令验证、对话流、预约） |
| `routers/portfolio.py` | 个人主页 API（配置、缓存重建、预览） |
| `services/rag_service.py` | **RAG 核心**：向量检索 + LLM 对话流（~1100 行） |
| `services/knowledge_manager.py` | 知识库 CRUD + MD 文件同步 + AI 解析 |
| `services/html_builder.py` | 个人主页/简历 HTML 生成器（4 套主题） |
| `services/resume_templates.py` | PDF 简历联系信息模板 |
| `services/pdf_service.py` | PDF 简历导出 |
| `services/prompt_manager.py` | 系统提示词版本管理（DB 持久化） |
| `services/intent_detector.py` | 用户意图分类 → 定向 KB 检索 |
| `services/ai_service.py` | AI 简历生成（调用 LLM 解析文本 → 结构化数据） |
| `services/session_manager.py` | 访客会话管理 |
| `services/portfolio_service.py` | 个人主页数据 + 缓存 |

### 前端
| 文件 | 职责 |
|------|------|
| `frontend/admin/src/pages/knowledge/KnowledgePage.tsx` | 知识库管理页面（个人信息、FAQ、技能等） |
| `frontend/admin/src/pages/config/MyConfigPage.tsx` | 个人配置页 |
| `frontend/admin/src/api/knowledge.ts` | 知识库 API 调用 |
| `frontend/admin/src/api/portfolio.ts` | 个人主页 API |
| `frontend/visitor_app.py` | Flask 访客端（~2200 行，含内联 JS/CSS/HTML） |

---

## 常用命令

```bash
# 构建 + 启动单个服务
docker compose build admin-frontend && docker rm -f answerresume-admin-frontend-1 && docker compose up -d admin-frontend

# 重启（代码变更后）
docker restart answerresume-backend-1
docker restart answerresume-visitor-1

# 查看日志
docker logs answerresume-backend-1 --tail 50 -f
docker logs answerresume-visitor-1 --tail 50 -f

# 重新构建向量库（全部）
docker exec answerresume-backend-1 python3 -c "
from services.rag_service import rag_service; from services.database import SessionLocal;
db = SessionLocal(); rag_service.build_main_with_mapping(db, user_id='用户UUID'); db.close()
"

# 重建个人主页缓存
docker exec answerresume-backend-1 python3 -c "
from services.portfolio_service import portfolio_service;
portfolio_service.rebuild(user_id='用户UUID')
"

# 进入容器
docker exec -it answerresume-backend-1 bash
docker exec -it answerresume-admin-frontend-1 sh
```

**`docker-compose` 已弃用，改用 `docker compose`。**

---

## 前端构建与部署流程

1. `npm run build`（`tsc -b && vite build` → `dist/`）
2. `docker compose build admin-frontend`（Dockerfile 把 `dist/` 拷进 nginx）
3. 删旧容器 + `docker compose up -d admin-frontend`

**只改 `KnowledgePage.tsx` 等源码不会生效** — 必须走完整构建流程。容器内没有挂载 `dist/` 目录。

---

## 关键架构细节

### RAG 服务（rag_service.RAGService）
- **模块级单例**：`rag_service = RAGService()`，应用生命周期内只有一个实例
- `self.vector_store`：共享的 FAISS 向量库引用（⚠️ 不要直接依赖它做跨用户操作）
- `self._vector_stores[user_id]`：每个用户一份的缓存，由 `_get_vector_store(user_id)` 懒加载
- **向量库污染风险**：`update_category()` 曾直接使用共享的 `self.vector_store` 导致跨用户数据交叉写入。已修复为：
  - `update_category` 和 `remove_by_ids` 现在直接从磁盘加载该用户的 FAISS 索引进行操作
  - 但仍需注意：修改涉及向量库操作时，必须加载对应用户的 store
- `_retrieve_context(question, k, category, user_id)` — 按分类检索，先全量搜索再过滤 metadata.category
- `answer_stream(question, conversation_history, use_visitor_llm, user_id)` — AI 对话 SSE 流

### 访客对话流程
1. 用户访问 `/visitor/{username}` → Flask 渲染含 `_USER_ID` 和 `_HAS_PASSWORD` 的内联 HTML
2. 输入口令 → POST `/verify` → 后端校验 `user_configs.visitor_password` → 创建 session
3. 发送消息 → POST `/chat` → `rag_service.answer_stream()` → SSE 流式返回
4. 每次请求必须带 `X-Session-ID` header（Flask 路由也回退到 `session.get()` 或 `request.args`）
5. 对话结束后异步检测意图，判断是否建议预约面试

### 知识管理流程
1. Admin 页面保存 → POST `/admin/knowledge-structured/{category}` → `knowledge_base` 表写入 JSON
2. `_sync_knowledge_to_md()` 同步写入 `user_data/{uid}/knowledge/{category}.md`
3. `rag_service.update_category()` 更新 FAISS 向量库中该分类的向量
4. 个人主页使用独立的**缓存**（`portfolio_contents` 表），**不自动同步**
   - 知识库变更后，必须手动或通过 API 触发 `portfolio_service.rebuild(user_id)`
   - 否则个人主页显示的仍是旧数据（常见陷阱）

### 个人主页缓存
- `portfolio_service.get_knowledge_data()` 优先返回 `portfolio_contents.content_json`（缓存）
- 无缓存时才从 `_get_all_kb_data()` 实时读取
- **缓存重建后**才展示最新数据（github URL、personal_website 等）

### 向量库文件
每个用户独立目录：`user_data/{uid}/vector_store/index.faiss` + `index.pkl`
- `main_kb_ids`（`knowledge_base` 表 entry）记录每个分类的 doc_id 映射
- `update_category` 时：删旧 doc_id → 加载 MD 文件 → 分块 → 添加新向量 → 更新映射

---

## 已知陷阱

### 1. Nginx 两个副本

- 源码：`frontend/admin/nginx.conf`（Dockerfile 构建时 COPY 的模板）
- 运行态：容器内 `/etc/nginx/conf.d/default.conf`
- 改源码后必须 `docker compose build admin-frontend && docker compose up -d admin-frontend`

### 2. visitor_app.py 不自动重载

visitor 容器用 bind mount 同步文件，但 Python 进程不带 `--reload`。改代码后必须 `docker restart answerresume-visitor-1`。

### 3. 个人主页缓存不同步

保存知识库 → 向量库更新 → 但个人主页缓存不更新。
修复：`portfolio_service.rebuild(user_id=用户UUID)`。
症状：GitHub 链接乱跳（缓存中 github 字段不带 `https://` 前缀）、personal_website 不显示。

### 4. 向量库跨用户污染（已修复）

旧代码中 `update_category()` 用共享 `self.vector_store` 单例做 `add_documents`+`save_local`。如果另一个用户的向量库先被加载进来，新文档会追加到错误用户的索引中。
当前代码已修复为直接加载对应用户的 FAISS 索引。如果未来修改涉及向量库操作，必须确保不通过共享单例跨用户操作。

### 5. X-Session-ID 传递（高危）

访客页面的 API 调用必须通过以下方式之一传递 session：
- HTTP header `X-Session-ID`（推荐，fetch 调用）
- Flask session cookie（同域页面导航）
- URL query `?session_id=`（仅 `window.open` 场景）

新建任何访客端 API 调用时，必须同时覆盖这几种传递方式。

### 6. Domain 隔离

`localhost:51668` 和 `asagent.me`（natapp）localStorage/cookie 独立。切域必须重新输入口令。

### 7. 数据库路径（DATABASE_PATH）必须落在 volume 挂载点内

**⚠️ 致命陷阱，已造成多次数据丢失。**

`config.py` 中 `DATABASE_PATH` 的 `os.path.join(__file__, "..", "..")` 解析结果必须仔细验证。

当前正确值（已修复，禁止改回）：
```python
DATABASE_PATH: str = os.path.join(os.path.dirname(__file__), "data", "app.db")
# → /app/data/app.db ✅ 在 volume 挂载上
```

任何时候修改 `config.py` 中的路径，必须：
1. 确认最终解析路径落在 `/app/data/` 下（volume 挂载点）
2. `docker exec answerresume-backend-1 stat /app/data/app.db` 的 device 与 `/app/data` 一致
3. 确认 `docker inspect answerresume-backend-1 | grep -A5 Mounts` 中 `./backend/data` 挂载到 `/app/data`

**备份策略：** 操作数据库前，先 `cp app.db app.db.backup_$(date +%Y%m%d_%H%M%S)`。所有备份文件必须保存在 `./hr-agent/backend/data/` 目录下。

### 8. Docker Compose 命令

`docker-compose`（旧版 hyphen 命令）已弃用。用 `docker compose`（新版子命令）。

---

## 多步骤任务工作流

当任务是**多步骤、跨文件改造任务**（如架构重构、功能迁移、大规模代码变更）时，必须遵循以下规范：

### 1. 先建计划，再动手
- 开始前创建/确认计划文档（如 `架构分析与改进方案.md`）
- 计划文档必须包含：分批策略、每批目标文件、风险等级
- 计划文档写入文件系统，不要只留在对话中

### 2. 用 task list 跟踪进度
- `todowrite` 每批次一个 item，粒度可回退（git commit level）
- 一个 item 对应一个阶段 → 一个 git commit

### 3. 发现问题先改计划
- 如果在执行中发现某文件比预期大、风险比预期高、策略不适用，**必须先更新计划文档**
- 计划文档中要记录：问题描述、原因、替代方案、调整后的策略
- 改完计划再继续执行

### 4. 批处理原则
- 每个批次独立可回退（git commit）
- 每批完成后跑测试
- 批次间如果有外部依赖（如 Docker 重启），在 plan 中注明

### 5. 文档同步
- 计划文档、todowrite、git commit message 三者保持一致
- 关键决策（如"不迁移 xx 文件"、"延后 yy 功能"）记入 plan 文档

### 当前 Phase 1.5 状态

参见 `架构分析与改进方案.md` 第五章的 Phase 1.5 分批策略。

---

## 外部工具

### lark-cli
- 安装：`/home/geryj/.hermes/node/bin/lark-cli`
- 认证：`lark-cli auth login --as user`（设备码流，需浏览器确认）
- Feishu Base 操作：`lark-cli base +record-list --as user --base-token {token} --table-id {table_id} --format json`
- **批次写入**：`+record-batch-create` 用 `fields` + `rows`；`+record-batch-update` 用 `record_id_list` + `patch`
- 注意：Base 操作需要 `base:field:read` 等 scope，bot 账户可能缺少某些 scope，用 `--as user`

### natapp
- 映射 `localhost:51668` → `asagent.me`（admin-frontend 的端口）
- visitor 和 backend 不走 natapp，通过 nginx proxy_pass 转发

---

## 数据备份

### 备份内容与路径

| 数据 | 宿主机路径 | 容器内路径 | 说明 |
|------|-----------|-----------|------|
| PostgreSQL | Docker volume: `answerresume_postgres_data` | `/var/lib/postgresql/data/` | 主数据库（用户、知识库、对话、配置） |
| User Data | `hr-agent/backend/user_data/` | `/app/user_data/` | 用户知识库 .md、FAISS 向量库、简历输出 |
| Vector Store | `hr-agent/vector_store/` | `/app/vector_store/` | 向量索引文件 (index.faiss + index.pkl) |
| SQLite | `hr-agent/backend/data/app.db` | `/app/data/app.db` | 旧版兼容，Docker 部署以 PostgreSQL 为主 |
| 环境变量 | `hr-agent/.env` / `hr-agent/backend/.env` | — | API Key 等敏感配置 |

### 一键备份脚本

```bash
# 备份到默认目录 backups/YYYYMMDD_HHMMSS/
bash scripts/backup.sh

# 备份到指定目录
bash scripts/backup.sh /mnt/d/backups/answerresume
```

备份内容：
- PostgreSQL → `postgres.dump`（custom format，`pg_restore` 可恢复）
- User Data → `user_data.tar.gz`
- Vector Store → `vector_store.tar.gz`
- .env 配置文件（自动移除敏感字段）
- SQLite → `app.db`（仅当存在时）

### 恢复流程

```bash
# 1. 恢复 PostgreSQL
docker compose exec -T postgres pg_restore -U gery -d answeragent \
  --clean --if-exists < backups/20260628_030000/postgres.dump

# 2. 恢复 user_data
tar -xzf backups/20260628_030000/user_data.tar.gz \
  -C hr-agent/backend/

# 3. 恢复 vector_store
tar -xzf backups/20260628_030000/vector_store.tar.gz \
  -C hr-agent/

# 4. 重启后端
docker compose restart backend rag-worker

# 5. 重建向量库缓存
docker exec answerresume-backend-1 python3 -c "
from services.rag_service import rag_service; from services.database import SessionLocal;
db = SessionLocal(); rag_service.build_main_with_mapping(db, user_id='用户UUID'); db.close()
"
```

### CRON 自动备份（Linux/WSL）

已配置：每天凌晨 3 点自动备份。

```bash
# 查看当前定时任务
crontab -l

# 日志查看
tail -f /mnt/d/trae/projects/answerresume/backups/backup.log
```

#### ⚠️ WSL 重启后 cron 不会自启

```bash
# 检查 cron 是否在运行
pgrep cron || echo "cron 未运行"

# 手动启动
sudo service cron start

# 设置 WSL 启动时自启（编辑 ~/.bashrc 或 ~/.profile）
echo "sudo service cron start" >> ~/.bashrc
```

或者使用 Docker 容器调度（更可靠，随 Docker 自启）：
```bash
docker run -d --name cron-backup --restart unless-stopped \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v /mnt/d/trae/projects/answerresume:/workspace \
  alpine:latest sh -c "
    echo '0 3 * * * /bin/sh /workspace/scripts/backup.sh' > /etc/crontabs/root
    crond -f
  "
```

备份保留 30 天，超期自动清理。

### 手动备份（操作前必做）

修改数据库或关键配置前：

```bash
# PostgreSQL
docker compose exec postgres pg_dump -U gery -d answeragent \
  --format=custom -f /tmp/pre_change.dump
docker compose cp postgres:/tmp/pre_change.dump ./backups/pre_change_$(date +%Y%m%d_%H%M%S).dump

# 用户数据
cp -r hr-agent/backend/user_data "hr-agent/backend/user_data.bak.$(date +%Y%m%d_%H%M%S)"
```

---

## WSL2 时钟漂移修复

### 问题
笔记本合盖/休眠唤醒后，WSL2 时钟可能偏差数秒到数分钟，导致：
- HTTPS 证书验证失败 → API 请求报 SSL 错误
- JWT token 被判定过期 → 会话异常中断
- 数据库时间戳混乱

### 修复方法

在 **Windows 管理员 PowerShell** 中执行：

```powershell
# 立即同步
wsl -d Ubuntu -u root hwclock -s

# 注册开机 + 唤醒自启任务
PowerShell -ExecutionPolicy Bypass .\scripts\wsl-time-sync.ps1
```

脚本 `scripts/wsl-time-sync.ps1` 会自动：
1. 立即同步一次 WSL 时间
2. 注册 Windows 计划任务 `WSL2-TimeSync`（开机 + 唤醒时自动同步）

### 手动验证

```bash
# 对比 Windows 和 WSL 时间
date
# 如果偏差大，手动同步
sudo hwclock -s
```
