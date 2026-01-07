from mars.graph.state import LeadState, ResearchPlan, ReportAndDecision
from dataclasses import dataclass
from typing import Any, Sequence, Optional, Literal, List

from langchain.tools import BaseTool
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AnyMessage, SystemMessage, HumanMessage, AIMessage
from langgraph.runtime import Runtime
from langgraph.store.base import BaseStore
from langgraph.types import Command, Overwrite

import uuid

from mars.prompt.load_prompt import load_prompt_text


@dataclass
class LeadContext:
    lead_model: Any
    subagent_model: Any
    citation_model: Any
    tools: Sequence[BaseTool]


PLAN_PROMPT = (load_prompt_text("mars.prompt.lead", "prompt.md") + "\n" +
               load_prompt_text("mars.prompt.lead", "plan_prompt.md"))

DELEGATE_PROMPT = (load_prompt_text("mars.prompt.lead", "prompt.md") + "\n" +
                   load_prompt_text("mars.prompt.lead", "delegate_prompt.md"))

FINALIZE_PROMPT = (load_prompt_text("mars.prompt.lead", "prompt.md") + "\n" +
                   load_prompt_text("mars.prompt.lead", "finalize_prompt.md"))

CITATION_PROMPT = load_prompt_text("mars.prompt.citation", "citation_prompt.md")


async def plan_node(
        state: LeadState,
        runtime: Runtime[LeadContext],
        config: RunnableConfig,
        *,
        store: Optional[BaseStore] = None,
):
    llm = runtime.context.lead_model
    replan_hint = state.replan_hint
    user_query = state.user_query

    try:
        planner = llm.with_structured_output(ResearchPlan, method="function_calling")
        plan: ResearchPlan = await planner.ainvoke([
            SystemMessage(content=PLAN_PROMPT),
            HumanMessage(content=f"{user_query}\nReplan hint (if any): {replan_hint or 'N/A'}")
        ])
    except Exception as e:
        raw = await llm.ainvoke([
            SystemMessage(content=PLAN_PROMPT),
            HumanMessage(content=f"{user_query}\nReplan hint (if any): {replan_hint or 'N/A'}")
        ])
        plan = ResearchPlan.model_validate_json(getattr(raw, "content", raw))

    if store is not None:
        user_id = config.get("configurable", {}).get("user_id", "anonymous")
        namespace = (str(user_id), "research_plans")
        store.put(
            namespace=namespace,
            key=str(uuid.uuid4()),
            value={
                "plan_version": state.plan_version + 1,
                "plan": plan,
                "user_query": user_query,
            },
            index=["user_query"]
        )

    return {
        "plan_version": state.plan_version + 1,
        "plan": plan,
        "replan_hint": None,  # consumed
    }


async def delegate_node(
        state: LeadState,
        runtime: Runtime[LeadContext],
        config: RunnableConfig,
) -> Command[Literal["plan", "delegate", "__end__"]]:
    base_llm = runtime.context.lead_model
    tools = list(runtime.context.tools or [])

    delegate_instruction = state.delegate_instruction
    delegator = base_llm.bind_tools(tools)

    if not state.messages:
        seed = [
            SystemMessage(content=DELEGATE_PROMPT),
            HumanMessage(
                content=f"User query:\n{state.user_query}\n\nPLAN:\n{state.plan}\n\nDelegate instruction (if any): {delegate_instruction or 'N/A'}"),
        ]
        ai_msg: AIMessage = await delegator.ainvoke(seed, config=config)
        return {
            "messages": Overwrite(seed + [ai_msg]),
            "iteration": state.iteration + 1,
        }

    ai_msg: AIMessage = await delegator.ainvoke(state.messages, config=config)
    return {
        "messages": [ai_msg],
        "iteration": state.iteration + 1,
    }


def render_messages(messages: List[AnyMessage]):
    parts = []
    for m in messages:
        role = m.type
        content = getattr(m, "content", "")
        parts.append(f"[{role}]\n{content}")
    return "\n\n".join(parts)


async def finalize_node(
        state: LeadState,
        runtime: Runtime["LeadContext"],
        config: RunnableConfig
) -> Command[Literal["plan", "__end__"]]:
    llm = runtime.context.lead_model

    decider = llm.with_structured_output(ReportAndDecision, method="function_calling")

    prior_synthesis = "\n".join(state.synthesis)
    try:
        resp: ReportAndDecision = await decider.ainvoke([
            SystemMessage(content=FINALIZE_PROMPT),
            HumanMessage(content=(
                f"User query: {state.user_query}\n\n"
                f"PLAN: {state.plan}\n\n"
                f"Research process (include tool results): {render_messages(state.messages)}\n\n"
                f"Prior synthesis: {prior_synthesis}\n"
                f"Current iteration: {state.iteration} - Max iterations: {state.max_iterations}"
            ))
        ], config=config)

        update: dict = {
            "synthesis": resp.synthesis,
            "replan_hint": resp.decision.replan_hint,
            "delegate_instruction": resp.decision.delegate_instruction
        }

        if resp.decision.action == "STOP":
            update["report"] = resp.report
            return Command(update=update, goto="citation")
        elif resp.decision.action == "REPLAN":
            return Command(update=update, goto="plan")
        elif resp.decision.action == "CONTINUE":
            update["messages"] = Overwrite([])
            return Command(update=update, goto="delegate")
        else:
            raise Exception("Unsupported action")
    except Exception as e:
        print(f"Error occured: {e}")


async def citation_node(
    state: LeadState,
    runtime: Runtime[LeadContext],
    config: RunnableConfig
):
    llm = runtime.context.citation_model

    report_text = state.report

    synthesis_text = "\n".join(state.synthesis)

    resp = await llm.ainvoke([
        SystemMessage(content=CITATION_PROMPT),
        HumanMessage(content=(
            f"<synthesized_text>\nReport without citation:\n{report_text}\n</synthesized_text>\n"
            f"Synthesis for citation:\n{synthesis_text}\n"
        ))
    ])

    final_text = resp.content if isinstance(resp, AIMessage) else str(resp)

    return {
        "report": final_text,
    }