from __future__ import annotations

from typing import Any, Optional

from pathlib import Path

from langchain_core.documents import Document
from langchain_qdrant import QdrantVectorStore
from langchain_core.embeddings import Embeddings

from qdrant_client import QdrantClient

from .vector_store import RaptorVectorStore

import logging

logger = logging.getLogger(__name__)

class QdrantRaptorVectorStore(RaptorVectorStore):
    def __init__(
            self,
            *,
            collection_name: str = "raptor_docs",
            url: str = "http://localhost:6333",
            api_key: Optional[str] = None,
            prefer_grpc: bool = True,
            embedding_model: Embeddings | None = None,
            persist_directory: str | Path | None = None,  # giữ để tương thích signature
            **kwargs: Any,
    ) -> None:
        super().__init__(
            embedding_model=embedding_model,
            store_type="faiss",
            persist_directory=persist_directory
        )

        self.collection_name = collection_name
        self.url = url
        self.api_key = api_key
        self.prefer_grpc = prefer_grpc

        self.client = QdrantClient(url=self.url, api_key=self.api_key, prefer_grpc=self.prefer_grpc)

        logger.info(
            "Initialized QdrantRaptorVectorStore: "
            f"collection={self.collection_name}, url={self.url}, prefer_grpc={self.prefer_grpc}"
        )

    def _create_vector_store(
            self,
            documents: list[Document]
    ) -> None:
        self._vector_store = QdrantVectorStore.from_documents(
            documents=documents,
            embedding=self.embedding_model,
            url=self.url,
            api_key=self.api_key,
            prefer_grpc=self.prefer_grpc,
            collection_name=self.collection_name,
        )
        logger.info(f"Created Qdrant collection and inserted {len(documents)} documents")

    def load(
            self,
            path: str | Path | None = None
    ):
        self._vector_store = QdrantVectorStore.from_existing_collection(
            embedding=self.embedding_model,
            collection_name=self.collection_name,
            url=self.url,
            api_key=self.api_key,
            prefer_grpc=self.prefer_grpc,
        )
        logger.info(f"Connected to existing Qdrant collection: {self.collection_name}")

    def save(
            self,
            path: str | Path | None = None
    ):
        if not self.is_initialized:
            raise ValueError("Vector store is not initialized!")
        logger.info("Qdrant persists server-side; save() is a no-op")

    def add_documents(
            self,
            documents: list[Document],
            **kwargs
    ) -> None:
        if not documents:
            logger.warning("No documents to add")
            return

        if self._vector_store is None:
            self._create_vector_store(documents=documents)
            return

        self._vector_store.add_documents(documents=documents, **kwargs)