"""Golden dataset for agent regression testing."""

GOLDEN_CASES = [
    # ── 简历生成 ──
    {
        "id": "resume_01",
        "input": "帮我生成一份前端开发的简历",
        "assert_tools": ["generate_resume_tool"],
        "assert_not_tools": ["web_search_tool", "query_sessions_tool"],
        "description": "基本简历生成",
    },
    {
        "id": "resume_02",
        "input": "做一份简历，岗位是产品经理",
        "assert_tools": ["generate_resume_tool"],
        "assert_not_tools": ["parse_file_tool"],
        "description": "指定岗位名称",
    },
    # ── 文件解析（不应误触简历生成） ──
    {
        "id": "parse_01",
        "input": "解析图片内容，看看这张图里写的什么",
        "assert_tools": ["parse_file_tool"],
        "assert_not_tools": ["generate_resume_tool"],
        "description": "纯文件解析，不应触发简历生成",
    },
    {
        "id": "parse_02",
        "input": "帮我读一下这个文件，里面是什么内容",
        "assert_tools": ["parse_file_tool"],
        "assert_not_tools": ["generate_resume_tool", "create_interview_record_tool"],
        "description": "纯文件读取",
    },
    # ── 在线搜索 ──
    {
        "id": "search_01",
        "input": "搜索一下最近AI行业的新闻",
        "assert_tools": ["web_search_tool"],
        "description": "在线搜索最新信息",
    },
    # ── 知识库修改 ──
    {
        "id": "kb_01",
        "input": "修改知识库，把我的名字改成张三",
        "assert_tools": ["knowledge_preview"],
        "description": "知识库修改触发预览",
    },
    # ── 统计查询 ──
    {
        "id": "stats_01",
        "input": "查一下最近7天的访问统计",
        "assert_tools": ["query_sessions_tool"],
        "description": "访客统计查询",
    },
]
