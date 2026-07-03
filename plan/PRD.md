# AnswerResume 产品需求文档 (PRD)

> **版本**: v2.0  
> **更新**: 2026-06-10  
> **状态**: 开发中 (迭代二)

---

## 1. 产品概述

### 1.1 产品定位

AnswerResume 是一款面向求职者的 **智能简历与个人品牌管理平台**。它通过 RAG（检索增强生成）技术，将求职者的个人信息、工作经历、项目经验等结构化知识库与大语言模型结合，为求职者和招聘方提供双向智能服务。

### 1.2 核心价值主张

- **求职者**：一键生成 AI 简历，搭建个人主页，通过 Agent 智能问答展示个人能力
- **招聘方**：通过访客端智能问答快速了解候选人，预约面试，下载简历
- **管理员**：多用户管理，用量监控，系统配置

### 1.3 产品目标

1. 帮助求职者高效构建个人知识库并自动生成多模板简历
2. 提供 7×24 小时 AI 求职助手，自动应答招聘方的提问
3. 搭建求职者个人品牌页面（个人主页），支持多种主题风格
4. 实现求职 Agent 自动爬取匹配岗位，生成面试指南
5. 建立会员与用量体系，支撑商业化运营

---

## 2. 目标用户与用户故事

### 2.1 用户角色

| 角色 | 标识 | 数量 | 权限范围 |
|------|------|------|----------|
| **超级管理员** | `role=super_admin` | 2 | 用户管理、系统配置、全局用量、所有数据可见 |
| **普通用户 (求职者)** | `role=user` | 4（当前） | 管理自己的知识库、简历、个人主页、Agent |
| **访客 (招聘方)** | 无账号 | 不限 | 浏览访客端、问答、下载简历、预约面试 |
| **招聘者** | `role=recruiter` | 0（规划中） | 独立招聘平台，管理职位、查看候选人 |

### 2.2 用户故事

#### 求职者 (User)

```
作为求职者
我希望表单化编辑我的个人信息、工作经历、项目经验、技能等
以便系统自动同步到知识库 Markdown 和向量库中，AI 问答时能准确回复

作为求职者
我希望一键生成 AI 简历并选择不同模板
以便高效投递不同风格的职位

作为求职者
我希望搭建个人主页并选择 4 种主题中的一种
以便向招聘方展示个人品牌

作为求职者
我希望通过 Agent 对话自然语言操作（生成简历、搜索职位、修改知识库）
以便不需要逐个点菜单操作

作为求职者
我希望系统自动爬取招聘网站的岗位并与我的简历匹配
以便发现最合适的职位机会

作为求职者
我希望系统自动生成面试指南（含通勤计算、时间冲突检测）
以便充分准备面试
```

#### 访客 / 招聘方 (Visitor)

```
作为访客
我希望输入候选人提供的口令后进入对话页
以便向 AI 提问了解候选人的详细情况

作为访客
我希望查看和下载候选人的 PDF 简历
以便保存和传阅

作为访客
我希望浏览候选人的个人主页
以便全面了解其个人品牌和作品

作为访客
我希望在线预约面试时间（系统自动检测档期冲突）
以便高效安排面试日程
```

#### 超级管理员 (Super Admin)

```
作为超级管理员
我希望查看所有用户的注册信息和状态
以便管理用户账号（启用/禁用）

作为超级管理员
我希望查看所有用户的用量数据（对话数、LLM tokens、存储空间）
以便进行成本控制和计费

作为超级管理员
我希望设置会员等级和对应的功能/用量限制
以便实现产品商业化
```

---

## 3. 功能需求

### 3.1 功能总览

| 模块 | 功能点 | 优先级 | 状态 |
|------|--------|--------|------|
| 知识库 | 表单化编辑 7 分类 | P0 | ✅ 已完成 |
| 知识库 | AI 智能替换（单字段/整段/全局换人） | P1 | ✅ 已完成 |
| 知识库 | FAQ 智能再生 | P1 | ✅ 已完成 |
| 知识库 | 附录知识库（外部文档上传） | P1 | ✅ 已完成 |
| 知识库 | 分类级增量向量重建 | P1 | ✅ 已完成 |
| 简历 | AI 简历生成（融合知识库） | P0 | ✅ 已完成 |
| 简历 | 多模板支持（modern/classic/minimal 等） | P1 | ✅ 已完成 |
| 简历 | PDF 导出（Pyppeteer + Chromium） | P1 | ✅ 已完成 |
| 个人主页 | 4 种主题风格（Editorial/Developer/Creative/Personal Brand） | P1 | ✅ 已完成 |
| 个人主页 | 内容区块显示/隐藏配置 | P1 | ✅ 已完成 |
| 个人主页 | 缓存管理（知识库变更后重建） | P1 | ✅ 已完成 |
| 个人主页 | 访客预览 | P2 | ✅ 已完成 |
| 访客端 | 口令验证登录 | P0 | ✅ 已完成 |
| 访客端 | AI 问答（RAG + 意图定向检索） | P0 | ✅ 已完成 |
| 访客端 | 快速问题按钮 | P1 | ✅ 已完成 |
| 访客端 | 自定义招呼语 | P1 | ✅ 已完成 |
| 访客端 | 简历预览与下载 | P0 | ✅ 已完成 |
| 访客端 | 个人主页浏览 | P1 | ✅ 已完成 |
| 访客端 | 面试预约（含冲突检测+通勤计算） | P1 | ✅ 已完成 |
| 助手 Agent | 多轮对话 + 工具调用 | P0 | ✅ 已完成 |
| 助手 Agent | 生成简历 | P1 | ✅ 已完成 |
| 助手 Agent | 知识库预览与确认修改 | P1 | ✅ 已完成 |
| 助手 Agent | 向量库重建 | P1 | ✅ 已完成 |
| 系统配置 | LLM/Embedding 模型配置 | P1 | ✅ 已完成 |
| 系统配置 | 服务参数（会话超时、最大会话数） | P1 | ✅ 已完成 |
| 系统配置 | 提示词管理 + 版本管理 | P1 | ✅ 已完成 |
| 系统配置 | 模型连接测试 | P2 | ✅ 已完成 |
| 求职 Agent | 职位爬取（自定义搜索） | P1 | ✅ 已完成 |
| 求职 Agent | JD 解析与结构化存储 | P1 | ✅ 已完成 |
| 求职 Agent | 简历与 JD 批量匹配 | P1 | ✅ 已完成 |
| 面试指南 | 面试创建（公司/岗位/时间） | P1 | ✅ 已完成 |
| 面试指南 | 通勤时间自动计算 | P1 | ✅ 已完成 |
| 面试指南 | 面试时间冲突检测 | P1 | ✅ 已完成 |
| 面试指南 | 面试报告自动生成 | P1 | ✅ 已完成 |
| 数据统计 | 访客会话统计 | P1 | ✅ 已完成 |
| 数据统计 | 高频问题分析 | P2 | ✅ 已完成 |
| 用量统计 | LLM Token 用量追踪 | P2 | ✅ 已完成 |
| 用量统计 | 按用户/时间维度统计 | P2 | ✅ 已完成 |
| 认证 | 用户注册 | P0 | ✅ 已完成 |
| 认证 | 登录（JWT） | P0 | ✅ 已完成 |
| 认证 | 密码修改 | P1 | ✅ 已完成 |
| 认证 | 用户管理（超管） | P2 | ⬜ 待完善 |
| 会员体系 | 会员等级定义与指标可视化 | P3 | ⬜ 待规划 |
| 招聘者平台 | 独立招聘者管理平台 | P3 | ⬜ 待规划 |
| 求职 Agent 开关 | 求职和招聘 Agent 自动开启/关闭 | P2 | ⬜ 待规划 |

### 3.2 知识库管理 (P0)

#### 3.2.1 功能描述

求职者通过表单化界面维护 7 个分类的知识条目，系统自动同步为 Markdown 文件并更新 FAISS 向量库，AI 问答时通过 RAG 检索相关上下文。

#### 3.2.2 知识分类

| 分类 | 存储键 | 内容说明 | 表单字段 |
|------|--------|----------|----------|
| 个人信息 | `personal_info` | 姓名、年龄、城市、邮箱、电话、GitHub、个人网站、工作年限、自我评价等 | 单表单，20+ 字段 |
| 教育背景 | `education` | 学校列表（学校名/学历/专业/时间） | 动态列表 |
| 工作经历 | `work_experience` | 公司列表（公司/职位/时间/描述） | 动态列表，按时间排序 |
| 项目经历 | `projects` | 项目列表（项目名/角色/技术栈/描述） | 动态列表 |
| 专业技能栈 | `skills` | 硬技能/软技能/工具平台分组 | 分组键值对 |
| HR高频问答 | `faq` | 15 条预设 Q&A，支持智能再生 | 动态列表 |
| 附录知识库 | `appendix` | 上传的文档（PDF/Word/MD） | 文件上传 + AI 摘要 |

#### 3.2.3 验收标准

- [ ] 用户可表单化增删改查每个分类的全部字段
- [ ] 保存后自动同步对应的 Markdown 文件
- [ ] 保存后自动重建该分类的 FAISS 向量索引
- [ ] 附录支持 PDF/Word/TXT/MD 文件上传和 AI 摘要生成
- [ ] 附录支持目录结构管理（添加/删除外部路径）
- [ ] FAQ 支持一键 AI 再生全部答案

### 3.3 简历管理 (P0)

#### 3.3.1 功能描述

融合知识库内容，通过 LLM 结构化为 JSON 简历数据，支持多模板渲染和 PDF 导出。

#### 3.3.2 模板风格

- **modern**: 现代专业风格，蓝色为主色调
- **classic**: 经典风格，黑色为主
- **minimal**: 极简风格
- **creative**: 创意风格（供设计师使用）

#### 3.3.3 验收标准

- [ ] 一键生成 JSON 简历（融合全部知识库分类）
- [ ] 支持在生成的 JSON 基础上手动微调
- [ ] 切换模板即时预览 HTML 效果
- [ ] PDF 导出可下载（Pyppeteer 渲染）
- [ ] 简历开关控制访客端是否可见

### 3.4 个人主页 (P1)

#### 3.4.1 功能描述

求职者的个人品牌展示页面，从知识库自动生成内容，支持 4 种主题风格和内容区块配置。

#### 3.4.2 主题风格

| 主题 | 风格描述 | 目标人群 |
|------|----------|----------|
| Editorial / 杂志风 | 大标题 + 图文混排，杂志排版感 | 产品经理、市场、咨询 |
| Developer / 工程师风 | 代码块式排版，技术感 | 前端、后端、AI 工程师 |
| Creative / 创意人风 | 视觉冲击布局，大图+留白 | 设计师、摄影师 |
| Personal Brand / 个人品牌风 | 个人品牌感，数据+头像突出 | 运营、增长 |

#### 3.4.3 验收标准

- [ ] 4 种主题风格可选
- [ ] 内容区块可单独显示/隐藏
- [ ] 联系方式开关控制 GitHub/网站/邮箱/电话可见性
- [ ] 个人主页开关控制访客端是否显示
- [ ] 知识库变更后支持手动重建缓存
- [ ] 支持管理端实时预览和访客预览

### 3.5 访客端 (P0)

#### 3.5.1 用户流程

```
输入口令 → 验证通过 → 进入对话页
                              ├── AI 问答（RAG 检索增强）
                              ├── 快捷问题按钮
                              ├── 简历预览/下载
                              ├── 个人主页浏览（如有配置）
                              └── 面试预约（含档期建议）
```

#### 3.5.2 验收标准

- [ ] 口令验证保护访客页面
- [ ] AI 问答结合 RAG 检索知识库返回准确答案
- [ ] 支持多轮对话上下文
- [ ] 快捷问题按钮可配置
- [ ] 招呼语可配置
- [ ] 简历预览 HTML + PDF 下载
- [ ] 个人主页展示（如已配置）
- [ ] 面试预约提交 + 档期冲突检测
- [ ] 通勤时间自动计算（高德地图 API）

### 3.6 助手 Agent (P0)

#### 3.6.1 功能描述

管理端的自然语言交互入口，基于 LangChain 工具调用架构，支持多轮对话完成复杂操作。

#### 3.6.2 工具清单

| 工具 | 功能 | 调用条件 |
|------|------|----------|
| 生成简历 JSON | 融合知识库生成结构化简历 | 用户说"生成简历" |
| 搜索网络 | Firecrawl/AnySearch 搜索 | 用户问需外部信息的问题 |
| 知识库预览 | 读取指定分类的当前内容 | 用户问"我的工作经历是什么" |
| 知识库确认修改 | 修改确认后写入知识库并重建向量 | 用户说"把公司名改成XXX" |
| 向量库重建 | 重建全部 FAISS 索引 | 用户说"重建向量库" |

#### 3.6.3 验收标准

- [ ] 多轮对话保持上下文
- [ ] 工具调用准确（意图识别 + 参数提取）
- [ ] 知识库修改需用户确认后才执行
- [ ] 支持流式输出（SSE: Server-Sent Events）
- [ ] 对话历史持久化到数据库
- [ ] 支持清除对话历史

### 3.7 求职 Agent (P1)

#### 3.7.1 功能描述

自动爬取招聘网站（Boss直聘等）的职位信息，解析 JD 并与求职者简历进行智能匹配。

#### 3.7.2 验收标准

- [ ] 自定义搜索条件（关键词/城市/平台）
- [ ] 职位爬取与 JD 解析（结构化存储）
- [ ] 简历与 JD 的批量匹配评分（含匹配细节）
- [ ] 匹配结果展示（评分排序、匹配详情高亮）
- [ ] 爬取任务状态跟踪

### 3.8 面试指南 (P1)

#### 3.8.1 功能描述

管理面试日程，自动计算通勤时间，检测面试时间冲突，并生成完整的面试报告。

#### 3.8.2 验收标准

- [ ] 创建面试记录（公司/岗位/HR信息/时间/地址）
- [ ] 自动计算从申请人地址到面试地点的通勤时间（高德 API）
- [ ] 时间冲突检测（每日最大面试数、间隔时间等）
- [ ] AI 生成面试准备报告（公司背景+岗位分析+注意事项）
- [ ] 面试状态管理（待面试/已完成/已取消）

### 3.9 管理后台 (P1)

#### 3.9.1 页面清单

| 菜单 | 页面 | 功能 |
|------|------|------|
| 知识库 | `knowledge/` | 7 分类表单化编辑 |
| 简历 | `resume/` | AI 简历生成、模板切换、PDF 导出 |
| 个人主页 | `portfolio/` | 主题选择、区块配置、预览 |
| 助手 Agent | `agent/` | Agent 对话 |
| 求职 Agent | `jobs/` | 职位爬取、JD 匹配 |
| 面试指南 | `interview-guide/` | 面试管理、报告生成 |
| 提示词管理 | `prompts/` | 系统提示词版本管理 |
| 数据统计 | `statistics/` | 访客会话统计、高频问题 |
| 用量统计 | `usage/` | LLM Token 用量 |
| 系统配置 | `config/` | LLM/Embedding/服务参数 |
| 申请人配置 | `applicant-profile/` | 面试偏好设置 |

---

## 4. 新需求规划（迭代二，2026 Q2-Q3）

以下 7 项需求在迭代一的开发过程中通过飞书多维表格持续收集，已按优先级排序：

### 4.1 【P1】Agent 菜单重构：增加"求职 Agent"入口

**需求描述**：当前 Agent 菜单统一为"助手 Agent"，需要拆分为两个独立入口：
- **助手 Agent**：现有的多轮对话 + 工具调用（生成简历、搜索、问答等）
- **求职 Agent**：新的独立 Agent，专注于职位搜索、JD 解析、简历匹配、面试安排等求职相关操作

**动机**：功能职责分离，避免单一 Agent 上下文过长，降低用户理解成本

**验收标准**：
- [ ] 侧边栏菜单"Agent"改为"助手 Agent"
- [ ] 新增"求职 Agent"一级菜单入口
- [ ] 求职 Agent 独立对话界面（独立的 session 和对话历史）
- [ ] 求职 Agent 可调用的工具集与助手 Agent 分离

### 4.2 【P2】用户注册管理（超管功能完善）

**需求描述**：虽然已有注册接口 (`/api/auth/register`) 和用户表，但超管后台缺乏用户管理界面。

**需要实现**：
- 超管后台新增"用户管理"页面
- 展示用户列表（用户名/角色/显示名/状态/注册时间）
- 支持启用/禁用用户
- 支持修改用户角色（user ↔ super_admin）
- 支持重置用户密码
- 新增用户手动创建

**验收标准**：
- [ ] 超管可查看全部用户
- [ ] 超管可启用/禁用用户（禁用后无法登录和管理端无法使用）
- [ ] 超管可修改用户角色
- [ ] 超管可重置任意用户密码
- [ ] 超管可手动创建新用户
- [ ] 普通用户看不到用户管理入口

### 4.3 【P2】用量统计增强（超管视角）

**需求描述**：当前的 `api/usage/all` 接口和 UsagePage 仅展示当前用户的数据。超管需要全局视角。

**需要实现**：
- 超管的用量页展示所有用户的聚合数据
- 按用户维度的用量拆分（对话数/Token数/存储空间）
- 按时间维度的趋势图表（日/周/月）
- 导出用量报表
- 可设置用量告警阈值

### 4.4 【P2】求职和招聘 Agent 自动开关

**需求描述**：求职者和招聘方使用 Agent 应有明确的启停控制，避免无意义的资源消耗。

**需要实现**：
- 配置页面增加 Agent 开关（求职 Agent 开/关、招聘 Agent 开/关）
- 开关关闭后对应端口的 Agent 不再响应新对话
- 开关状态在系统配置中持久化
- 超管可远程控制所有用户的 Agent 开关

### 4.5 【P3】会员体系设计与可视化

**需求描述**：为商业化运营做准备，设计会员等级和对应的功能/用量限制。

**设计方向**：

| 等级 | 知识库容量 | LLM 月额度 | 简历生成 | 个人主页 | 求职 Agent | 价格（设想） |
|------|-----------|-----------|----------|----------|-----------|-------------|
| 免费版 | 50 条 | 5000 tokens | 5 次/月 | 基础主题 | ❌ | ¥0 |
| 专业版 | 200 条 | 50000 tokens | 50 次/月 | 全部主题 | ✅ | ¥29/月 |
| 企业版 | 不限 | 不限 | 不限 | 全部主题 | ✅ + API | ¥99/月 |

**需要实现**：
- [ ] 会员等级定义表
- [ ] 用量限制检查中间件（知识库条目数、Token 消耗等）
- [ ] 超管后台会员管理界面
- [ ] 用户端会员状态展示

### 4.6 【P3】招聘者管理平台

**需求描述**：让招聘方拥有独立的平台，而不仅仅是访客端的问答页面。

**功能设想**：
- 招聘者注册/登录（独立角色 `role=recruiter`）
- 浏览已同意公开的候选人列表
- 对候选人发起提问（AI 自动回复）
- 查看候选人简历和主页
- 管理面试邀约
- 招聘者仪表盘（在招职位数/面试安排/已沟通候选人）

**实现前提**：会员体系上线 → 确定招聘者是付费角色还是免费角色

---

## 5. 非功能需求

### 5.1 性能要求

| 指标 | 目标值 | 说明 |
|------|--------|------|
| AI 问答首字节响应 | ≤ 3s | 包含 RAG 检索 + LLM 流式输出启动 |
| 知识库保存同步 | ≤ 5s | 保存 → MD 同步 → 单分类 FAISS 重建 |
| 简历生成 | ≤ 15s | 融合全部知识库 → LLM 结构化输出 |
| 访客端页面加载 | ≤ 2s | Flask 内联页面不含外部依赖 |
| PDF 导出 | ≤ 10s | Pyppeteer 渲染 + 导出 |
| 并发访客会话 | ≥ 50 | 单容器支持 |
| 向量检索 | ≤ 500ms | FAISS 单用户索引（< 100 条） |

### 5.2 安全要求

| 要求 | 实现方式 | 状态 |
|------|----------|------|
| 密码存储 | bcrypt 哈希 | ✅ 已完成 |
| API 认证 | JWT（HS256） | ✅ 已完成 |
| 口令验证 | 每个用户独立口令 | ✅ 已完成 |
| 数据隔离 | 按 user_id 隔离知识库/向量库 | ✅ 已完成 |
| 提示注入检测 | prompt_injection.py | ✅ 已完成 |
| CORS 限制 | FastAPI CORSMiddleware | ✅ 已完成 |
| SQL 注入防护 | SQLAlchemy ORM（非原生 SQL） | ✅ 已完成 |

### 5.3 可用性要求

- 访客端 7×24 可用（Flask 单进程，可多实例）
- 管理端需登录验证（JWT Token 过期机制）
- 错误反馈友好（中文错误提示）
- 所有列表操作支持加载状态

### 5.4 兼容性要求

| 维度 | 要求 |
|------|------|
| 浏览器 | Chrome 90+, Firefox 90+, Safari 14+, Edge 90+ |
| 访客端 | 不需要 JavaScript 也可浏览基础页面（渐进增强） |
| 移动端 | 访客端适配手机屏幕，管理端 AntDesign 响应式 |
| PDF 导出 | Chromium headless（Docker 内包含） |

---

## 6. 技术方案

### 6.1 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                        外网 (asagent.me)                             │
│                      natapp 隧道 → localhost:51668                   │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────────┐
│                        Docker Compose                                │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │ Admin-Front  │  │  Backend     │  │  Visitor     │               │
│  │ (React+Antd) │  │  (FastAPI)   │  │  (Flask)     │               │
│  │ :51668       │  │  :51666      │  │  :51670      │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                  │                       │
│         │          ┌──────▼────────┐         │                       │
│         │          │   SQLite DB    │         │                       │
│         │          │  (app.db)      │         │                       │
│         │          └──────┬────────┘         │                       │
│         │                 │                  │                       │
│         │          ┌──────▼────────┐         │                       │
│         └──────────►   FAISS      ◄─────────┘                       │
│                    │  Vector Store │                                  │
│                    │ (per-user)     │                                  │
│                    └──────┬────────┘                                  │
│                           │                                           │
│                    ┌──────▼────────┐                                  │
│                    │  LLM API      │                                  │
│                    │ (LongCat)     │                                  │
│                    └───────────────┘                                  │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐                                  │
│  │  SearXNG     │  │  Chromium    │                                  │
│  │  (搜索)      │  │  (PDF)       │                                  │
│  │  :51669      │  │              │                                  │
│  └──────────────┘  └──────────────┘                                  │
└──────────────────────────────────────────────────────────────────────┘
```

### 6.2 技术选型

| 组件 | 技术 | 选型理由 |
|------|------|----------|
| 后端框架 | FastAPI (Python 3.10+) | 异步性能好，原生 SSE 支持，自动 OpenAPI 文档 |
| 访客端 | Flask | 轻量，单页面内联 HTML/CSS/JS |
| 管理端前端 | React 19 + AntDesign v6 + Vite 8 | 企业级 UI 组件库，开发体验好 |
| 数据库 | SQLite + SQLAlchemy | 单用户场景足够，无需数据库服务 |
| 向量检索 | FAISS (faiss-cpu) | 小规模检索性能优秀，无外部依赖 |
| LLM | LongCat-2.0-Preview | 中文能力强，性价比较好 |
| Embedding | BAAI/bge-m3 (SiliconFlow) | 中文 Embedding 效果优秀 |
| 搜索 | Firecrawl + SearXNG + AnySearch | 多源搜索，深度抓取 |
| PDF | Pyppeteer + Chromium | HTML 精确渲染为 PDF |
| Agent 框架 | LangChain (tools) | 工具调用成熟稳定 |
| 容器化 | Docker Compose | 5 个服务统一编排 |
| 外网映射 | natapp | 内网穿透到公网域名 |
| 地图 | 高德地图 API | 通勤计算 + 路线规划 |
| 认证 | JWT (pyjwt) | 无状态 Token 认证 |

### 6.3 数据模型

#### 核心表结构

| 表名 | 说明 | 关键字段 |
|------|------|----------|
| `users` | 用户账号 | id, username, password_hash(bcrypt), role(super_admin/user), is_active |
| `knowledge_base` | 知识库数据 | user_id, category(personal_info/education/…), data(JSON), updated_at |
| `resumes` | 简历记录 | user_id, resume_data(JSON), template, is_active, created_at |
| `sessions` | 访客会话 | session_id, user_id, is_active, expires_at |
| `conversations` | 访客对话 | session_id, role(user/assistant), content, user_id |
| `agent_conversations` | Agent 对话 | session_id, role, content, user_id |
| `agent_tasks` | Agent 异步任务 | session_id, user_id, status, request, response, resume_id |
| `portfolio_configs` | 个人主页配置 | user_id, style, blocks_order(JSON), blocks_hidden(JSON), contact_enabled(JSON) |
| `portfolio_contents` | 个人主页缓存 | user_id, content_json(HTML), built_at |
| `interview_guides` | 面试指南 | user_id, company_name, job_title, interview_time, commute_duration_min, status |
| `crawled_jobs` | 爬取职位 | user_id, platform, title, company, jd_text, match_score, status |
| `prompt_templates` | 提示词模板 | key(agent/resume/visitor), content, version |
| `prompt_versions` | 提示词版本历史 | prompt_key, version, content, change_log |
| `stats` | 事件统计 | event_type, session_id, user_id, created_at |
| `llm_usage` | LLM 用量 | user_id, provider, model, tokens, cost, endpoint(request_type) |
| `user_configs` | 用户配置 | user_id, key, value(JSON) |
| `system_configs` | 系统配置 | key, value(JSON) |
| `applicant_profile` | 申请人面试偏好 | user_id, home_address, travel_mode, interview_duration, workday_hours |

### 6.4 RAG 流程

```
用户提问
    │
    ▼
意图分类 (intent_detector.py)
    ├── 个人信息类 → 定向检索 personal_info 子索引
    ├── 工作经历类 → 定向检索 work_experience 子索引
    ├── 项目/技能类 → 定向检索 projects + skills 子索引
    ├── HR 问答类   → 定向检索 faq 子索引
    └── 其他       → 全部索引 + 附录联合检索
    │
    ▼
FAISS 语义检索 (k=5 per category)
    │
    ▼
重排序 (关键词匹配 + 术语匹配 + n-gram)
    │
    ▼
Prompt 组装 + LLM 生成回答
    │
    ▼
流式输出到访客端
```

### 6.5 数据隔离方案

```
user_data/
└── {uuid}/
    ├── knowledge/            # MD 文件（按分类）
    │   ├── 01_个人信息.md
    │   ├── 02_教育背景.md
    │   ├── 03_工作经历.md
    │   ├── 04_项目经历.md
    │   ├── 05_专业技能.md
    │   ├── 06_HR高频问答.md
    │   └── 07_附录知识库.md
    ├── vector_store/         # FAISS 索引（按分类命名）
    │   ├── personal_info/
    │   ├── education/
    │   ├── ...
    │   └── faiss_index_all/  # 全量索引
    └── resumes/              # 简历输出
```

所有服务层通过 `user_id` 参数路由到正确的目录和数据库记录。

---

## 7. API 接口总览

### 7.1 访客端 API (`/api/*`)

| 方法 | 路径 | 功能 | 认证 |
|------|------|------|------|
| POST | `/api/auth/register` | 用户注册 | 无 |
| POST | `/api/auth/login` | 用户登录 | 无 |
| POST | `/api/verify-password` | 访客口令验证 | 无 |
| POST | `/api/chat` | 访客 AI 问答 | session_id |
| GET | `/api/check-session` | 检查会话有效性 | session_id |
| GET | `/api/profile` | 访客端个人资料 | session_id |
| GET | `/api/welcome-config` | 招呼语配置 | session_id |
| GET | `/api/public-config` | 公开配置 | 无 |
| GET | `/api/resume/preview` | 简历 HTML 预览 | session_id |
| GET | `/api/resume/download` | 简历 PDF 下载 | session_id |
| GET | `/api/resume/status` | 简历开关状态 | session_id |
| GET | `/api/booking-suggestion` | 面试档期建议 | session_id |
| POST | `/api/booking` | 提交面试预约 | session_id |
| GET | `/api/booking/{session_id}` | 查询预约 | session_id |
| POST | `/api/booking-dismiss` | 取消预约提醒 | session_id |
| POST | `/api/export-pdf` | 导出 PDF | session_id |
| GET | `/api/visitor-status` | 访客在线状态 | 无 |

### 7.2 管理端 API (`/admin/*`)

| 方法 | 路径 | 功能 |
|------|------|------|
| POST | `/admin/login` | 管理员登录 |
| POST | `/admin/register` | 管理员注册 |
| GET | `/admin/me` | 当前用户信息 |
| POST | `/admin/change-password` | 修改密码 |
| GET/POST | `/admin/config` | 系统配置读写 |
| POST | `/admin/config/test-llm` | LLM 连接测试 |
| POST | `/admin/config/test-embedding` | Embedding 连接测试 |
| GET | `/admin/knowledge/{category}` | 获取知识分类内容 |
| GET | `/admin/knowledge-structured/{category}` | 获取结构化知识 |
| POST | `/admin/kb/preview` | Agent 知识预览 |
| POST | `/admin/kb/confirm` | Agent 确认修改 |
| POST | `/admin/kb/rebuild-vector` | 重建向量库 |
| POST | `/admin/kb/regenerate-faq` | 再生 FAQ |
| GET/POST | `/admin/appendix/*` | 附录知识库管理 |
| GET | `/admin/resume/templates` | 简历模板列表 |
| POST | `/admin/resume/generate` | 生成简历 |
| POST | `/admin/resume/generate-with-template` | 使用模板生成 |
| GET | `/admin/resume/preview` | 简历 HTML 预览 |
| GET | `/admin/resumes` | 简历列表 |
| GET | `/admin/resumes/{id}` | 简历详情 |
| GET | `/admin/resumes/{id}/download` | 简历下载 |
| GET | `/admin/resumes/{id}/view` | 简历查看 |
| GET | `/admin/portfolio/config` | 个人主页配置 |
| GET | `/admin/portfolio/preview` | 个人主页预览 |
| GET | `/admin/portfolio/styles` | 主题风格列表 |
| GET | `/admin/portfolio/toggle` | 个人主页开关 |
| GET | `/admin/portfolio/build-status` | 缓存状态 |
| POST | `/admin/agent/chat` | Agent 对话 |
| POST | `/admin/agent/chat/stream` | Agent 流式对话 |
| GET | `/admin/agent/history` | Agent 对话历史 |
| POST | `/admin/agent/clear-all` | 清空 Agent 历史 |
| GET | `/admin/jobs` | 职位列表 |
| POST | `/admin/jobs/crawl` | 提交爬取任务 |
| POST | `/admin/jobs/batch-match` | 批量匹配 |
| GET | `/admin/interview-guide/list` | 面试列表 |
| POST | `/admin/interview-guide/create` | 创建面试 |
| POST | `/admin/interview-guide/parse-jd` | 解析 JD |
| POST | `/admin/interview-guide/{id}/generate-report` | 生成面试报告 |
| GET | `/admin/stats` | 统计概览 |
| GET | `/admin/stats/questions` | 高频问题 |
| GET | `/admin/sessions` | 会话列表 |
| GET | `/admin/prompt/{type}` | 获取提示词 |
| GET/PUT | `/api/admin/prompts/{key}` | 提示词管理 |

### 7.3 管理 API (`/api/admin/*`)

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/admin/prompts` | 提示词列表 |
| GET/PUT | `/api/admin/prompts/{key}` | 提示词读写 |
| GET | `/api/auth/users` | 用户列表 |
| PUT | `/api/auth/users/{id}` | 用户管理 |
| GET | `/api/usage/all` | 全局用量统计 |
| GET | `/api/usage/my` | 个人用量统计 |
| GET | `/api/usage/all/daily` | 全局日用量 |
| GET | `/api/usage/my/daily` | 个人日用量 |
| GET | `/api/user-by-username/{username}` | 用户查询 |

---

## 8. 风险分析

### 8.1 技术风险

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| LLM API 服务不可用 | 中 | 高 | 支持多 Provider 切换管理端可配置 |
| FAISS 索引损坏 | 低 | 中 | 支持一键重建全部索引；MD 文件始终作为源 |
| 向量库跨用户污染 | 中 | 高 | ✅ 已修复：改为直接加载磁盘索引而非共享单例 |
| 端口冲突 | 低 | 中 | Docker 映射可配置 |
| 并发会话过多 OOM | 中 | 中 | 最大会话数限制（可配），会话超时自动清理 |
| Pyppeteer/Chromium 版本兼容 | 低 | 中 | Docker 内锁定 Chromium 版本 |
| SQLite 写并发 | 中 | 低 | 单用户场景，写操作不频繁 |

### 8.2 业务风险

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| AI 回答内容不准确 | 高 | 中 | RAG + 重排序 + 意图定向检索降低幻觉率 |
| 用户数据隐私 | 中 | 高 | 按用户隔离，口令保护访客端 |
| 爬虫被目标网站封禁 | 中 | 中 | Firecrawl 官方接口 + 慢速爬取 |
| LLM API 成本超支 | 中 | 高 | 用量统计监控 + 月度预算配置 |

---

## 9. 里程碑规划

| 阶段 | 时间 | 目标 |
|------|------|------|
| **迭代一 (已完成)** | 2026 Q1-Q2 | 知识库管理、简历生成、个人主页、访客问答、Agent 对话、系统配置 |
| **迭代二 (当前)** | 2026 Q2-Q3 | Agent 菜单拆分为求职 Agent、超管用户管理、用量统计增强、Agent 开关、面试报告 |
| **迭代三 (规划中)** | 2026 Q3-Q4 | 会员体系设计与实现、用量限制中间件 |
| **迭代四** | 2026 Q4+ | 招聘者管理平台、商业化运营 |

### 当前迭代 (迭代二) 交付节点

| 需求 | 优先级 | 预计交付 |
|------|--------|----------|
| Agent 菜单重构：增加"求职 Agent"入口 | P1 | 2026-06 |
| 个人信息增加"个人网站"字段 | P2 | ✅ 已交付 |
| 超管用户注册管理功能 | P2 | 2026-06 |
| 超管用量数据统计与监控 | P2 | 2026-07 |
| 求职和招聘 Agent 自动开启开关 | P2 | 2026-07 |
| 会员体系指标设计与可视化 | P3 | 2026-08 |
| 招聘者管理平台 | P3 | 2026-09+ |

---

## 10. 附录

### 10.1 环境变量参考

```ini
# 必需
LONGCAT_API_KEY=<longcat-api-key>
LONGCAT_API_BASE=https://api.longcat.chat/openai/v1
LONGCAT_MODEL=LongCat-2.0-Preview
SILICONFLOW_API_KEY=<siliconflow-api-key>
SILICONFLOW_API_BASE=https://api.siliconflow.cn/v1
SILICONFLOW_EMBEDDING_MODEL=BAAI/bge-m3

# 服务端口
BACKEND_PORT=51666
VISITOR_PORT=51670
ADMIN_PORT=51668

# 可选
FIRECRAWL_API_KEY=<firecrawl-key>
FIRECRAWL_DAILY_BUDGET=20
NATAUTH_TOKEN=<natapp-token>
```

### 10.2 Docker 部署参考

```yaml
# docker-compose.yml 核心服务
# backend: FastAPI on :51666
# admin-front: Nginx + React on :51668
# visitor: Flask on :51670
# searxng: Search engine on :51669
# natapp: Tunnel asagent.me → :51668
```

### 10.3 相关文档

- [AGENTS.md](./AGENTS.md) — 项目知识库与操作手册
- [README.md](./README.md) — 快速开始与架构说明
