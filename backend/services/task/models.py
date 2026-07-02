from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class Action:
    action_id: str
    tool: str
    input_params: dict = field(default_factory=dict)
    output_key: str = ""
    retry: int = 1
    timeout: int = 120
    depends_on: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.output_key:
            self.output_key = self.action_id

    def to_dict(self) -> dict:
        return {
            "action_id": self.action_id,
            "tool": self.tool,
            "input_params": self.input_params,
            "output_key": self.output_key,
            "retry": self.retry,
            "timeout": self.timeout,
            "depends_on": self.depends_on,
        }


@dataclass
class SubTask:
    sub_task_id: str
    goal: str
    actions: list[Action] = field(default_factory=list)
    depend_on: list[str] = field(default_factory=list)
    priority: int = 0

    def to_dict(self) -> dict:
        return {
            "sub_task_id": self.sub_task_id,
            "goal": self.goal,
            "actions": [a.to_dict() for a in self.actions],
            "depend_on": self.depend_on,
            "priority": self.priority,
        }


@dataclass
class TaskDAG:
    nodes: dict[str, SubTask] = field(default_factory=dict)
    edges: list[tuple[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": list(self.edges),
        }


@dataclass
class TaskRoot:
    task_id: str
    goal: str
    action_sequence: list[dict] = field(default_factory=list)
    dag: TaskDAG = field(default_factory=TaskDAG)
    error_strategy: Literal["continue", "abort"] = "continue"

    @classmethod
    def new(cls, goal: str, action_sequence: list[dict] | None = None) -> TaskRoot:
        return cls(
            task_id=uuid.uuid4().hex[:16],
            goal=goal,
            action_sequence=action_sequence or [],
        )

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "goal": self.goal,
            "action_sequence": self.action_sequence,
            "dag": self.dag.to_dict() if self.dag else None,
            "error_strategy": self.error_strategy,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
