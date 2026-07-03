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


# ── 模板3: create_interview_then_generate_report ────────────

def _match_create_interview_then_report(seq: list[dict]) -> bool:
    if len(seq) < 2:
        return False
    first = seq[0]
    last = seq[-1]
    return (
        isinstance(first, dict) and first.get("tool") == "create_interview_record_tool"
        and isinstance(last, dict) and last.get("tool") == "generate_interview_report_tool"
    )


def _build_create_interview_then_report(seq: list[dict]) -> TaskRoot:
    first_params = dict(seq[0].get("params", {}))
    last_params = dict(seq[-1].get("params", {}))

    create_action = Action(
        action_id="create_interview",
        tool="create_interview_record_tool",
        input_params=dict(first_params),
        output_key="create_interview_result",
    )

    report_params = dict(last_params)
    if not report_params.get("company") and first_params.get("company_name"):
        report_params["company"] = first_params["company_name"]
    if not report_params.get("job_title") and first_params.get("job_title"):
        report_params["job_title"] = first_params["job_title"]

    report_action = Action(
        action_id="generate_report",
        tool="generate_interview_report_tool",
        input_params=report_params,
        output_key="report_result",
        depends_on=["create_interview"],
    )

    all_actions = [create_action, report_action]
    subtask = SubTask(
        sub_task_id="main",
        goal="创建面试记录并生成面试报告",
        actions=all_actions,
    )

    edges = [("create_interview", "generate_report")]
    dag = TaskDAG(nodes={"main": subtask}, edges=edges)

    return TaskRoot(
        task_id="",
        goal="创建面试记录并生成面试报告",
        action_sequence=seq,
        dag=dag,
    )


register(TaskTemplate(
    name="create_interview_then_generate_report",
    description="创建面试记录后自动生成面试报告",
    matches=_match_create_interview_then_report,
    build=_build_create_interview_then_report,
))


# ── 模板4: parse_then_generate_resume ────────────────────────

def _match_parse_then_generate_resume(seq: list[dict]) -> bool:
    if len(seq) < 2:
        return False
    for s in seq[:-1]:
        if not isinstance(s, dict) or s.get("tool") != "parse_file_tool":
            return False
    last = seq[-1]
    return isinstance(last, dict) and last.get("tool") == "generate_resume_tool"


def _build_parse_then_generate_resume(seq: list[dict]) -> TaskRoot:
    parse_actions: list[Action] = []
    for i, s in enumerate(seq[:-1]):
        params = dict(s.get("params", {}))
        parse_actions.append(Action(
            action_id=f"parse_{i}",
            tool=s["tool"],
            input_params=params,
            output_key=f"parse_result_{i}",
        ))

    resume_params = dict(seq[-1].get("params", {}))
    resume_action = Action(
        action_id="generate_resume",
        tool="generate_resume_tool",
        input_params=resume_params,
        output_key="resume_result",
        depends_on=[a.action_id for a in parse_actions],
    )

    all_actions = parse_actions + [resume_action]
    subtask = SubTask(
        sub_task_id="main",
        goal="解析文件并生成简历",
        actions=all_actions,
    )

    edges = [(a.action_id, "generate_resume") for a in parse_actions]
    dag = TaskDAG(nodes={"main": subtask}, edges=edges)

    return TaskRoot(
        task_id="",
        goal="解析文件并生成简历",
        action_sequence=seq,
        dag=dag,
    )


register(TaskTemplate(
    name="parse_then_generate_resume",
    description="解析文件后生成简历",
    matches=_match_parse_then_generate_resume,
    build=_build_parse_then_generate_resume,
))


# ── 模板匹配入口 ────────────────────────────────────────────

def match_template(sequence: list[dict]) -> TaskTemplate | None:
    for tmpl in TASK_TEMPLATES:
        if tmpl.matches(sequence):
            return tmpl
    return None
