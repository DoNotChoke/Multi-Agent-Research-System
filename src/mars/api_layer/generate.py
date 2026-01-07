from typing import AsyncGenerator
from langchain_core.messages import AIMessage

async def generate_stream(
        graph,
        question: str
) -> AsyncGenerator[str, None]:
    messages = []
    ai_msg = await graph.ainvoke(question)
    messages.append(ai_msg)

    if isinstance(ai_msg, AIMessage) and hasattr(ai_msg, "tool_calls"):
        for tool_call in ai_msg.tool_calls:
            selected_tool = {tool.name: tool}[tool_call["name"].lower()]
            tool_msg = await selected_tool.ainvoke(tool_call)
            messages.append(tool_msg)
