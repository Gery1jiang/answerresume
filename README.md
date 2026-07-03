# AnswerResume — AI 求职助手

基于大语言模型的智能简历与问答系统。求职者通过管理端维护知识库，AI Agent 辅助管理，访客（HR/招聘方）通过访客端进行智能问答、简历下载和个人主页浏览。

> 管理端：http://localhost:51668 | 访客端：http://localhost:51668/visitor/{username}
> 默认管理员：admin / admin123

---

## 架构

```
answerresume/
├── hr-agent/
│   ├── backend/           # FastAPI 后端 (51666)
│   │   ├── routers/       # 路由层（admin/visitor/agent/auth 等 7 模块）
│   │   ├── services/      # 业务逻辑（RAG、Agent、简历、知识库等）
│   │   └── models/        # 21 张 SQLAlchemy 表
│   ├── frontend/
│   │   ├── admin/         # React SPA 管理端 (Vite + Ant Design 6)
│   │   └── visitor_app.py # Flask 访客端
│   └── user_data/         # 按 user_id 隔离的用户数据
├── docker-compose.yml     # 9 个服务编排
├── .env                   # API Key 等配置
└── deploy/nginx.conf      # 统一网关 (51668)
```

## 技术栈

| 模块 | 技术 |
|------|------|
| 后端 | Python FastAPI + LangGraph + SQLAlchemy |
| 数据库 | PostgreSQL 16 |
| 向量库 | FAISS + BAAI/bge-m3 (SiliconFlow) |
| Agent | LangGraph 状态图（14 工具 + HITL） |
| PDF | Playwright (Chromium) |
| 管理端 | React 19 + Ant Design 6 + Vite 8 + Zustand + Recharts |
| 访客端 | Python Flask + 内联 HTML/CSS/JS |
| 网关 | nginx |
| 容器化 | Docker Compose（9 个服务） |

## 功能特性

### 🤖 Agent 对话管理
- 自然语言交互，支持多轮对话与 SSE 流式输出
- 14 个 Agent 工具：简历生成/解析、网络搜索、职位爬取、面试记录管理、知识库预览与确认、向量库重建、数据统计查询
- 人工确认（HITL）敏感操作，多步骤自动编排

### 📋 简历管理
- 🎨 AI 简历生成器：输入经历 → 融合知识库 → STAR 法则 + 量化数据 → JSON 简历
- 🖼 多模板支持（modern / classic / minimal 等）
- 📥 PDF 预览与下载（文件名：`姓名_职位_手机号.pdf`）
- 📌 设为默认、删除管理

### 🌐 个人主页（Portfolio）
- 🎨 四种主题风格：
  - Editorial / 杂志风 — 适合产品经理、市场、咨询
  - Developer / 工程师风 — 适合前端、后端、AI 工程师、DevOps
  - Creative / 创意人风 — 适合 UI/UX 设计师、视觉设计、摄影
  - Personal Brand / 个人品牌风 — 适合运营、增长、内容
- 📝 内容区块可配置（拖拽排序、显示/隐藏）
- 📤 HTML 导出与新窗口预览

### 💬 访客对话
- 🔐 口令验证登录（支持按用户独立口令 + 全局口令）
- 💬 AI 智能问答（意图分类 + RAG 知识库检索 + 向量库协同）
- 📄 简历预览与 PDF 下载
- 🌐 个人主页浏览
- ⚡ 快捷问题按钮 + 自定义招呼语
- 📅 面试预约（含通勤计算与冲突检测）
- 🚫 IP 级频率限制（10 次失败锁定 10 分钟）

### 📚 知识库管理
- 表单化编辑 7 个分类：
  - 个人信息、教育背景、工作经历、项目经历、专业技能、HR 高频问答、附录知识库
- Agent 驱动智能替换：单字段替换、整段经历替换、FAQ 智能再生
- FAISS 向量库自动更新：每次保存自动重建该分类索引

### 📋 面试宝典
- 面试记录全生命周期管理：待确认 / 已确认 / 已取消 / 已完成
- 自动生成面试报告 PDF（含公司调研、产品分析、面试建议）
- Agent 自动创建与管理

### 🔍 职位雷达
- Kimi WebBridge 浏览器自动化爬取 51job / Boss 直聘 / 智联招聘
- AI 匹配评分（与候选人画像对比）
- 手动增删改查

### ⚙️ 系统管理
- 🏷️ 访客招呼语、个人介绍、快捷问题配置
- 🧠 LLM 供应商切换（支持 10+：SiliconFlow、LongCat、DeepSeek、OpenAI、Anthropic、Google 等）
- 🌓 主题切换（跟随系统 / 浅色 / 深色）
- 🔧 会话超时、最大会话数、访客密码
- 📈 Token 用量统计（按用户 / 按日周月）

### 📊 数据统计
- 📈 访客会话统计（访问量、对话数、下载量、主页浏览）
- 💬 高频问题 Top-N 分析

## 知识库结构

```
表单保存 → KnowledgeBase 表 (PostgreSQL JSON)
     ↓
 同步 .md 文件
     ↓
 更新 FAISS 向量库
     ↓
 RAG 问答检索生效
```

| 分类 | 说明 |
|------|------|
| 个人信息 | name, age, city, email, phone, github, work_years, self_intro |
| 教育背景 | 学校 / 学历 / 专业 / 时间 |
| 工作经历 | 公司 / 职位 / 时间 / 描述（按时间倒序） |
| 项目经历 | 项目名 / 角色 / 技术栈 / 描述 |
| 专业技能 | 硬技能 / 软技能 / 工具平台 |
| HR 高频问答 | Q&A 列表，支持智能再生 |
| 附录知识库 | 外部上传的补充文档 |

## 快速开始

### 环境要求
- Docker & Docker Compose
- API Key（至少需要 LongCat + SiliconFlow）

### 启动

```bash
git clone https://github.com/Gery1jiang/answerresume.git
cd answerresume
# 编辑 .env 填入 API Key
docker compose up -d --build
```

### 访问

| 地址 | 说明 |
|------|------|
| http://localhost:51668 | 管理端 |
| http://localhost:51668/visitor/{username} | 访客端 |
| http://localhost:51666/docs | API 文档 |

## 环境变量

| 变量 | 用途 |
|------|------|
| `LONGCAT_API_KEY` | 管理端 + Agent LLM |
| `SILICONFLOW_API_KEY` | Embedding 模型 |
| `DEEPSEEK_API_KEY` | 访客 LLM + 意图识别 |
| `TAVILY_API_KEY` | Agent 网络搜索 |
| `FIRECRAWL_API_KEY` | 深度网页抓取 |
| `AMAP_API_KEY` | 高德地图（访客端地址选择） |
