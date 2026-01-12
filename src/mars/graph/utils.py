import json
from typing import Any, Iterable, Optional

from langchain_core.messages import AnyMessage, AIMessage, ToolMessage


def _last_nonempty_ai_text(messages: list[Any]) -> Optional[str]:
    last: Optional[str] = None

    for m in messages:
        if isinstance(m, AIMessage):
            if isinstance(m.content, str) and m.content.strip():
                last = m.content
            continue

        if isinstance(m, dict):
            m_type = (m.get("type") or m.get("role") or "").lower()
            if m_type in {"ai", "assistant", "aimessage"}:
                c = m.get("content")
                if isinstance(c, str) and c.strip():
                    last = c

    return last


def _tool_content_blocks_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text" and isinstance(item.get("text"), str):
                parts.append(item["text"])
            elif isinstance(item, str):
                parts.append(item)
        return "\n".join(parts)
    return str(content)


def _extract_subagent_final_text_from_tool_message(tm: ToolMessage) -> Optional[str]:
    raw_text = _tool_content_blocks_to_text(tm.content)

    try:
        payload = json.loads(raw_text)
        if isinstance(payload, dict) and isinstance(payload.get("messages"), list):
            return _last_nonempty_ai_text(payload["messages"])
    except Exception:
        pass

    return None


def compact_tool_messages_for_lead(messages: Iterable[AnyMessage]) -> list[AnyMessage]:
    out: list[AnyMessage] = []
    for m in messages:
        if isinstance(m, ToolMessage):
            final_text = _extract_subagent_final_text_from_tool_message(m)
            if final_text:
                out.append(
                    ToolMessage(
                        content=final_text,
                        tool_call_id=m.tool_call_id,
                        name=m.name,
                        id=getattr(m, "id", None),
                    )
                )
            else:
                raw = _tool_content_blocks_to_text(m.content)
                out.append(
                    ToolMessage(
                        content=(raw[:4000] + "\n...[truncated]...") if len(raw) > 4000 else raw,
                        tool_call_id=m.tool_call_id,
                        name=m.name,
                        id=getattr(m, "id", None),
                    )
                )
        else:
            out.append(m)
    return out
