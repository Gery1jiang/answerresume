from services.agent_prompt_builder import AgentPromptBuilder, DEFAULTS, KEY_ROLE, KEY_TOOLS, KEY_RULES_COMMON, KEY_OUTPUT_FORMAT


class TestAgentPromptBuilder:
    def test_build_includes_core_sections(self):
        prompt = AgentPromptBuilder.build()
        assert DEFAULTS[KEY_ROLE] in prompt
        assert DEFAULTS[KEY_TOOLS] in prompt
        assert DEFAULTS[KEY_RULES_COMMON] in prompt
        assert DEFAULTS[KEY_OUTPUT_FORMAT] in prompt

    def test_build_with_resume_intent(self):
        prompt = AgentPromptBuilder.build(user_input="帮我生成简历")
        assert DEFAULTS[KEY_ROLE] in prompt
        assert "生成简历" in prompt
        assert "帮我写简历" in prompt  # from intent module

    def test_build_with_parse_intent(self):
        prompt = AgentPromptBuilder.build(user_input="解析这张图片")
        assert "OCR" in prompt

    def test_build_with_interview_intent(self):
        prompt = AgentPromptBuilder.build(user_input="创建面试记录")
        assert "创建面试" in prompt

    def test_build_with_file_upload(self):
        prompt = AgentPromptBuilder.build(user_input="[文件: jd.png] 解析它")
        assert "[文件:" in prompt
        assert "parse_file_tool" in prompt

    def test_build_empty_returns_all_sections(self):
        prompt = AgentPromptBuilder.build(user_input="")
        # Should include role, tools, rules, output
        assert DEFAULTS[KEY_ROLE] in prompt
        assert DEFAULTS[KEY_TOOLS] in prompt
        # Should NOT include intent-specific sections
        assert "帮我写简历" not in prompt

    def test_build_fallback_when_db_empty(self):
        """Without DB seeded, should use code DEFAULTS."""
        prompt = AgentPromptBuilder.build()
        assert prompt  # not empty
        assert "AS Agent管理助手" in prompt
