import json
import pytest
from services.tool_result import ToolResult, ok, err


class TestToolResult:
    def test_ok(self):
        r = ok(data="hello")
        assert r.is_ok
        assert not r.is_error
        assert r.code == 0
        assert r.data == "hello"

    def test_err(self):
        r = err(code=400, error="bad param")
        assert r.is_error
        assert not r.is_ok
        assert r.code == 400
        assert r.error == "bad param"

    def test_to_llm_text_ok(self):
        r = ok(data={"name": "test"})
        parsed = json.loads(r.to_llm_text())
        assert parsed["ok"] is True
        assert parsed["data"]["name"] == "test"

    def test_to_llm_text_err(self):
        r = err(code=404, error="not found")
        parsed = json.loads(r.to_llm_text())
        assert parsed["ok"] is False
        assert parsed["error"] == "not found"

    def test_to_dict(self):
        r = ok(data=[1, 2, 3], extra={"source": "test"})
        d = r.to_dict()
        assert d["code"] == 0
        assert d["data"] == [1, 2, 3]
        assert d["extra"]["source"] == "test"

    def test_default_code(self):
        r = err(error="fail")
        assert r.code == 500  # default

    def test_extra_default_empty(self):
        r = ok(data="x")
        assert r.extra == {}
