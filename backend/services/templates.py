from dataclasses import dataclass, field
from typing import Callable

from services.task.models import Action, SubTask, TaskDAG, TaskRoot


@dataclass
class TaskTemplate:
    name: str
    description: str
    matches: Callable[[list[dict]], bool]
    build: Callable[[list[dict]], TaskRoot]


TASK_TEMPLATES: list[TaskTemplate] = []


def register(tmpl: TaskTemplate):
    TASK_TEMPLATES.append(tmpl)


# ── 模板1: crawl_and_match ──────────────────────────────────

def _match_crawl_and_match(seq: list[dict]) -> bool:
    if len(seq) < 2:
        return False
    for s in seq[:-1]:
        if not isinstance(s, dict) or s.get("tool") != "kimi_crawl_tool":
            return False
    last = seq[-1]
    return isinstance(last, dict) and last.get("tool") == "match_jobs_tool"


def _build_crawl_and_match(seq: list[dict]) -> TaskRoot:
    crawl_actions: list[Action] = []
    for i, s in enumerate(seq[:-1]):
        params = dict(s.get("params", {}))
        crawl_actions.append(Action(
            action_id=f"crawl_{i}",
            tool="kimi_crawl_tool",
            input_params=params,
            output_key=f"crawl_result_{i}",
        ))

    match_params = dict(seq[-1].get("params", {}))
    match_action = Action(
        action_id="match",
        tool="match_jobs_tool",
        input_params=_inject_job_ids(match_params, crawl_actions),
        output_key="match_result",
        depends_on=[a.action_id for a in crawl_actions],
    )

    all_actions = crawl_actions + [match_action]
    subtask = SubTask(
        sub_task_id="main",
        goal="抓取岗位并匹配评分",
        actions=all_actions,
    )

    edges = [(a.action_id, "match") for a in crawl_actions]
    dag = TaskDAG(nodes={"main": subtask}, edges=edges)

    return TaskRoot(
        task_id="",
        goal="抓取岗位并匹配评分",
        action_sequence=seq,
        dag=dag,
    )


def _inject_job_ids(params: dict, crawl_actions: list[Action]) -> dict:
    result = dict(params)
    if not result.get("job_ids"):
        refs = [f"${a.output_key}.id" for a in crawl_actions]
        result["_job_id_refs"] = refs
    return result


register(TaskTemplate(
    name="crawl_and_match",
    description="抓取岗位后自动匹配评分",
    matches=_match_crawl_and_match,
    build=_build_crawl_and_match,
))


# ── 模板2: parse_then_create_interview ──────────────────────

def _match_parse_then_create_interview(seq: list[dict]) -> bool:
    if len(seq) < 2:
        return False
    for s in seq[:-1]:
        if not isinstance(s, dict) or s.get("tool") != "parse_file_tool":
            return False
    last = seq[-1]
    return isinstance(last, dict) and last.get("tool") == "create_interview_record_tool"


def _build_parse_then_create_interview(seq: list[dict]) -> TaskRoot:
    parse_actions: list[Action] = []
    for i, s in enumerate(seq[:-1]):
        params = dict(s.get("params", {}))
        parse_actions.append(Action(
            action_id=f"parse_{i}",
            tool=s["tool"],
            input_params=params,
            output_key=f"parse_result_{i}",
        ))

    interview_params = dict(seq[-1].get("params", {}))
    interview_action = Action(
        action_id="create_interview",
        tool="create_interview_record_tool",
        input_params=interview_params,
        output_key="interview_result",
        depends_on=[a.action_id for a in parse_actions],
    )

    all_actions = parse_actions + [interview_action]
    subtask = SubTask(
        sub_task_id="main",
        goal="解析文件并创建面试记录",
        actions=all_actions,
    )

    edges = [(a.action_id, "create_interview") for a in parse_actions]
    dag = TaskDAG(nodes={"main": subtask}, edges=edges)

    return TaskRoot(
        task_id="",
        goal="解析文件并创建面试记录",
        action_sequence=seq,
        dag=dag,
    )


register(TaskTemplate(
    name="parse_then_create_interview",
    description="解析文件后创建面试记录",
    matches=_match_parse_then_create_interview,
    build=_build_parse_then_create_interview,
))


# ── 模板匹配入口 ────────────────────────────────────────────

def match_template(sequence: list[dict]) -> TaskTemplate | None:
    for tmpl in TASK_TEMPLATES:
        if tmpl.matches(sequence):
            return tmpl
    return None
