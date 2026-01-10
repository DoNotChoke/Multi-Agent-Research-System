from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool
from langchain.agents.middleware import wrap_tool_call

from typing import Dict, Any, Optional
import inspect

from mars.prompt.load_prompt import load_prompt_text


async def run_researcher(
        *,
        worker_graph: Any,
        prompt: str,
        recursion_limit: int = 25,
        config: Optional[dict[str, Any]] = None,
):
    inputs = {"messages": [{"role": "user", "content": prompt}]}
    run_config: dict[str, Any] = {"recursion_limit": recursion_limit}

    if config:
        run_config.update(config)
    state = await worker_graph.ainvoke(input=inputs, config=run_config)
    return state


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

        tools_list = [tool_registry[t] for t in tools]

        system_prompt = load_prompt_text("mars.prompt.worker", file_name="prompt.md")

        graph = create_agent(
            model=model,
            tools=tools_list,
            name=name,
            system_prompt=system_prompt,
            # response_format=ProviderStrategy(WebResearchReport),
            middleware=[handle_tool_error],
        )

        resp = await run_researcher(
            worker_graph=graph,
            prompt=prompt,
            recursion_limit=50
        )
        return resp

    return run_agent
