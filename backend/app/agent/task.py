"""Planner-Executor task definitions."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


@dataclass
class Task:
    """A single executable task in the plan."""

    task: str
    tool: str
    args: dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    result: dict[str, Any] | None = None
    error: str | None = None


@dataclass
class TaskPlan:
    """Ordered list of tasks produced by the planner."""

    tasks: list[Task] = field(default_factory=list)
    summary: str = ""

    def as_serializable(self) -> list[dict[str, Any]]:
        return [
            {
                "task": task.task,
                "tool": task.tool,
                "args": task.args,
                "status": task.status.value,
            }
            for task in self.tasks
        ]
