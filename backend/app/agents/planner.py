"""Planner compatibility wrapper — delegates to app.agent.planner."""

from app.agent.planner import build_messages, build_user_input

__all__ = ["build_messages", "build_user_input"]
