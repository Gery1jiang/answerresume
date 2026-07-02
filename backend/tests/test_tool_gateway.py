import pytest
from services.tool_gateway import ToolGateway, ToolEntry, AuthMiddleware, AuditMiddleware
from services.tool_result import ToolResult, ok, err


def _fake_tool(text: str = "") -> str:
    return ok(data=f"processed: {text}").to_llm_text()


def _failing_tool(text: str = "") -> str:
    return err(code=500, error="oops").to_llm_text()


class TestToolGateway:
    CTX = {"user_id": "test"}

    def test_register_and_list(self):
        gw = ToolGateway()
        gw.register(ToolEntry(name="test_tool", fn=_fake_tool, category="misc"))
        tools = gw.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "test_tool"
        assert tools[0].category == "misc"

    @pytest.mark.asyncio
    async def test_call_unknown_tool_returns_404(self):
        gw = ToolGateway()
        result = await gw.call("nonexistent", {}, ctx=self.CTX)
        assert result.code == 404
        assert "不存在" in result.error

    @pytest.mark.asyncio
    async def test_call_success(self):
        gw = ToolGateway()
        gw.register(ToolEntry(name="greet", fn=_fake_tool))
        result = await gw.call("greet", {"text": "hello"}, ctx=self.CTX)
        assert result.code == 0
        assert "hello" in str(result.data)

    @pytest.mark.asyncio
    async def test_call_with_failing_tool(self):
        gw = ToolGateway()
        gw.register(ToolEntry(name="fail", fn=_failing_tool))
        result = await gw.call("fail", {}, ctx=self.CTX)
        assert result.code == 500

    @pytest.mark.asyncio
    async def test_auth_blocks_missing_user_id(self):
        gw = ToolGateway()
        gw.register(ToolEntry(name="greet", fn=_fake_tool))
        result = await gw.call("greet", {"text": "hi"}, ctx={})
        assert result.code == 403
        assert "未认证" in result.error

    @pytest.mark.asyncio
    async def test_auth_passes_with_user_id(self):
        gw = ToolGateway()
        gw.register(ToolEntry(name="greet", fn=_fake_tool))
        result = await gw.call("greet", {"text": "hi"}, ctx={"user_id": "u1"})
        assert result.code == 0

    def test_audit_tool_call_public_method(self):
        gw = ToolGateway()
        gw.register(ToolEntry(name="greet", fn=_fake_tool))
        gw.audit_tool_call("greet", {"text": "hi"}, {"user_id": "u1"})

    def test_audit_tool_call_unknown_tool(self):
        gw = ToolGateway()
        gw.audit_tool_call("nonexistent", {}, {"user_id": "u1"})

    def test_register_multiple_categories(self):
        gw = ToolGateway()
        gw.register(ToolEntry(name="a", fn=_fake_tool, category="resume", sensitive=True))
        gw.register(ToolEntry(name="b", fn=_fake_tool, category="knowledge"))
        tools = gw.list_tools()
        assert len(tools) == 2
        cats = {t.name: t.category for t in tools}
        assert cats["a"] == "resume"
        assert cats["b"] == "knowledge"
        assert next(t for t in tools if t.name == "a").sensitive is True

    @pytest.mark.asyncio
    async def test_auth_then_audit_middleware_chain(self):
        gw = ToolGateway()
        gw.register(ToolEntry(name="greet", fn=_fake_tool))
        result = await gw.call("greet", {"text": "chain"}, ctx=self.CTX)
        assert result.code == 0
