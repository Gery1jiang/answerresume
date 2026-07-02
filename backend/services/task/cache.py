import json
import time
from collections import OrderedDict
from typing import Any


class TaskCache:
    def __init__(self, max_templates: int = 100, action_ttl: int = 300):
        self._template_cache: OrderedDict = OrderedDict()
        self._max_templates = max_templates
        self._action_cache: dict[str, tuple[float, Any]] = {}
        self._action_ttl = action_ttl

    def get_template(self, key: str) -> Any | None:
        return self._template_cache.get(key)

    def set_template(self, key: str, value: Any):
        self._template_cache[key] = value
        if len(self._template_cache) > self._max_templates:
            self._template_cache.popitem(last=False)

    def get_action(self, tool: str, params: dict) -> Any | None:
        key = f"{tool}:{json.dumps(params, sort_keys=True, ensure_ascii=False)}"
        entry = self._action_cache.get(key)
        if not entry:
            return None
        ts, val = entry
        if time.time() - ts > self._action_ttl:
            del self._action_cache[key]
            return None
        return val

    def set_action(self, tool: str, params: dict, result: Any):
        key = f"{tool}:{json.dumps(params, sort_keys=True, ensure_ascii=False)}"
        self._action_cache[key] = (time.time(), result)

    def invalidate_action(self, tool: str | None = None):
        if tool is None:
            self._action_cache.clear()
        else:
            self._action_cache = {
                k: v for k, v in self._action_cache.items()
                if not k.startswith(f"{tool}:")
            }


task_cache = TaskCache()
