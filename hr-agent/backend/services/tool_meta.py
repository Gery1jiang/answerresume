from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolParam:
    name: str
    type: str
    description: str
    required: bool = False


@dataclass
class ToolMeta:
    name: str
    display_name: str
    description: str
    category: str
    parameters: list[ToolParam] = field(default_factory=list)
    sensitive: bool = False
    timeout: int = 30
    example_prompt: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "category": self.category,
            "parameters": [{"name": p.name, "type": p.type, "description": p.description, "required": p.required} for p in self.parameters],
            "sensitive": self.sensitive,
            "timeout": self.timeout,
            "example_prompt": self.example_prompt,
        }


# ── 11 tool metadata definitions ──────────────────────

TOOL_METADATA: dict[str, ToolMeta] = {}

def _reg(meta: ToolMeta):
    TOOL_METADATA[meta.name] = meta


_reg(ToolMeta(
    name="web_search_tool",
    display_name="在线搜索",
    description="搜索实时互联网信息。当用户询问公司信息、人物背景、实时资讯、行业动态时优先调用",
    category="search",
    sensitive=False,
    parameters=[
        ToolParam("query", "string", "搜索关键词", required=True),
        ToolParam("max_results", "integer", "返回结果数量（默认5）"),
    ],
    example_prompt="帮我搜索一下字节跳动的面试流程",
))

_reg(ToolMeta(
    name="generate_resume_tool",
    display_name="生成简历",
    description="根据目标岗位和岗位描述生成简历PDF。一次调用即可生成完整简历，无需多次调用",
    category="resume",
    sensitive=True,
    parameters=[
        ToolParam("target_job", "string", "目标岗位名称（必填）。用户上传了图片/文件时，先解析再从内容提取核心岗位名；无法确定才追问", required=True),
        ToolParam("jd", "string", "岗位描述/JD文本（可选）"),
        ToolParam("raw_content", "string", "上传的简历内容原文（可选，提供后不使用知识库）"),
    ],
    example_prompt="帮我生成一份前端开发的简历",
))

_reg(ToolMeta(
    name="query_sessions_tool",
    display_name="查询会话统计",
    description="查询最近N天的访客会话统计数据，包括访问量、对话次数、简历下载次数",
    category="misc",
    parameters=[
        ToolParam("days", "integer", "查询最近的天数（默认7）"),
    ],
    example_prompt="最近7天的访客统计是多少",
))

_reg(ToolMeta(
    name="knowledge_preview",
    display_name="知识库预览",
    description="知识库内容修改预览。管理员提出修改知识库时，调用此工具预览变更效果",
    category="knowledge",
    sensitive=False,
    parameters=[
        ToolParam("text", "string", "要修改的内容原文（不要总结或改写）", required=True),
    ],
    example_prompt="把工作经历中的公司名改成字节跳动",
))

_reg(ToolMeta(
    name="knowledge_confirm",
    display_name="知识库确认",
    description="确认执行知识库修改。预览后管理员确认时调用",
    category="knowledge",
    sensitive=True,
    parameters=[
        ToolParam("preview_id", "string", "预览时返回的预览ID", required=True),
    ],
    example_prompt="确认修改",
))

_reg(ToolMeta(
    name="knowledge_rebuild_vector",
    display_name="重建向量库",
    description="重建知识库向量索引。管理员说'重建向量库'、'刷新知识库'时调用",
    category="knowledge",
    sensitive=False,
    example_prompt="重建向量库",
))

_reg(ToolMeta(
    name="generate_interview_report_tool",
    display_name="生成面试报告",
    description="生成面试报告/面试宝典PDF。自动使用最新面试记录若未指定公司",
    category="resume",
    sensitive=True,
    parameters=[
        ToolParam("company", "string", "公司名称（可选，不传时自动使用最新面试记录）", required=False),
        ToolParam("job_title", "string", "岗位名称（可选）"),
    ],
    example_prompt="生成字节跳动的面试报告",
))

_reg(ToolMeta(
    name="parse_file_tool",
    display_name="文件解析",
    description="解析上传文件中的文字内容。支持图片（OCR）、PDF、DOCX、MD、PPTX、XLSX、HTML等格式",
    category="file",
    parameters=[
        ToolParam("filename", "string", "文件名，从[文件: xxx.ext]标记中提取", required=True),
    ],
    example_prompt="解析这个PDF文件",
))

_reg(ToolMeta(
    name="kimi_crawl_tool",
    display_name="Kimi 岗位爬取",
    description="通过 Kimi WebBridge 在真实浏览器中爬取招聘网站的岗位信息，结果保存到岗位雷达。默认不自动匹配，可设置 auto_match=true 后台匹配",
    category="job",
    parameters=[
        ToolParam("keywords", "string", "搜索关键词，如'Python后端开发'", required=True),
        ToolParam("city", "string", "城市，如'北京'、'上海'、'杭州'，默认杭州"),
        ToolParam("platform", "string", "平台：51job/boss/zhaopin，默认51job"),
        ToolParam("max_count", "integer", "抓取数量，默认5，最多10。用户说「一个」则传1，「两个」则传2，以此类推"),
        ToolParam("auto_match", "boolean", "是否自动匹配经历评分，默认false"),
    ],
    example_prompt="帮我爬取51job上的AI产品经理岗位",
))

_reg(ToolMeta(
    name="match_jobs_tool",
    display_name="岗位匹配评分",
    description="对已抓取的招聘岗位进行经历匹配评分。不传job_ids时自动匹配最新未评分岗位",
    category="job",
    parameters=[
        ToolParam("job_ids", "string", "岗位ID列表，逗号分隔如'1,2,3'。不传时自动匹配最新未评分岗位", required=False),
        ToolParam("status_filter", "string", "要匹配的岗位状态：new / matching，默认new"),
    ],
    example_prompt="匹配所有未评分的岗位",
))

_reg(ToolMeta(
    name="create_interview_record_tool",
    display_name="创建面试记录",
    description="创建面试记录（面试宝典）。根据文件解析结果或管理员提供的信息新增面试记录",
    category="misc",
    sensitive=False,
    parameters=[
        ToolParam("company_name", "string", "公司名称（必填）", required=True),
        ToolParam("job_title", "string", "岗位名称（必填）", required=True),
        ToolParam("interview_time", "string", "面试时间，格式如'2025-06-15 14:00'"),
        ToolParam("interview_address", "string", "面试地址"),
        ToolParam("address_type", "string", "地址类型：online或offline，默认offline"),
        ToolParam("video_link", "string", "视频面试链接"),
        ToolParam("interview_round", "string", "面试阶段：一面/二面/技术面/HR面"),
        ToolParam("hr_name", "string", "联系人姓名"),
        ToolParam("hr_phone", "string", "联系人电话"),
        ToolParam("salary", "string", "薪资范围，如'11-15K'"),
        ToolParam("company_description", "string", "公司简介/公司信息描述"),
        ToolParam("jd_text", "string", "岗位描述文本"),
    ],
    example_prompt="创建一条字节跳动的面试记录",
))

_reg(ToolMeta(
    name="update_interview_record_tool",
    display_name="修改面试记录",
    description="修改已有的面试记录（面试宝典）。先用query_system_data_tool查到记录ID，再调用此工具修改。只传需要修改的字段，未传的保持不变",
    category="misc",
    sensitive=False,
    parameters=[
        ToolParam("record_id", "integer", "要修改的面试记录ID（必填），从 query_system_data_tool 查询结果中获取", required=True),
        ToolParam("company_name", "string", "公司名称"),
        ToolParam("job_title", "string", "岗位名称"),
        ToolParam("interview_time", "string", "面试时间，格式如'2025-06-15 14:00'"),
        ToolParam("interview_address", "string", "面试地址"),
        ToolParam("address_type", "string", "地址类型：online或offline"),
        ToolParam("video_link", "string", "视频面试链接"),
        ToolParam("interview_round", "string", "面试阶段：一面/二面/技术面/HR面"),
        ToolParam("hr_name", "string", "联系人姓名"),
        ToolParam("hr_phone", "string", "联系人电话"),
        ToolParam("salary", "string", "薪资范围，如'11-15K'"),
        ToolParam("company_description", "string", "公司简介"),
        ToolParam("jd_text", "string", "岗位描述文本"),
    ],
    example_prompt="把面试时间改成明天下午两点",
))

_reg(ToolMeta(
    name="query_system_data_tool",
    display_name="查询系统数据",
    description="查询面试记录等系统数据，主要用于修改面试记录前查询记录ID",
    category="misc",
    sensitive=False,
    parameters=[
        ToolParam("entity_type", "string", "查询类型：interview_guide（面试记录）", required=True),
        ToolParam("keyword", "string", "搜索关键字，可选"),
    ],
    example_prompt="查一下面试记录",
))
