from langgraph.constants import START, END
from langgraph.graph import StateGraph

from mars.graph.node import LeadContext, delegate_node, plan_node, finalize_node, citation_node
from mars.graph.state import LeadState

from typing import Sequence, Any, Optional
from langchain.tools import BaseTool
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.base import BaseStore
from langgraph.prebuilt import ToolNode, tools_condition


def build_lead_orchestrator(
        *,
        lead_model: Any,
        subagent_model: Any,
        citation_model: Any,
        tools: Sequence[BaseTool],
        checkpointer: Optional[Any] = None,
        store: Optional[BaseStore] = None,
):
    builder = StateGraph(LeadState, context_schema=LeadContext)
    builder.add_node("plan", plan_node)
    builder.add_node("delegate", delegate_node)
    builder.add_node("finalize", finalize_node)
    builder.add_node("tools", ToolNode(tools=tools, handle_tool_errors=True))
    builder.add_node("citation", citation_node)

    builder.add_edge(START, "plan")
    builder.add_edge("plan", "delegate")
    builder.add_conditional_edges(
        "delegate",
        tools_condition,
        {"tools": "tools", "__end__": "finalize"},
    )
    builder.add_edge("tools", "delegate")
    builder.add_edge("citation", END)

    app = builder.compile(
        checkpointer=checkpointer or InMemorySaver(),
        store=store,
    )

    context = LeadContext(
        lead_model=lead_model,
        subagent_model=subagent_model,
        citation_model=citation_model,
        tools=tools
    )
    return app, context
