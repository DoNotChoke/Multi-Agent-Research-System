import asyncio

from langchain_openai import ChatOpenAI

from mars.graph.graph import build_lead_orchestrator
from mars.graph.state import LeadState
from mars.graph.tools import get_available_tools
from mars.tools.lead_tools.run_agent import make_run_agent_tool


async def main():
    tools = await get_available_tools() # tools
    tool_registry = {t.name: t for t in tools}

    run_agent_tool = make_run_agent_tool(tool_registry, model="gpt-5-mini") # tool to make subagent

    lead_model = ChatOpenAI(model="gpt-5", streaming=True)
    subagent_model = ChatOpenAI(model="gpt-5-mini", streaming=True)
    citation_model = ChatOpenAI(model="gpt-5-nano", streaming=True)

    lead_tools = tools + [run_agent_tool]

    app, context = build_lead_orchestrator(
        lead_model=lead_model,
        subagent_model=subagent_model,
        citation_model=citation_model,
        tools=lead_tools,
    )

    initial_state = LeadState(
        user_query="In 1.58-bit large language models, does the performance–efficiency advantage of native 1-bit training (BitNet trained from scratch) over distillation-based 1-bit adaptation (BitNet Distillation) persist when simultaneously scaling model size to at least 7B parameters, extending context length to 32k tokens or beyond, and increasing reliance on long chain-of-thought reasoning, or do the two approaches converge to equivalent solutions in terms of representation, optimization dynamics, numerical robustness, and energy efficiency once continued pre-training, attention-based distillation, and hardware-aware inference kernels are fully accounted for, and if they do not converge, what does this divergence imply about the existence of a fundamentally different scaling law and representational limit for ternary (1.58-bit) transformers compared to full-precision LLMs?"
                   "You should retrieve information from documents.").model_dump(
        exclude_none=True)
    config = {"configurable": {"thread_id": "t1", "user_id": "u1"}, "recursion_limit": 50}

    final = await app.ainvoke(initial_state, config=config, context=context)
    print(final)

if __name__ == '__main__':
    asyncio.run(main())