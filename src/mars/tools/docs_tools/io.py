from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict

class DocsRetrieveArgs(BaseModel):
    """Arguments for docs_retrieve tool."""
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, description="Query for retrieval")
    k: int = Field(default=5, ge=1, le=50, description="Top-K documents to return")

    chat_id: Optional[str] = Field(default=None, description="Optional chat/session id for filtering")

    qdrant_filter: Optional[dict[str, Any]] = Field(
        default=None,
        description=(
            "Optional Qdrant filter in JSON form (e.g. {'must': [{'key': 'chat_id', 'match': {'value': '...'}}]})."
        ),
    )

    include_metadata: bool = Field(default=True, description="Return metadata in each hit")
    include_scores: bool = Field(default=True, description="Return similarity scores")


class RetrievedQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str = Field(min_length=1, description="Query string")
    k: int = Field(default=5, ge=1, le=50, description="Top-K requested")
    chat_id: Optional[str] = Field(default=None, description="Applied chat filter if any")


class DocumentWire(BaseModel):
    model_config = ConfigDict(extra="forbid")

    page_content: str = Field(default="", description="Document text content")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Document metadata/payload")

class RetrievedHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document: DocumentWire
    score: Optional[float] = None
    rank: Optional[int] = Field(default=None, ge=1)


class DocsRetrieveResult(BaseModel):
    """Structured output for docs_retrieve tool"""
    model_config = ConfigDict(extra="forbid")

    retrieved_at: datetime
    query: RetrievedQuery
    results: list[RetrievedHit]