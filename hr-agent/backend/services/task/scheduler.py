import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

from services.task.models import Action, TaskDAG, TaskRoot
from services.task.validator import validate_action
from services.task.cache import task_cache


def topological_sort(dag: TaskDAG) -> list[list[str]]:
    all_ids: list[str] = []
    action_deps: dict[str, list[str]] = {}

    for sub_id, subtask in dag.nodes.items():
        for action in subtask.actions:
            all_ids.append(action.action_id)
            action_deps[action.action_id] = list(action.depends_on)

    edges: list[tuple[str, str]] = []
    for sub_id, subtask in dag.nodes.items():
        for action in subtask.actions:
            for dep in action.depends_on:
                edges.append((dep, action.action_id))

    in_degree: dict[str, int] = {}
    for aid in all_ids:
        in_degree[aid] = 0
    for dep, action_id in edges:
        in_degree[action_id] = in_degree.get(action_id, 0) + 1

    remaining = set(all_ids)
    layers: list[list[str]] = []

    while remaining:
        layer = [aid for aid in remaining if in_degree.get(aid, 0) == 0]
        if not layer:
            cycle = remaining
            raise ValueError(f"检测到循环依赖，剩余节点: {cycle}")
        layers.append(layer)
        for aid in layer:
            remaining.remove(aid)
            for sub_id, subtask in dag.nodes.items():
                for action in subtask.actions:
                    if aid in action.depends_on:
                        in_degree[action.action_id] -= 1

    return layers


def _resolve_params(params: dict, results: dict[str, Any]) -> dict:
    resolved = {}
    for k, v in params.items():
        if isinstance(v, str) and v.startswith("$"):
            ref = v[1:]
            if "." in ref:
                key, field = ref.split(".", 1)
                parent = results.get(key, {})
                if isinstance(parent, dict):
                    resolved[k] = parent.get(field)
                else:
                    resolved[k] = getattr(parent, field, v)
            else:
                resolved[k] = results.get(ref, v)
        else:
            resolved[k] = v

    refs = params.pop("_job_id_refs", None)
    if refs:
        job_ids = []
        for ref in refs:
            ref_key = ref.lstrip("$")
            if "." in ref_key:
                key, field = ref_key.split(".", 1)
            else:
                key, field = ref_key, "id"
            val = results.get(key, {})
            if isinstance(val, dict):
                jid = val.get(field)
            else:
                jid = getattr(val, field, None)
            if jid is not None:
                job_ids.append(str(jid))
        if job_ids:
            resolved["job_ids"] = ",".join(job_ids)

    return resolved


def _find_action(root: TaskRoot, action_id: str) -> Action | None:
    for subtask in root.dag.nodes.values():
        for a in subtask.actions:
            if a.action_id == action_id:
                return a
    return None


class DAGScheduler:
    def __init__(self, gateway, live_event_pusher=None, event_saver=None, ctx: dict | None = None):
        self._gateway = gateway
        self._push = live_event_pusher
        self._save_event = event_saver
        self._ctx = ctx or {}

    def execute(self, root: TaskRoot) -> dict[str, Any]:
        layers = topological_sort(root.dag)
        all_results: dict[str, Any] = {}

        self._emit("dag_plan", {
            "task_id": root.task_id,
            "goal": root.goal,
            "layers": [[str(aid) for aid in layer] for layer in layers],
        })

        for layer_idx, layer in enumerate(layers):
            with ThreadPoolExecutor(max_workers=len(layer)) as pool:
                future_map = {}
                for action_id in layer:
                    action = _find_action(root, action_id)
                    if not action:
                        continue
                    params = _resolve_params(action.input_params, all_results)

                    cached = task_cache.get_action(action.tool, params)
                    if cached is not None:
                        all_results[action.output_key] = cached
                        self._emit("dag_progress", {
                            "action_id": action_id,
                            "tool": action.tool,
                            "status": "cached",
                        })
                        continue

                    future = pool.submit(
                        self._execute_single, action, params, layer_idx
                    )
                    future_map[future] = action

                for future in as_completed(future_map):
                    action = future_map[future]
                    try:
                        result = future.result()
                        all_results[action.output_key] = result
                    except Exception as e:
                        self._emit("dag_progress", {
                            "action_id": action.action_id,
                            "status": "failed",
                            "error": str(e),
                        })
                        if root.error_strategy == "abort":
                            raise
                        all_results[action.output_key] = {"error": str(e)}

        self._emit("dag_progress", {
            "task_id": root.task_id,
            "status": "completed",
        })

        return all_results

    def _execute_single(self, action: Action, params: dict, layer_idx: int) -> Any:
        self._emit("dag_progress", {
            "action_id": action.action_id,
            "tool": action.tool,
            "status": "running",
            "layer": layer_idx,
        })
        self._emit("tool_call", {
            "tool": action.tool,
            "args": params,
        })

        v_errors = validate_action(action.tool, params)
        if v_errors:
            raise ValueError(f"参数不完整，缺少: {'、'.join(v_errors)}")

        raw = self._gateway.call_sync_to_text(action.tool, params, self._ctx)

        self._emit("tool_result", {
            "tool": action.tool,
            "result_preview": raw[:200] if raw else "",
        })

        parsed = _try_parse_json(raw)
        task_cache.set_action(action.tool, params, parsed)
        return parsed

    def _emit(self, event_type: str, data: dict):
        if self._push:
            self._push({"type": event_type, "data": data})


def _try_parse_json(raw: str) -> Any:
    if not raw:
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


def aggregate_results(results: dict[str, Any]) -> str:
    lines = []
    for key, val in results.items():
        if isinstance(val, dict) and "error" in val:
            lines.append(f"【{key}】执行失败: {val['error']}")
        elif isinstance(val, dict) and val.get("ok"):
            data = val.get("data", "")
            lines.append(f"【{key}】成功: {data}")
        elif isinstance(val, dict) and not val.get("ok"):
            err = val.get("error", str(val))
            lines.append(f"【{key}】失败: {err}")
        else:
            lines.append(f"【{key}】: {str(val)[:500]}")
    return "\n".join(lines)
