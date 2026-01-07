from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langchain.agents.middleware import wrap_tool_call


from typing import Dict, Literal, Any
import inspect

@wrap_tool_call
async def handle_tool_error(request, handler):
    """Handle tool execution errors with custom messages."""
    try:
        result = handler(request)
        if inspect.isawaitable(result):
            result = await result
        return result
    except Exception as e:
        tool_call = getattr(request, "tool_call", {}) or {}
        tool_call_id = tool_call.get("id", "unknown")
        tool_name = tool_call.get("name", "unknown_tool")

        return ToolMessage(
            content=(
                f"[TOOL_ERROR] Tool '{tool_name}' failed: {type(e).__name__}: {e}. "
                "You may retry with different args or skip this tool and continue."
            ),
            tool_call_id=tool_call_id,
        )

def make_run_agent_tool(tool_registry: Dict[str, BaseTool], model: Any):
    @tool
    async def run_agent(name: str, tools: list[str], prompt: str):
        """Initialize subagent to accomplish a task.
        :arg name: name of the subagent (`web_researcher` for web research subagent)
        :arg tools: list of tools to use (Just provide tool's name)
        :arg prompt: prompt about instruction and task
        """

        unknown = [t for t in tools if t not in tool_registry]
        if unknown:
            raise ValueError(f"Unknown tools requested: {unknown}. Allowed={list(tool_registry.keys())}")