"""Executor stage for the travel agent."""

from __future__ import annotations

import copy
import json

from app.agent.state import AgentState
from app.agent.task import Task, TaskStatus
from app.agent.tools.registry import resolve_tool_name
from app.agents.executor import build_tool_messages, execute_tool_calls


def _make_tool_call(task: Task, index: int) -> dict:
    concrete_tool = resolve_tool_name(task.tool)
    return {
        "id": f"task_{index}_{concrete_tool}",
        "type": "function",
        "function": {
            "name": concrete_tool,
            "arguments": json.dumps(task.args, ensure_ascii=False),
        },
    }


def _build_route_task_from_places(state: AgentState) -> Task | None:
    pois = []
    for result in state.tool_results:
        if result.get("tool_name") in ("search_place", "search_pois"):
            pois.extend(result.get("result", {}).get("pois", []))
    if len(pois) < 2:
        return None
    origin = pois[0].get("name")
    destination = pois[1].get("name")
    if not origin or not destination:
        return None
    return Task(
        task="规划热门景点路线",
        tool="route",
        args={"start": origin, "end": destination, "city": state.destination, "mode": "driving"},
    )


async def _execute_single_task(
    state: AgentState,
    task: Task,
    index: int,
    on_task_start,
    on_task_result,
) -> None:
    task.status = TaskStatus.RUNNING
    state.current_task = copy.deepcopy(task)

    tool_call = _make_tool_call(task, index)
    args = json.loads(tool_call["function"]["arguments"])
    await on_task_start(task, resolve_tool_name(task.tool), args)

    results = await execute_tool_calls([tool_call])
    result = results[0]
    task.status = TaskStatus.ERROR if result.get("result", {}).get("error") else TaskStatus.DONE
    task.result = result.get("result", {})
    task.error = task.result.get("error") if isinstance(task.result, dict) else None
    state.tool_results.append(result)

    assistant_msg, tool_msgs = build_tool_messages([tool_call], results)
    state.messages.append(assistant_msg)
    state.messages.extend(tool_msgs)
    await on_task_result(task, result)


async def execute_plan(
    state: AgentState,
    on_task_start,
    on_task_result,
) -> AgentState:
    """Execute all tasks in order and update runtime state."""
    executed_route = False

    for index, task in enumerate(list(state.plan.tasks)):
        if task.tool == "route" and not (
            ("start" in task.args and "end" in task.args)
            or ("origin" in task.args and "destination" in task.args)
        ):
            dynamic_task = _build_route_task_from_places(state)
            if dynamic_task is None:
                continue
            state.plan.tasks[index] = dynamic_task
            task = dynamic_task
            executed_route = True
        elif task.tool == "route":
            executed_route = True

        await _execute_single_task(state, task, index, on_task_start, on_task_result)

    if not executed_route:
        dynamic_task = _build_route_task_from_places(state)
        if dynamic_task is not None:
            state.plan.tasks.append(dynamic_task)
            await _execute_single_task(state, dynamic_task, len(state.plan.tasks) - 1, on_task_start, on_task_result)

    state.current_task = None
    return state
