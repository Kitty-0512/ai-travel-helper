"""Agent 主循环 —— Planner → Executor → Finalize 协调器

新生成请求：Planner 生成显式任务计划 → Executor 按计划调用工具 → LLM 流式撰写最终行程。
多轮续聊请求：沿用 ReAct（Think → Act → Observe）循环，保证 /chat 端点行为不变。

两条路径最终都汇聚到 `_finalize`，产出相同的 SSE 事件序列
（agent_think | tool_call | tool_result | chunk | itinerary_json | done | error），
前端无需感知内部实现差异。
"""

import json
import logging
import asyncio
from contextlib import suppress
from typing import AsyncGenerator

from app.core.config import settings
from app.llm.deepseek import chat_completion_stream, chat_completion_simple
from app.agents.executor import execute_tool_calls, build_tool_messages
from app.agents.prompts.planner import FINALIZE_SYSTEM_PROMPT
from app.tools.registry import build_tools_schema
from app.models.response import SSEEvent
from app.session.store import session_store
from app.session.repository import session_repo

from app.agent.state import AgentState, build_request_id
from app.agent.planner import create_plan, build_user_input, build_fallback_plan
from app.agent.executor import execute_plan
from app.memory import memory_manager
from app.trace import trace_manager
from app.trace.context import has_trace_context

logger = logging.getLogger(__name__)


async def run_agent(
    destination: str,
    days: int,
    styles: list[str],
    previous_messages: list[dict] | None = None,
    user_feedback: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
) -> AsyncGenerator[SSEEvent, None]:
    """
    Agent 主循环入口。

    - 新生成：previous_messages=None → Planner-Executor 流程
    - 多轮修改：previous_messages + user_feedback → ReAct 续聊流程
    """
    event_id = 0
    request_id = build_request_id()

    def _emit(ev_type: str, data=None) -> SSEEvent:
        nonlocal event_id
        event_id += 1
        return SSEEvent(type=ev_type, data=data, id=event_id)

    # Retrieve long-term preference memory (fail-open)
    query = user_feedback or destination
    memory_text = await memory_manager.retrieve_for_prompt(user_id, query=query)
    await trace_manager.start_trace(
        request_id=request_id,
        user_id=user_id,
        input_payload={
            "mode": "chat" if previous_messages is not None else "generate",
            "destination": destination,
            "days": days,
            "styles": styles,
            "session_id": session_id,
            "has_memory": bool(memory_text),
            "user_feedback": user_feedback or "",
        },
    )

    if previous_messages is not None:
        generator = _run_chat_continuation(
            _emit,
            request_id,
            destination,
            days,
            styles,
            previous_messages,
            user_feedback,
            session_id,
            user_id=user_id,
            memory_text=memory_text,
        )
    else:
        generator = _run_planner_executor(
            _emit,
            request_id,
            destination,
            days,
            styles,
            session_id,
            user_id=user_id,
            memory_text=memory_text,
        )

    try:
        async for event in generator:
            yield event
    except GeneratorExit:
        return
    except BaseException as e:
        # 兜底：捕获所有从子生成器逃逸的未处理异常，
        # 转成 error SSE 事件后关流，避免前端看到"连接意外中断"。
        logger.exception("[Agent] unhandled exception escaped generator: %s", e)
        with suppress(BaseException):
            yield _emit("error", {
                "code": "STREAM_ERROR",
                "message": f"生成过程异常（{type(e).__name__}），请重试",
            })
    finally:
        if has_trace_context():
            await trace_manager.finish_trace(
                status="cancelled",
                action="request_cancelled",
                output_payload={"message": "trace ended before finalize"},
            )


# ============================================================
# 路径 1：Planner → Executor → Finalize（首次生成）
# ============================================================

async def _run_planner_executor(
    _emit,
    request_id: str,
    destination: str,
    days: int,
    styles: list[str],
    session_id: str | None,
    user_id: str | None = None,
    memory_text: str = "",
) -> AsyncGenerator[SSEEvent, None]:
    state = AgentState(
        request_id=request_id,
        user_input=build_user_input(
            destination, days, styles, memory_text=memory_text or None
        ),
        destination=destination,
        days=days,
        styles=styles,
        session_id=session_id or "",
    )

    if memory_text:
        yield _emit("agent_think", f"已加载用户长期偏好：{memory_text}")

    # ── 1. Planner：生成显式执行计划 ──
    yield _emit("agent_think", "正在制定旅行规划方案...")
    try:
        state.plan = await asyncio.wait_for(create_plan(state), timeout=settings.planner_timeout)
    except asyncio.TimeoutError:
        state.plan_source = "fallback"
        state.plan = build_fallback_plan(state)
    except Exception as e:
        yield await _emit_error_with_trace(_emit, "PLANNER_ERROR", str(e))
        return

    await trace_manager.record_step(
        action="planner_complete",
        output_payload={
            "plan_source": state.plan_source,
            "summary": state.plan.summary,
            "tasks": state.plan.as_serializable(),
            "task_count": len(state.plan.tasks),
        },
        status="success" if state.plan_source == "planner" else "fallback",
    )

    plan_lines = "\n".join(f"{i + 1}. {t.task}" for i, t in enumerate(state.plan.tasks))
    yield _emit(
        "agent_think",
        f"已生成执行计划（共{len(state.plan.tasks)} 项任务）：\n{plan_lines}",
    )

    # ── 2. Executor：按计划执行工具调用 ──
    # execute_plan 是普通协程而非异步生成器，这里用队列把它的任务回调桥接成 SSE 事件，
    # 使执行过程可以和 LLM 流式输出一样被实时推送给前端。
    queue: asyncio.Queue = asyncio.Queue()
    _SENTINEL = object()

    async def on_task_start(task, tool_name, args):
        await queue.put(("agent_think", f"正在执行任务：{task.task}"))
        await queue.put(("tool_call", {
            "type": "tool_call",
            "tool": tool_name,
            "status": "running",
            "message": _tool_running_message(tool_name),
            "args": args,
        }))

    async def on_task_result(task, result):
        await queue.put((
            "tool_result",
            {
                "tool": result["tool_name"],
                "status": "error" if result.get("result", {}).get("error") else "success",
                "message": _tool_result_message(result["tool_name"], result.get("result", {})),
                "duration": result.get("duration_ms", 0),
                "result_preview": _truncate_result(result.get("result", {})),
            },
        ))

    async def _drive_executor():
        try:
            await execute_plan(state, on_task_start, on_task_result)
        except BaseException as e:
            logger.exception("[Executor] _drive_executor raised: %s (type=%s)", e, type(e).__name__)
            raise
        finally:
            await queue.put(_SENTINEL)

    exec_task = asyncio.create_task(_drive_executor())
    try:
        while True:
            item = await queue.get()
            if item is _SENTINEL:
                break
            ev_type, data = item
            yield _emit(ev_type, data)
        # 等待 task 完成，传播内部异常（如有）
        await asyncio.wait_for(exec_task, timeout=settings.executor_timeout)
        # 额外检查：task 是否以异常结束但未被 await 探测到
        if exec_task.done() and not exec_task.cancelled():
            exc = exec_task.exception()
            if exc is not None:
                logger.exception("[Executor] task completed with unhandled exception: %s", exc)
                yield await _emit_error_with_trace(
                    _emit, "EXECUTOR_ERROR",
                    f"工具执行异常（{type(exc).__name__}）：{exc}",
                )
                return
    except asyncio.TimeoutError:
        if not exec_task.done():
            exec_task.cancel()
            with suppress(Exception):
                await exec_task
        yield await _emit_error_with_trace(
            _emit,
            "EXECUTOR_TIMEOUT",
            f"工具执行超时（>{settings.executor_timeout}s）",
        )
        return
    except Exception as e:
        logger.exception("[Executor] unhandled exception in queue loop: %s", e)
        if not exec_task.done():
            exec_task.cancel()
            with suppress(Exception):
                await exec_task
        yield await _emit_error_with_trace(_emit, "EXECUTOR_ERROR", str(e))
        return
    except BaseException as e:
        logger.exception("[Executor] base exception in queue loop: %s (type=%s)", e, type(e).__name__)
        if not exec_task.done():
            exec_task.cancel()
            with suppress(Exception):
                await exec_task
        with suppress(BaseException):
            yield await _emit_error_with_trace(
                _emit, "EXECUTOR_CANCELLED", f"生成过程被中断（{type(e).__name__}），请重试"
            )
        return

    # ── 3. Finalize：基于 Executor 收集到的真实数据，流式撰写最终行程 ──
    yield _emit("agent_think", "正在撰写行程文案...")

    # 工具摘要合并进单一 user 消息，避免连发多条 assistant「已执行工具调用…」
    # 导致模型复述工具日志而不是写行程文案
    data_block = _build_finalize_data_block(state.messages)
    messages: list[dict] = [
        {"role": "system", "content": FINALIZE_SYSTEM_PROMPT},
        {
            "role": "user",
            "content": (
                f"{state.user_input}\n\n"
                f"{data_block}\n\n"
                "请根据以上真实数据，直接输出完整 Markdown 行程文案（结构见系统提示），"
                "末尾附一个 JSON 代码块。"
                "禁止复述「已执行工具调用」或任何工具日志原文；"
                "禁止输出 XML/HTML；禁止再调用工具。"
            ),
        },
    ]

    try:
        llm_response = None
        async for item in _stream_llm_with_timeout(messages=messages, timeout=settings.finalize_timeout):
            if isinstance(item, str):
                yield _emit("chunk", item)
            else:
                llm_response = item
        if llm_response is None:
            yield await _emit_error_with_trace(_emit, "LLM_EMPTY", "LLM 未返回任何内容")
            return

        content = (llm_response.content or "").strip()
        # 文案过短或复述工具日志时，再非流式补写一次（仅 Finalize，不影响其它路径）
        if len(content) < 120 or content.startswith("已执行工具调用"):
            try:
                rescued = await asyncio.wait_for(
                    chat_completion_simple(
                        [
                            {"role": "system", "content": FINALIZE_SYSTEM_PROMPT},
                            {
                                "role": "user",
                                "content": (
                                    f"{state.user_input}\n\n{data_block}\n\n"
                                    "请输出完整 Markdown 行程（含 Day 结构与末尾 JSON）。"
                                    "不要输出工具日志。"
                                ),
                            },
                        ],
                        max_tokens=3500,
                    ),
                    timeout=settings.finalize_timeout,
                )
                rescued = (rescued or "").strip()
                if len(rescued) > len(content):
                    content = rescued
                    # 前端此前可能已收到劣质 chunk，用完整正文再推一次覆盖观感
                    yield _emit("chunk", "\n\n" + content)
            except Exception:
                logger.warning("[Finalize] rescue rewrite failed", exc_info=True)

        if content:
            # 用最终正文覆盖 messages，供后续 JSON 提取
            messages.append({"role": "assistant", "content": content})
            llm_response.content = content

    except asyncio.TimeoutError:
        yield await _emit_error_with_trace(
            _emit,
            "FINALIZE_TIMEOUT",
            f"行程撰写超时（>{settings.finalize_timeout}s）",
        )
        return
    except Exception as e:
        yield await _emit_error_with_trace(_emit, "LLM_API_ERROR", str(e))
        return
    except BaseException as e:
        try:
            yield await _emit_error_with_trace(_emit, "LLM_CANCELLED", f"LLM 调用被中断（{type(e).__name__}）")
        except Exception:
            pass
        return

    async for ev in _finalize(
        _emit,
        request_id,
        messages,
        destination,
        days,
        styles,
        session_id,
        user_id=user_id,
        extract_text="",
        extract_styles=styles,
        places_source=state.messages,
    ):
        yield ev


# ============================================================
# 路径 2：ReAct 续聊（/chat 多轮修改，兼容旧行为）
# ============================================================

async def _run_chat_continuation(
    _emit,
    request_id: str,
    destination: str,
    days: int,
    styles: list[str],
    previous_messages: list[dict],
    user_feedback: str | None,
    session_id: str | None,
    user_id: str | None = None,
    memory_text: str = "",
) -> AsyncGenerator[SSEEvent, None]:
    """ReAct：Think → Act → Observe → Loop，在已有上下文上继续对话。"""
    messages = previous_messages.copy()
    if memory_text:
        yield _emit("agent_think", f"已加载用户长期偏好：{memory_text}")
        # Inject once near the top if not already present
        if not any(
            isinstance(m.get("content"), str) and "【用户长期偏好】" in m.get("content", "")
            for m in messages
        ):
            messages.insert(
                1 if messages and messages[0].get("role") == "system" else 0,
                {"role": "system", "content": memory_text},
            )
    if user_feedback:
        messages.append({"role": "user", "content": user_feedback})

    tools_schema = build_tools_schema()
    step_count = 0

    while step_count < settings.agent_max_steps:
        step_count += 1
        yield _emit("agent_think", f"第 {step_count} 步：正在分析...")

        try:
            llm_response = None
            async for item in _stream_llm_with_timeout(
                messages=messages,
                tools=tools_schema,
                timeout=settings.finalize_timeout,
            ):
                if isinstance(item, str):
                    yield _emit("chunk", item)
                else:
                    llm_response = item

            if llm_response is None:
                yield await _emit_error_with_trace(_emit, "LLM_EMPTY", "LLM 未返回任何内容")
                return
        except asyncio.TimeoutError:
            yield await _emit_error_with_trace(
                _emit,
                "LLM_TIMEOUT",
                f"LLM 响应超时（>{settings.finalize_timeout}s）",
            )
            return
        except Exception as e:
            yield await _emit_error_with_trace(_emit, "LLM_API_ERROR", str(e))
            return
        except BaseException as e:
            try:
                yield await _emit_error_with_trace(_emit, "LLM_CANCELLED", f"LLM 调用被中断（{type(e).__name__}）")
            except Exception:
                pass
            return

        if llm_response.content and llm_response.content.strip():
            messages.append({"role": "assistant", "content": llm_response.content})

        if llm_response.tool_calls:
            for tc in llm_response.tool_calls:
                fn = tc.get("function", {})
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tool_name = fn.get("name", "unknown")
                yield _emit("tool_call", {
                    "type": "tool_call",
                    "tool": tool_name,
                    "status": "running",
                    "message": _tool_running_message(tool_name),
                    "args": args,
                })

            try:
                tool_results = await execute_tool_calls(llm_response.tool_calls)
            except BaseException as e:
                try:
                    yield await _emit_error_with_trace(_emit, "TOOL_ERROR", f"工具调用失败（{type(e).__name__}）：{e}")
                except Exception:
                    pass
                return
            for tr in tool_results:
                yield _emit("tool_result", {
                    "tool": tr["tool_name"],
                    "status": "error" if tr.get("result", {}).get("error") else "success",
                    "message": _tool_result_message(tr["tool_name"], tr.get("result", {})),
                    "duration": tr.get("duration_ms", 0),
                    "result_preview": _truncate_result(tr.get("result", {})),
                })

            assistant_msg, tool_msgs = build_tool_messages(llm_response.tool_calls, tool_results)
            messages.append(assistant_msg)
            messages.extend(tool_msgs)
            continue  # 回到循环顶部，让 LLM 处理工具结果

        if llm_response.finish_reason == "stop":
            break

    async for ev in _finalize(
        _emit,
        request_id,
        messages,
        destination,
        days,
        styles,
        session_id,
        user_id=user_id,
        extract_text=user_feedback or "",
        extract_styles=None,
    ):
        yield ev


# ============================================================
# 公共收尾：提取行程 JSON、持久化会话、发出 done 事件
# ============================================================

async def _finalize(
    _emit,
    request_id: str,
    messages: list[dict],
    destination: str,
    days: int,
    styles: list[str],
    session_id: str | None,
    user_id: str | None = None,
    extract_text: str = "",
    extract_styles: list[str] | None = None,
    places_source: list[dict] | None = None,
) -> AsyncGenerator[SSEEvent, None]:
    yield _emit("agent_think", "正在整理最终行程数据...")
    await trace_manager.record_step(
        action="finalize_start",
        input_payload={"message_count": len(messages), "destination": destination, "days": days},
        status="running",
    )

    # Load previous itinerary for merge (multi-turn chat)
    previous_itinerary: dict | None = None
    if session_id:
        prev_state = session_store.get(session_id)
        if prev_state is not None:
            previous_itinerary = prev_state.itinerary

    final_itinerary = await _extract_itinerary_json(messages, destination, days, previous_itinerary)
    itinerary_data = final_itinerary.get("days", [])
    all_places = final_itinerary.get("allPlaces", [])

    yield _emit("itinerary_json", {
        "days": itinerary_data,
        "allPlaces": all_places,
    })

    # Finalize 文案 messages 里通常没有 role=tool；坐标必须从 Executor 原始工具结果收集
    places_detail = _collect_places_from_messages(places_source or messages)
    if all_places:
        wanted = {n for n in all_places if n}
        matched = [p for p in places_detail if p.get("name") in wanted and p.get("lng") and p.get("lat")]
        if matched:
            places_detail = matched
    resolved_session_id = _persist_session(
        session_id, destination, days, styles, messages,
        itinerary=final_itinerary, user_id=user_id, places_detail=places_detail,
    )

    # Side-effect: extract & save long-term preferences (never break SSE)
    try:
        await memory_manager.extract_and_save(
            user_id=user_id,
            user_text=extract_text,
            source_session_id=resolved_session_id,
            styles=extract_styles,
        )
    except Exception:
        pass

    done_payload = {
        "request_id": request_id,
        "destination": destination,
        "days": days,
        "places_count": len(all_places),
        "places_detail": places_detail,
        "session_id": resolved_session_id,
    }
    await trace_manager.record_step(
        action="finalize_complete",
        output_payload=done_payload,
        status="success",
    )
    await trace_manager.finish_trace(status="success", output_payload=done_payload)

    yield _emit("done", done_payload)


def _persist_session(
    session_id: str | None,
    destination: str,
    days: int,
    styles: list[str],
    messages: list[dict],
    itinerary: dict | None = None,
    user_id: str | None = None,
    places_detail: list[dict] | None = None,
) -> str:
    """创建或更新会话，使 /chat 能在同一会话上继续对话。同时持久化到 PG。"""
    state = session_store.get(session_id) if session_id else None
    if state is None:
        state = session_store.create(destination, days, styles)
    else:
        state.destination = destination
        state.days = days
        state.styles = styles
    state.messages = messages
    if itinerary is not None:
        state.itinerary = itinerary
    session_store.set(state.session_id, state)

    # Persist to PostgreSQL (non-blocking best-effort; never break SSE)
    if session_repo.ready and user_id:
        try:
            asyncio.ensure_future(
                session_repo.upsert(
                    session_id=state.session_id,
                    user_id=user_id,
                    destination=destination,
                    days=days,
                    styles=styles,
                    itinerary=itinerary,
                    messages=messages,
                    places_detail=places_detail,
                )
            )
        except Exception:
            logger.warning("[Session] PG upsert fire-and-forget failed", exc_info=True)

    return state.session_id


async def _extract_itinerary_json(
    messages: list[dict],
    destination: str,
    days: int,
    previous: dict | None = None,
) -> dict:
    """提取最终行程 JSON。

    优先从 Finalize 文案末尾的 ```json 块解析（快且稳），失败再轻量 LLM 抽取。
    """
    # 1) 优先：直接解析助手文案里的 JSON（新生成路径的主路径）
    parsed = _parse_itinerary_json_from_messages(messages)
    if parsed and parsed.get("days") and not (previous and previous.get("days")):
        return _normalize_itinerary(parsed, days)

    if previous and previous.get("days"):
        prev_json = json.dumps(previous, ensure_ascii=False, indent=2)
        merge_instruction = (
            f"【已存在的行程（请在此基础上更新，不要删除已有内容）】:\n{prev_json}\n\n"
            "用户提出了新的要求。请把新的信息合并到已有行程中（例如把推荐的美食添加到对应日期的晚上时段、"
            "替换或补充景点等），保留所有原有的行程内容。输出完整的合并后 JSON。"
        )
    else:
        merge_instruction = ""

    system_prompt = (
        "你是一个数据提取助手。从以下对话中提取最终旅行行程，输出为 JSON。\n"
        f"目的地：{destination}，天数：{days}\n"
        "输出格式：\n"
        '{"days": [{"day": 1, "morning": "...", "afternoon": "...", "evening": "..."}, ...], '
        '"allPlaces": ["景点1", "景点2", ...]}\n'
        "规则：\n"
        "- 景点名称必须与搜索工具返回的一致\n"
        "- morning/afternoon/evening 每个时段一个景点\n"
        "- 只输出 JSON，不要其他文字"
    )

    # 2) 只喂「行程正文」，避免把 Finalize 的 system/工具附录整包塞进抽取，导致抽空
    assistant_text = ""
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), str) and msg["content"].strip():
            assistant_text = msg["content"].strip()
            break

    extract_messages: list[dict] = [
        {"role": "system", "content": system_prompt},
    ]
    if merge_instruction:
        extract_messages.append({"role": "user", "content": merge_instruction})
    extract_messages.append({
        "role": "user",
        "content": (
            f"请从以下行程文案提取 JSON（目的地 {destination}，{days} 天）：\n\n"
            f"{assistant_text or '（无正文，请按目的地生成空结构占位）'}"
        ),
    })

    try:
        raw = await asyncio.wait_for(
            chat_completion_simple(extract_messages, max_tokens=1500),
            timeout=settings.finalize_timeout,
        )
        json_match = raw.strip()
        if "```json" in json_match:
            json_match = json_match.split("```json")[1].split("```")[0]
        elif "```" in json_match:
            json_match = json_match.split("```")[1].split("```")[0]
        data = json.loads(json_match.strip())
        if data.get("days"):
            return _normalize_itinerary(data, days)
    except (json.JSONDecodeError, Exception):
        pass

    if parsed and parsed.get("days"):
        return _normalize_itinerary(parsed, days)
    return previous if previous else {"days": [], "allPlaces": []}


def _parse_itinerary_json_from_messages(messages: list[dict]) -> dict | None:
    """从助手 Markdown 末尾 ```json 块解析行程。"""
    import re

    for msg in reversed(messages):
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content") or ""
        if not isinstance(content, str):
            continue
        match = re.search(r"```json\s*([\s\S]*?)\s*```", content)
        if not match:
            # 兼容无 fence 的纯 JSON 尾巴
            match = re.search(r"(\{\s*\"days\"\s*:\s*\[[\s\S]*\]\s*,\s*\"allPlaces\"\s*:\s*\[[\s\S]*\]\s*\})", content)
        if not match:
            continue
        try:
            data = json.loads(match.group(1))
            if isinstance(data, dict) and isinstance(data.get("days"), list):
                return data
        except json.JSONDecodeError:
            continue
    return None


def _normalize_itinerary(data: dict, days: int) -> dict:
    """补齐字段，保证前端左侧 Day 列表能渲染。"""
    raw_days = data.get("days") or []
    norm_days = []
    for i, d in enumerate(raw_days):
        if not isinstance(d, dict):
            continue
        norm_days.append({
            "day": int(d.get("day") or (i + 1)),
            "morning": (d.get("morning") or "").strip(),
            "afternoon": (d.get("afternoon") or "").strip(),
            "evening": (d.get("evening") or "").strip(),
        })
    all_places = data.get("allPlaces") or []
    if not isinstance(all_places, list):
        all_places = []
    if not all_places:
        names: list[str] = []
        for d in norm_days:
            for key in ("morning", "afternoon", "evening"):
                name = d.get(key) or ""
                if name and name not in names:
                    names.append(name)
        all_places = names
    # 若模型少写了天数，不强制补空天，原样返回有内容的部分
    _ = days
    return {"days": norm_days, "allPlaces": all_places}


def _build_finalize_data_block(messages: list[dict]) -> str:
    """把 Executor 的 tool_call / tool 结果压成一段「数据附录」，供 Finalize 撰写。

    不要再拆成多条 role=assistant 的「已执行工具调用…」，否则模型容易复述日志。
    """
    lines: list[str] = [
        "【已收集的真实工具数据】（仅供你规划行程时参考，不要复述本段原文，不要写「已执行工具调用」）",
    ]
    for msg in messages:
        role = msg.get("role", "")
        if role == "assistant" and msg.get("tool_calls"):
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                name = fn.get("name", "unknown")
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    args = {}
                lines.append(f"- 调用：{_summarize_tool_call(name, args)}")
        elif role == "tool":
            try:
                result = (
                    json.loads(msg.get("content", "{}"))
                    if isinstance(msg.get("content"), str)
                    else msg.get("content", {})
                )
            except json.JSONDecodeError:
                result = {}
            summary = _summarize_tool_result(result)
            if summary:
                lines.append(f"- 结果：{summary}")
    if len(lines) == 1:
        lines.append("- （暂无额外工具结果，请基于目的地做合理规划，并如实说明信息有限）")
    return "\n".join(lines)


def _simplify_messages_for_finalize(messages: list[dict]) -> list[dict]:
    """兼容旧逻辑：将 tool 消息转为纯文本（现主要由 _build_finalize_data_block 使用）。"""
    simplified: list[dict] = []
    for msg in messages:
        role = msg.get("role", "")
        if role == "assistant" and msg.get("tool_calls"):
            tool_names = []
            for tc in msg.get("tool_calls", []):
                fn = tc.get("function", {})
                name = fn.get("name", "unknown")
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except (json.JSONDecodeError, TypeError):
                    args = {}
                tool_names.append(_summarize_tool_call(name, args))
            simplified.append({
                "role": "assistant",
                "content": "已执行工具调用：" + "；".join(tool_names),
            })
        elif role == "tool":
            try:
                result = json.loads(msg.get("content", "{}")) if isinstance(msg.get("content"), str) else msg.get("content", {})
            except json.JSONDecodeError:
                result = {}
            simplified.append({
                "role": "assistant",
                "content": _summarize_tool_result(result),
            })
        else:
            simplified.append(msg)
    return simplified


def _summarize_tool_call(name: str, args: dict) -> str:
    city = args.get("city") or args.get("location") or ""
    keyword = args.get("keyword") or ""
    category = args.get("category") or ""
    mapping = {
        "get_weather": f"查询{city}天气" if city else "查询天气",
        "search_place": f"搜索{city}{keyword or category or '景点'}" if city else f"搜索{keyword or category or '景点'}",
        "calculate_route": f"规划{args.get('start', '')}到{args.get('end', '')}路线" if args.get("start") else "规划路线",
        "search_flights": f"搜索飞往{city}机票" if city else "搜索机票",
        "search_hotels": f"搜索{city}酒店" if city else "搜索酒店",
    }
    return mapping.get(name, f"调用 {name}")


def _summarize_tool_result(result: dict) -> str:
    if not isinstance(result, dict):
        return "工具执行完成"
    if result.get("error"):
        return f"工具执行出错：{result['error']}"
    if result.get("forecasts"):
        bits = []
        for f in result["forecasts"][:5]:
            if not isinstance(f, dict):
                continue
            day = f.get("date") or f.get("week") or ""
            weather = f.get("dayweather") or f.get("weather") or ""
            temp = ""
            if f.get("daytemp") is not None or f.get("nighttemp") is not None:
                temp = f"{f.get('daytemp', '')}/{f.get('nighttemp', '')}℃"
            bits.append(" ".join(x for x in (str(day), str(weather), temp) if x).strip())
        detail = "；".join(b for b in bits if b)
        return f"天气预报（{len(result['forecasts'])}天）" + (f"：{detail}" if detail else "")
    if result.get("distance_text"):
        return f"路线距离 {result['distance_text']}，约 {result.get('duration_text', '')}"
    if result.get("flights"):
        return f"找到 {len(result['flights'])} 个航班"
    if result.get("hotels"):
        return f"找到 {len(result['hotels'])} 家酒店"
    if result.get("pois"):
        names = [p.get("name", "") for p in result["pois"][:10] if p.get("name")]
        if names:
            extra = f"等共 {result.get('pois_total') or len(result['pois'])} 个" if len(result["pois"]) > 10 or result.get("pois_total") else ""
            return f"搜索到景点：{'、'.join(names)}{extra}"
        return f"搜索到 {len(result['pois'])} 个结果"
    if result.get("pois_total"):
        return f"搜索到 {result['pois_total']} 个景点"
    return "工具执行完成"


def _truncate_result(result: dict, max_keys: int = 3) -> dict:
    """预览截断工具结果，避免 SSE 中传输过大数据"""
    if not isinstance(result, dict):
        return {"value": str(result)[:100]}
    truncated = {}
    for k, v in result.items():
        if isinstance(v, list) and len(v) > 3:
            truncated[k] = v[:3]
            truncated[f"{k}_total"] = len(v)
        elif isinstance(v, dict) and len(v) > 5:
            truncated[k] = dict(list(v.items())[:5])
            truncated[f"{k}_truncated"] = True
        else:
            truncated[k] = v
    return truncated


async def _stream_llm_with_timeout(
    *,
    messages: list[dict],
    tools: list[dict] | None = None,
    timeout: int,
) -> AsyncGenerator:
    """Bridge LLM stream through a queue so the whole operation respects a deadline."""
    queue: asyncio.Queue = asyncio.Queue()
    done = object()

    async def _pump() -> None:
        try:
            async for item in chat_completion_stream(messages=messages, tools=tools):
                await queue.put(item)
        except BaseException as exc:
            # 将异常封装后传入队列，让消费者能感知到 LLM 调用失败的原因
            await queue.put(exc)
        finally:
            await queue.put(done)

    pump_task = asyncio.create_task(_pump())
    deadline = asyncio.get_running_loop().time() + timeout
    try:
        while True:
            remaining = deadline - asyncio.get_running_loop().time()
            if remaining <= 0:
                raise asyncio.TimeoutError
            item = await asyncio.wait_for(queue.get(), timeout=remaining)
            if item is done:
                break
            if isinstance(item, BaseException):
                # _pump 将 LLM 异常传入队列，在此重新抛出
                raise item
            yield item
    finally:
        if not pump_task.done():
            pump_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await pump_task


async def _emit_error_with_trace(_emit, code: str, message: str) -> SSEEvent:
    await trace_manager.finish_trace(
        status="error",
        output_payload={"code": code, "message": message},
    )
    return _emit("error", {"code": code, "message": message})


def _tool_running_message(tool_name: str) -> str:
    mapping = {
        "get_weather": "正在查询天气...",
        "search_place": "正在搜索景点...",
        "calculate_route": "正在规划路线...",
        "search_flights": "正在搜索机票...",
        "search_hotels": "正在搜索酒店...",
    }
    return mapping.get(tool_name, f"正在调用 {tool_name}...")


def _tool_result_message(tool_name: str, result: dict) -> str:
    mapping = {
        "get_weather": "天气查询完成",
        "search_place": "景点搜索完成",
        "calculate_route": "路线规划完成",
        "search_flights": "机票搜索完成",
        "search_hotels": "酒店搜索完成",
    }
    if result.get("error"):
        return f"{mapping.get(tool_name, tool_name)}失败"
    if result.get("is_fallback"):
        return f"{mapping.get(tool_name, tool_name)}失败，已使用备用结果"
    return mapping.get(tool_name, f"{tool_name} 执行完成")


def _collect_places_from_messages(messages: list[dict]) -> list[dict]:
    """从工具调用的结果中收集景点坐标信息"""
    places = []
    for msg in messages:
        if msg.get("role") != "tool":
            continue
        content = msg.get("content", "")
        try:
            data = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict) and "pois" in data:
            for poi in data["pois"]:
                name = poi.get("name", "")
                if not name:
                    continue
                places.append({
                    "name": name,
                    "lng": poi.get("lng", 0),
                    "lat": poi.get("lat", 0),
                    "address": poi.get("address", "") or "",
                    "tel": (poi.get("tel") or "").strip(),
                    "category": poi.get("category", "") or "",
                })
    # 同名去重，保留首次（通常信息更全）
    deduped: list[dict] = []
    seen: set[str] = set()
    for p in places:
        key = p.get("name", "")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(p)
    return deduped
