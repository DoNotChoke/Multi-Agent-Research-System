from langchain_openai import ChatOpenAI

from mars.graph.graph import build_lead_orchestrator
from mars.graph.state import LeadState
from mars.graph.tools import get_available_tools
from mars.tools.lead_tools.run_agent import make_run_agent_tool


async def main():
    tools = await get_available_tools()
    tool_registry = {t.name: t for t in tools}

    run_agent_tool = make_run_agent_tool(tool_registry, model="gpt-5-mini")

    lead_model = ChatOpenAI(model="gpt-5")
    subagent_model = ChatOpenAI(model="gpt-5-mini")
    citation_model = ChatOpenAI(model="gpt-5-nano")

    lead_tools = tools + [run_agent_tool]

    app, context = build_lead_orchestrator(
        lead_model=lead_model,
        subagent_model=subagent_model,
        citation_model=citation_model,
        tools=lead_tools,
    )

    initial_state = LeadState(
        user_query="Research how Uber implement their kafka infrastructure, especially how they replica kafka.").model_dump(
        exclude_none=True)
    config = {"configurable": {"thread_id": "t1", "user_id": "u1"}, "recursion_limit": 50}

    final = await app.ainvoke(initial_state, config=config, context=context)
    print(final)