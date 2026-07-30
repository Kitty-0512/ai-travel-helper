"""Extract structured travel preferences from user text via LLM."""

from __future__ import annotations

import json
import logging
import re

from app.llm.deepseek import chat_completion_simple
from app.memory.models import ExtractedPreferences

logger = logging.getLogger(__name__)

EXTRACTOR_PROMPT = """你是旅行偏好抽取器。从用户话语中提取长期旅行偏好，只输出 JSON。

输出格式：
{
  "style": "slow|fast|balanced|null",
  "interests": ["美食", "人文"],
  "dislike": ["museum"],
  "budget": "经济|舒适|高档|null",
  "transport": "火车|飞机|自驾|null",
  "constraints": ["不喜欢早起"]
}

规则：
1. 只提取明确表达的偏好；没有的字段用 null 或 []
2. dislike / interests 用简短英文或中文关键词均可
3. 不要编造用户没说的内容
4. 只输出 JSON，不要 markdown
"""


async def extract_preferences(user_text: str) -> ExtractedPreferences:
    text = (user_text or "").strip()
    if not text:
        return ExtractedPreferences()

    # Fast path for obvious preference statements without calling LLM when short
    try:
        messages = [
            {"role": "system", "content": EXTRACTOR_PROMPT},
            {"role": "user", "content": text},
        ]
        raw = await chat_completion_simple(messages, max_tokens=400)
        return _parse_extracted(raw)
    except Exception as e:
        logger.warning("[Memory] extract failed: %s", e)
        return _heuristic_extract(text)


def _parse_extracted(raw: str) -> ExtractedPreferences:
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        text = match.group(0)
    data = json.loads(text)
    style = data.get("style")
    if style in (None, "null", ""):
        style = None
    budget = data.get("budget")
    if budget in (None, "null", ""):
        budget = None
    transport = data.get("transport")
    if transport in (None, "null", ""):
        transport = None
    return ExtractedPreferences(
        style=style,
        interests=[str(x) for x in (data.get("interests") or []) if x],
        dislike=[str(x) for x in (data.get("dislike") or []) if x],
        budget=budget,
        transport=transport,
        constraints=[str(x) for x in (data.get("constraints") or []) if x],
    )


def _heuristic_extract(text: str) -> ExtractedPreferences:
    pref = ExtractedPreferences()
    if "慢节奏" in text or "不赶" in text:
        pref.style = "slow"
    if "博物馆" in text and ("不喜欢" in text or "不要" in text or "别" in text):
        pref.dislike.append("museum")
    if "美食" in text and ("喜欢" in text or "想" in text):
        pref.interests.append("美食")
    if "人文" in text:
        pref.interests.append("人文")
    return pref
