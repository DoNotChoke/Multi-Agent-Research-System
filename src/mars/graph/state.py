from pydantic import BaseModel, Field
from typing import Literal, Optional, Annotated
from operator import add
import uuid

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages

from typing import List


class ResearchTask(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    objective: str = ""


class ResearchPlan(BaseModel):
    goal: str
    tasks: list[ResearchTask] = Field(default_factory=list)
    stop_criteria: list[str] = Field(default_factory=list)


class DelegateDecision(BaseModel):
    action: Literal["CONTINUE", "REPLAN", "STOP"]
    rationale: str
    replan_hint: Optional[str] = None
    delegate_instruction: Optional[str] = None


class ReportAndDecision(BaseModel):
    synthesis: List[str] = Field(default_factory=list)
    report: Optional[str] = None
    decision: DelegateDecision


class LeadState(BaseModel):
    user_query: str
    iteration: int = 0
    max_iterations: int = 3

    plan_version: int = 0
    plan: Optional[ResearchPlan] = None

    messages: Annotated[List[AnyMessage], add_messages] = Field(default_factory=list)

    report: Optional[str] = None

    synthesis: Annotated[List[str], add] = Field(default_factory=list)

    replan_hint: Optional[str] = None
    delegate_instruction: Optional[str] = None
