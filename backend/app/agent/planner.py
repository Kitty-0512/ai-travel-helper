"""Planner stage for the travel agent."""

from __future__ import annotations

import json
import re
import asyncio

from app.agent.state import AgentState
from app.agent.task import Task, TaskPlan
from app.agents.prompts.planner import PLANNER_SYSTEM_PROMPT
from app.core.config import settings
from app.llm.deepseek import chat_completion_simple


PLANNER_OUTPUT_PROMPT = """你是旅行任务规划器。请把用户需求拆成执行计划，只输出 JSON。

输出格式：
{
  "summary": "一句话总结规划思路",
  "tasks": [
    {"task": "查询天气", "tool": "weather", "args": {"city": "上海", "days": 5}},
    {"task": "搜索热门景点", "tool": "poi_search", "args": {"city": "上海"}},
    {"task": "搜索文化景点", "tool": "poi_search", "args": {"city": "上海", "category": "古迹"}},
    {"task": "规划候选路线", "tool": "route", "args": {"city": "上海"}}
  ]
}

规则：
1. tool 只能从 weather / poi_search / route / flight_search / hotel_search 中选择
2. 所有任务必须围绕目标城市和旅行天数
3. 至少包含 weather 和 poi_search
4. 只有用户明确提到机票/酒店/住宿时，才加入 flight_search / hotel_search
5. route 任务如果没有明确起终点，可以只传 city，让执行器后续根据 POI 结果补充
6. 只输出 JSON，不要 markdown，不要解释
"""


def build_user_input(
    destination: str,
    days: int,
    styles: list[str],
    user_feedback: str | None = None,
    memory_text: str | None = None,
) -> str:
    """Create a normalized user request string."""
    style_text = f"，偏好：{'、'.join(styles)}" if styles else ""
    if user_feedback:
        base = f"目的地：{destination}；天数：{days}天{style_text}。用户追问：{user_feedback}"
    else:
        base = f"请帮我规划{destination}{days}天旅行行程{style_text}。"
    if memory_text:
        return f"{base}\n{memory_text}"
    return base


def build_messages(
    destination: str,
    days: int,
    styles: list[str],
    user_feedback: str | None = None,
    memory_text: str | None = None,
) -> list[dict]:
    """Build final response generation messages.

    Kept as a compatibility wrapper for the old module path.
    """
    return [
        {"role": "system", "content": PLANNER_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": build_user_input(
                destination, days, styles, user_feedback, memory_text=memory_text
            ),
        },
    ]


async def create_plan(state: AgentState) -> TaskPlan:
    """Create an explicit execution plan for the executor."""
    # Prefer the already-normalized user_input (may include long-term memory)
    user_content = state.user_input or build_user_input(
        state.destination, state.days, state.styles
    )
    messages = [
        {"role": "system", "content": PLANNER_OUTPUT_PROMPT},
        {"role": "user", "content": user_content},
    ]
    try:
        raw = await asyncio.wait_for(
            chat_completion_simple(messages, max_tokens=1200),
            timeout=settings.planner_timeout,
        )
        parsed = _parse_plan_json(raw)
        plan = TaskPlan(
            tasks=[Task(task=item["task"], tool=item["tool"], args=item.get("args", {})) for item in parsed["tasks"]],
            summary=parsed.get("summary", ""),
        )
        if plan.tasks:
            state.plan_source = "planner"
            return plan
    except Exception:
        pass
    state.plan_source = "fallback"
    return build_fallback_plan(state)


def build_fallback_plan(state: AgentState) -> TaskPlan:
    """Deterministic fallback plan if planner LLM output fails."""
    tasks = [
        Task("查询天气", "weather", {"city": state.destination, "days": min(state.days, 7)}),
        Task("搜索热门景点", "poi_search", {"city": state.destination}),
    ]

    category_map = {
        "历史文化": "古迹",
        "自然风光": "自然",
        "购物": "购物",
        "美食": "美食",
        "艺术": "博物馆",
    }
    for style in state.styles[:2]:
        category = category_map.get(style)
        if category:
            tasks.append(Task(f"搜索{style}相关地点", "poi_search", {"city": state.destination, "category": category}))

    tasks.append(Task("规划候选路线", "route", {"city": state.destination}))
    return TaskPlan(tasks=tasks, summary="基于天气、景点和路线信息生成旅行行程。")


def _parse_plan_json(raw: str) -> dict:
    text = raw.strip()
    match = re.search(r"\{[\s\S]*\}$", text)
    if match:
        text = match.group(0)
    parsed = json.loads(text)
    tasks = parsed.get("tasks", [])
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("planner returned empty tasks")
    return parsed
