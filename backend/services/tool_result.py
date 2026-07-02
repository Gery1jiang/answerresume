from dataclasses import dataclass, field
from typing import Any
import json


@dataclass
class ToolResult:
    code: int
    data: Any = None
    error: str = ""
    extra: dict = field(default_factory=dict)

    @property
    def is_ok(self) -> bool:
        return self.code == 0

    @property
    def is_error(self) -> bool:
        return self.code != 0

    def to_llm_text(self) -> str:
        """Format as legacy {ok, data/error} JSON string for LLM consumption."""
        if self.is_ok:
            d = {"ok": True, "data": self.data}
            if self.extra:
                d["extra"] = self.extra
            return json.dumps(d, ensure_ascii=False)
        return json.dumps({"ok": False, "error": self.error}, ensure_ascii=False)

    def to_dict(self) -> dict:
        d = {"code": self.code}
        if self.data is not None:
            d["data"] = self.data
        if self.error:
            d["error"] = self.error
        if self.extra:
            d["extra"] = self.extra
        return d


def ok(data: Any = None, extra: dict | None = None) -> ToolResult:
    return ToolResult(code=0, data=data, extra=extra or {})


def err(code: int = 500, error: str = "", extra: dict | None = None) -> ToolResult:
    return ToolResult(code=code, error=error, extra=extra or {})


# Map code to human-readable label
CODE_LABELS = {
    0: "成功",
    400: "参数错误",
    403: "无权限",
    404: "资源不存在",
    408: "超时",
    429: "请求过多",
    500: "服务异常",
}
