from typing import Any, Callable

from services.task.models import Action, SubTask, TaskDAG, TaskRoot
from services.task.templates import match_template
from services.tool_meta import TOOL_METADATA


_DECOMPOSE_PROMPT = """你是一个任务拆解专家。根据用户提供的 Action 序列和原始需求，生成一个可执行的 DAG（有向无环图）。

要求：
1. 每个 Action 都必须映射到现有工具，以下是可用工具列表：
{tools_list}

2. 判断哪些 Action 可以并行执行，哪些必须串行
3. 为每个 Action 补充必要的参数（从用户原始描述中提取）
4. 不要生成多余的操作
5. 如果 Action 之间存在数据依赖（如匹配需要抓取结果的 job_ids），在 depends_on 中标明

以 JSON 格式返回，不要包含其他文字：
{{
  "goal": "任务目标描述",
  "actions": [
    {{
      "action_id": "唯一标识",
      "tool": "工具名",
      "input_params": {{}},
      "depends_on": ["依赖的 action_id 列表"]
    }}
  ]
}}

Action 序列：{action_json}
用户原始需求：{user_input}
"""


def _build_tools_list() -> str:
    lines = []
    for name, meta in TOOL_METADATA.items():
        params_desc = ", ".join(
            f"{p.name}({'必填' if p.required else '可选'})"
            for p in meta.parameters
        )
        lines.append(f"- {name}: {meta.description} 参数: {params_desc}")
    return "\n".join(lines)


class TaskDecompositionEngine:
    def __init__(self, llm_call: Callable[[str], str] | None = None):
        self._llm_call = llm_call

    def should_decompose(self, actions: list[dict]) -> bool:
        if not actions:
            return False
        return len(actions) >= 2

    def decompose(self, actions: list[dict], user_input: str = "") -> TaskRoot | None:
        if not self.should_decompose(actions):
            return None

        tmpl = match_template(actions)
        if tmpl is not None:
            root = tmpl.build(actions)
            action_ids = set()
            for subtask in root.dag.nodes.values():
                for a in subtask.actions:
                    action_ids.add(a.action_id)
            if not root.task_id:
                import uuid
                root.task_id = uuid.uuid4().hex[:16]
            return root

        if self._llm_call is not None:
            return self._llm_decompose(actions, user_input)

        return None

    def _llm_decompose(self, actions: list[dict], user_input: str) -> TaskRoot | None:
        import json

        prompt = _DECOMPOSE_PROMPT.format(
            tools_list=_build_tools_list(),
            action_json=json.dumps(actions, ensure_ascii=False),
            user_input=user_input,
        )

        try:
            resp = self._llm_call(prompt)
            parsed = _extract_json(resp)
            if not parsed or "actions" not in parsed:
                return None

            import uuid
            root = TaskRoot(
                task_id=uuid.uuid4().hex[:16],
                goal=parsed.get("goal", user_input),
                action_sequence=actions,
                dag=_build_dag_from_llm(parsed),
            )
            return root
        except Exception:
            return None

    @classmethod
    def from_llm_only(cls) -> "TaskDecompositionEngine":
        return cls(llm_call=None)


def _extract_json(text: str) -> dict | None:
    import json
    import re

    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    m = re.search(r"\{.*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _build_dag_from_llm(parsed: dict) -> TaskDAG:
    action_list = parsed.get("actions", [])
    actions = []
    for a in action_list:
        actions.append(Action(
            action_id=a.get("action_id", ""),
            tool=a.get("tool", ""),
            input_params=a.get("input_params", {}),
            output_key=a.get("action_id", ""),
            depends_on=a.get("depends_on", []),
        ))

    subtask = SubTask(
        sub_task_id="main",
        goal=parsed.get("goal", ""),
        actions=actions,
    )

    edges = []
    for a in actions:
        for dep in a.depends_on:
            edges.append((dep, a.action_id))

    return TaskDAG(nodes={"main": subtask}, edges=edges)
