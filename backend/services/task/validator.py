from services.tool_meta import TOOL_METADATA
from services.task.models import TaskRoot


def validate_action(tool: str, params: dict) -> list[str]:
    errors: list[str] = []

    meta = TOOL_METADATA.get(tool)
    if not meta:
        errors.append(f"工具 '{tool}' 不存在")
        return errors

    for p in meta.parameters:
        val = params.get(p.name)
        if p.required:
            if val is None or (isinstance(val, str) and not val.strip()):
                errors.append(f"缺少必需参数 '{p.name}'")
        # Type coercion
        if val is not None and p.type == "integer" and not isinstance(val, int):
            try:
                params[p.name] = int(val)
            except (ValueError, TypeError):
                errors.append(f"参数 '{p.name}' 需要整数，实际为 {type(val).__name__}")

    return errors


def _find_cycle(nodes: list[str], edges: list[tuple[str, str]]) -> list[str] | None:
    graph: dict[str, list[str]] = {n: [] for n in nodes}
    for src, dst in edges:
        if src in graph:
            graph[src].append(dst)

    visited = set()
    path = []

    def dfs(node: str) -> list[str] | None:
        visited.add(node)
        path.append(node)
        for neighbor in graph.get(node, []):
            if neighbor in path:
                cycle_start = path.index(neighbor)
                return path[cycle_start:] + [neighbor]
            if neighbor not in visited:
                result = dfs(neighbor)
                if result:
                    return result
        path.pop()
        return None

    for n in nodes:
        if n not in visited:
            result = dfs(n)
            if result:
                return result
    return None


def validate_dag(root: TaskRoot) -> list[str]:
    errors: list[str] = []

    if not root.dag or not root.dag.nodes:
        errors.append("DAG 中没有任务节点")
        return errors

    all_action_ids: set[str] = set()
    all_tools: set[str] = set()

    for sub_id, subtask in root.dag.nodes.items():
        for action in subtask.actions:
            all_action_ids.add(action.action_id)
            all_tools.add(action.tool)

            meta = TOOL_METADATA.get(action.tool)
            if not meta:
                errors.append(f"工具 '{action.tool}' (action: {action.action_id}) 不存在")
                continue

            for p in meta.parameters:
                if p.required:
                    val = action.input_params.get(p.name)
                    if val is None or (isinstance(val, str) and not val.strip()):
                        errors.append(f"Action '{action.action_id}' 缺少必需参数 '{p.name}'")

    for sub_id, subtask in root.dag.nodes.items():
        for action in subtask.actions:
            for dep in action.depends_on:
                if dep not in all_action_ids:
                    errors.append(f"Action '{action.action_id}' 依赖 '{dep}' 但该 Action 不存在")

    node_ids = list(all_action_ids)
    edges: list[tuple[str, str]] = []
    for sub_id, subtask in root.dag.nodes.items():
        for action in subtask.actions:
            for dep in action.depends_on:
                edges.append((dep, action.action_id))

    cycle = _find_cycle(node_ids, edges)
    if cycle:
        errors.append(f"检测到循环依赖: {' → '.join(cycle)}")

    return errors
