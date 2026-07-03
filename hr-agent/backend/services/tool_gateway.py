from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable
from services.tool_result import ToolResult, ok, err
from services.tool_meta import ToolMeta, TOOL_METADATA
import asyncio
import contextvars
import time


# ============================================================
# Types
# ============================================================


@dataclass
class ToolEntry:
    name: str
    fn: Callable[..., Any]  # the original @tool decorated function
    description: str = ""
    category: str = "misc"  # resume/knowledge/job/search/file/misc
    sensitive: bool = False
    timeout: int = 30

    def get_meta(self) -> ToolMeta | None:
        return TOOL_METADATA.get(self.name)


MiddlewareFn = Callable[[str, dict, dict], Awaitable[ToolResult | None]]


# ============================================================
# Middlewares
# ============================================================


class AuthMiddleware:
    """Check user authentication for tool calls.

    In the multi-tenant architecture, each user's agent operates on their own
    data (enforced by get_current_user_id() ContextVar). This middleware only
    verifies that the caller is an authenticated user, without restricting by
    role — all agent tools are user-facing, not admin-only.
    """

    async def process(self, name: str, params: dict, ctx: dict) -> ToolResult | None:
        user_id = ctx.get("user_id", "")
        if not user_id:
            return err(code=403, error="未认证用户无法调用工具")
        return None  # pass through


class ValidateMiddleware:
    """Validate tool parameters against ToolMeta definitions."""

    async def process(self, name: str, params: dict, ctx: dict) -> ToolResult | None:
        meta = TOOL_METADATA.get(name)
        if meta is None:
            return None  # no schema defined, pass through
        for p in meta.parameters:
            if p.required and (p.name not in params or not params.get(p.name)):
                return err(code=400, error=f"缺少必填参数 '{p.name}'")
        return None


class AuditMiddleware:
    """Log every tool call with params, result code, and duration."""

    def __init__(self, logger: Callable[[str], None] = print):
        self._logger = logger

    async def process(self, name: str, params: dict, ctx: dict) -> ToolResult | None:
        return None  # never blocks

    def on_result(self, name: str, params: dict, ctx: dict, result: ToolResult, elapsed: float):
        uid = ctx.get("user_id", "")
        role = ctx.get("role", "")
        self._logger(
            f"[gateway] tool={name} user={uid} role={role} code={result.code} "
            f"elapsed={elapsed:.2f}s"
        )


# ============================================================
# Gateway
# ============================================================


class ToolGateway:
    """Unified tool call entry point with middleware chain."""

    def __init__(self):
        self._entries: dict[str, ToolEntry] = {}
        self._middlewares: list[MiddlewareFn] = []
        self._auth = AuthMiddleware()
        self._validate = ValidateMiddleware()
        self._audit = AuditMiddleware()

    def register(self, entry: ToolEntry):
        self._entries[entry.name] = entry

    def set_sensitive_tools(self, names: set[str]):
        self._sensitive_tools = names

    def add_middleware(self, mw: MiddlewareFn):
        self._middlewares.append(mw)

    async def call(self, name: str, params: dict, ctx: dict | None = None) -> ToolResult:
        ctx = ctx or {}
        ctx.setdefault("sensitive_tools", getattr(self, "_sensitive_tools", set()))

        # Built-in auth middleware (always runs first)
        auth_block = await self._auth.process(name, params, ctx)
        if auth_block is not None:
            return auth_block

        # Built-in validate middleware (runs before custom chain)
        validate_block = await self._validate.process(name, params, ctx)
        if validate_block is not None:
            return validate_block

        # Custom middleware chain
        for mw in self._middlewares:
            try:
                block = await mw(name, params, ctx)
                if block is not None:
                    return block
            except Exception as e:
                return err(code=500, error=f"middleware error: {e}")

        entry = self._entries.get(name)
        if not entry:
            self._audit.on_result(name, params, ctx, err(code=404, error=f"tool '{name}' not found"), 0)
            return err(code=404, error=f"工具 '{name}' 不存在")

        start = time.monotonic()
        try:
            raw = await _run_sync(entry.fn, params, ctx)
            elapsed = time.monotonic() - start
            result = _parse_raw(raw)
            self._audit.on_result(name, params, ctx, result, elapsed)
            return result
        except asyncio.TimeoutError:
            elapsed = time.monotonic() - start
            result = err(code=408, error=f"工具 '{name}' 执行超时 ({entry.timeout}s)")
            self._audit.on_result(name, params, ctx, result, elapsed)
            return result
        except Exception as e:
            elapsed = time.monotonic() - start
            result = err(code=500, error=f"工具 '{name}' 执行异常: {e}")
            self._audit.on_result(name, params, ctx, result, elapsed)
            return result

    def list_tools(self) -> list[ToolEntry]:
        return list(self._entries.values())

    def get_tool_meta(self, name: str) -> dict | None:
        entry = self._entries.get(name)
        if not entry:
            return None
        meta = entry.get_meta()
        if meta:
            return meta.to_dict()
        return {
            "name": entry.name,
            "display_name": entry.name,
            "description": entry.description,
            "category": entry.category,
            "parameters": [],
            "sensitive": entry.sensitive,
            "timeout": entry.timeout,
            "example_prompt": "",
        }

    def list_tools_with_meta(self) -> list[dict]:
        result = []
        for entry in self._entries.values():
            meta = entry.get_meta()
            if meta:
                result.append(meta.to_dict())
            else:
                result.append({
                    "name": entry.name,
                    "display_name": entry.name,
                    "description": entry.description,
                    "category": entry.category,
                    "parameters": [],
                    "sensitive": entry.sensitive,
                    "timeout": entry.timeout,
                    "example_prompt": "",
                })
        return result

    def audit_tool_call(self, name: str, params: dict, ctx: dict, code: int = 0):
        """Public convenience: log a tool call through the audit middleware.

        Useful when tools execute outside gateway.call() (e.g. via LangChain's
        ToolNode), so the gateway can still record an audit trail.
        """
        start = time.monotonic()
        result = ok(data="") if code == 0 else err(code=code)
        elapsed = time.monotonic() - start
        self._audit.on_result(name, params, ctx, result, elapsed)

    def call_sync(self, name: str, params: dict, ctx: dict | None = None) -> ToolResult:
        """Synchronous version of call() for use in non-async contexts."""
        return _run_async(self.call(name, params, ctx or {}))

    def call_sync_to_text(self, name: str, params: dict, ctx: dict | None = None) -> str:
        """Synchronous gateway call returning the legacy JSON string format."""
        result = self.call_sync(name, params, ctx)
        return result.to_llm_text()


# ============================================================
# Helpers
# ============================================================


async def _run_sync(fn: Callable, params: dict, ctx: dict | None = None) -> str:
    """Run a synchronous tool function in a thread, respecting params.

    Handles both raw functions and LangChain StructuredTool (@tool decorated).
    Also propagates ctx['user_id'] to the thread-local ContextVar so tools
    calling get_current_user_id() get the correct value.
    """
    import inspect
    # LangChain StructuredTool has a .func attribute holding the original function
    if hasattr(fn, "func") and callable(getattr(fn, "func", None)):
        actual_fn = fn.func
    else:
        actual_fn = fn
    sig = inspect.signature(actual_fn)
    kwargs = {}
    for p in sig.parameters.values():
        if p.name in params:
            kwargs[p.name] = params[p.name]
        elif p.default is inspect.Parameter.empty:
            kwargs[p.name] = ""

    uid = (ctx or {}).get("user_id", "")

    def _run():
        if uid:
            try:
                from services.agent_service import set_current_user_id
                set_current_user_id(uid)
            except ImportError:
                pass
        return actual_fn(**kwargs)

    _ctx = contextvars.copy_context()
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _ctx.run, _run)


def _parse_raw(raw: str) -> ToolResult:
    """Parse the legacy {ok, data/error} JSON string back to ToolResult."""
    import json
    try:
        d = json.loads(raw)
        if d.get("ok"):
            return ok(data=d.get("data", ""), extra=d.get("extra"))
        return err(error=d.get("error", "unknown error"))
    except (json.JSONDecodeError, TypeError):
        return ok(data=raw)


def _run_async(coro) -> ToolResult:
    """Run an async coroutine synchronously, creating a new event loop if needed."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop is not None and loop.is_running():
        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(coro)
        finally:
            new_loop.close()
    return asyncio.run(coro)
