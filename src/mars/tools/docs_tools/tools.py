from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

from dotenv import load_dotenv

from mcp.shared.exceptions import McpError
from mcp.types import ErrorData, INVALID_PARAMS, INTERNAL_ERROR

from fastmcp import FastMCP

from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore

from .io import (
    DocsRetrieveArgs,
    DocsRetrieveResult,
    RetrievedQuery,
    RetrievedHit,
    DocumentWire
)
from .raptor.retrieval.vector_store import RaptorVectorStore

logger = logging.getLogger(__name__)
load_dotenv()


def json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def build_chat_filter(chat_id: str) -> dict[str, Any]:
    """
        Build a Qdrant payload filter that matches exact chat_id.
        Qdrant filtering uses structured conditions; simplest is exact match on a payload key. :contentReference[oaicite:2]{index=2}
    """
    return {
        "must": [
            {
                "key": "chat_id",
                "match": {"value": chat_id},
            }
        ]
    }


def merge_qdrant_filters(base: Optional[dict[str, Any]], extra: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """
    Merge two Qdrant filter dicts by concatenating 'must' lists (best-effort).
    If one is None, return the other.
    """
    if base is None:
        return extra
    if extra is None:
        return base

    merged = dict(base)
    merged_must = list(merged.get("must") or [])
    extra_must = list(extra.get("must") or [])
    merged["must"] = merged_must + extra_must
    # NOTE: we deliberately do not attempt deep merge for should/must_not etc.
    return merged


def build_vector_store() -> QdrantVectorStore:
    qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
    qdrant_api_key = os.getenv("QDRANT_API_KEY") or None
    collection_name = os.getenv("QDRANT_COLLECTION", "raptor_docs")

    embedding_model = os.getenv("EMBEDDING_MODEL") or "text-embedding-3-small"
    embeddings = OpenAIEmbeddings(model=embedding_model)

    vs = QdrantVectorStore.from_existing_collection(
        collection_name=collection_name,
        embedding=embeddings,
        url=qdrant_url,
        api_key=qdrant_api_key,
        prefer_grpc=os.getenv("QDRANT_PREFER_GRPC", "true").lower() in ("1", "true", "yes"),
    )
    return vs


def docs_retrieve_impl(args: DocsRetrieveArgs, vector_store: RaptorVectorStore) -> DocsRetrieveResult:
    f1 = build_chat_filter(args.chat_id) if args.chat_id else None
    f = merge_qdrant_filters(args.qdrant_filter, f1)

    if args.include_scores:
        pairs = vector_store.similarity_search_with_score(args.query, k=args.k, filter=f)
        hits: list[RetrievedHit] = []
        for idx, (doc, score) in enumerate(pairs, start=1):
            doc = doc if isinstance(doc, Document) else doc
            metadata = dict(doc.metadata or {}) if args.include_metadata else {}
            hits.append(
                RetrievedHit(
                    document=DocumentWire(page_content=doc.page_content, metadata=metadata),
                    score=float(score) if score is not None else None,
                    rank=idx,
                )
            )

    else:
        docs = vector_store.similarity_search(args.query, k=args.k, filter=f)
        hits: list[RetrievedHit] = []
        for idx, doc in enumerate(docs, start=1):
            metadata = dict(doc.metadata or {}) if args.include_metadata else {}
            hits.append(
                RetrievedHit(
                    document=DocumentWire(page_content=doc.page_content, metadata=metadata),
                    score=None,
                    rank=idx,
                )
            )
    return DocsRetrieveResult(
        retrieved_at=datetime.now(timezone.utc),
        query=RetrievedQuery(q=args.query, k=args.k, chat_id=args.chat_id),
        results=hits,
    )


def create_fastmcp_app() -> FastMCP:
    """
    FastMCP server exposing:
    - docs_retrieve: returns structured retrieval hits (Document-like objects)
    - docs_answer: optional RAG answer generation on top of retrieved context
    """
    mcp = FastMCP(name="docs-mcp-server")

    try:
        vector_store = build_vector_store()
    except Exception as e:
        raise RuntimeError(f"Failed to initialize QdrantVectorStore: {e}")
    
    @mcp.tool(
        name="docs_retrieve",
        description=(
            "Retrieve relevant documents from internal data source." \
            "Support optional chat_id for seperated session."
        )
    )
    def tool_docs_retrieve(
        query: str,
        k: int = 5,
        chat_id: str | None = None,
        qdrant_filter: dict[str, Any] | None = None,
        include_metadata: bool = True,
        include_scores: bool = True
    ) -> str:
        try:
            args = DocsRetrieveArgs(
                query=query,
                k=k,
                chat_id=chat_id,
                qdrant_filter=qdrant_filter,
                include_metadata=include_metadata,
                include_scores=include_scores,
            )
            result = docs_retrieve_impl(args, vector_store=vector_store)
            return json_text(result.model_dump(mode="json"))

        except McpError:
            raise
        except Exception as e:
            raise McpError(ErrorData(code=INTERNAL_ERROR, message=str(e)))

    @mcp.prompt(
        name="docs_retrieve",
        description=(
            "Retrieve relevant documentation passages from the indexed corpus."
        )
    )
    def prompt_docs_retrieve(query: str) -> str:
        return f"Retrieve documentation passages relevant to: {query}"

    return mcp


def main():
    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8010"))

    mcp = create_fastmcp_app()
    mcp.run(transport="http", host=host, port=port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()
