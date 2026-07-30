"""Planner-Executor runtime state."""

from dataclasses import dataclass, field
import time
import uuid

from app.agent.task import Task, TaskPlan


@dataclass
class AgentState:
    """Runtime state for one request."""

    request_id: str
    user_input: str
    destination: str
    days: int
    styles: list[str] = field(default_factory=list)
    session_id: str = ""
    previous_messages: list[dict] = field(default_factory=list)
    plan: TaskPlan = field(default_factory=TaskPlan)
    plan_source: str = "planner"
    current_task: Task | None = None
    tool_results: list[dict] = field(default_factory=list)
    final_answer: str = ""
    messages: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)


def build_request_id() -> str:
    """Short request id for tracing."""
    return uuid.uuid4().hex[:12]
