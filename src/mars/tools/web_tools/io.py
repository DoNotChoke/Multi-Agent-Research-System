from pydantic import BaseModel, Field, ConfigDict

from typing import Optional
from datetime import datetime


class WebSearchArgs(BaseModel):
    """Arguments for web_search tool"""
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1, description="Search query")
    k: int = Field(default=5, ge=1, le=50, description="Maximum number of results to return")
    recency_days: Optional[int] = Field(
        default=None,
        ge=0,
        description="Optional recency filter in days"
    )
    domains: Optional[list[str]] = Field(
        default=None,
        description="Optimal domain allowed list; results outside are filtered out."
    )


class SearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str = Field(min_length=1, description="Query string")
    recency_days: Optional[int] = Field(default=None, ge=0, description="Number of days to search for")
    domains: Optional[list[str]] = Field(default=None, description="Domains to search for")
    k: int = Field(default=5, ge=1, le=50, description="Maximum number of search results returned.")


class SearchHit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    url: str = Field(min_length=1)
    title: Optional[str] = None
    snippet: Optional[str] = None
    rank: Optional[int] = Field(default=None, ge=1)


class WebSearchResult(BaseModel):
    """Structured output for web_search tool"""
    model_config = ConfigDict(extra="forbid")

    retrieved_at: datetime
    query: SearchQuery
    results: list[SearchHit]


class WebFetchArgs(BaseModel):
    """Arguments for web_fetch MCP tool."""
    model_config = ConfigDict(extra="forbid")

    url: str = Field(description="URL to fetch from")
    start_index: int = Field(default=0, ge=0, description="Start character index")
    max_length: int = Field(default=5000, ge=1, le=200000, description="Max characters to return")
    raw: bool = Field(default=False, description="If True, do not simplify HTML to markdown")
    timeout_s: float = Field(default=30.0, ge=1.0, le=180.0, description="Fetch timeout seconds")


class RawDocument(BaseModel):
    """Document snapshot for storing."""
    model_config = ConfigDict(extra="forbid")

    content_type: Optional[str] = Field(default=None, description="e.g., text/html, application/pdf")
    text: str = Field(default="", description="Text extracted from docs (or raw text).")
    raw: Optional[bytes] = Field(default=None, description="Raw bytes if needed (pdf/html).")
    sha256: Optional[str] = Field(default=None, description="Hash for dedupe/integrity.")


class WebFetchResult(BaseModel):
    """Structured output for web_fetch."""
    model_config = ConfigDict(extra="forbid")

    retrieved_at: datetime
    url: str
    document: RawDocument
    truncated: bool
    next_start_index: Optional[int] = None
    note: Optional[str] = None
