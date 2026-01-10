import logging
from pathlib import Path
from typing import Literal, Any, cast

from langchain_community.vectorstores import FAISS, Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.vectorstores import VectorStore
from langchain_openai import OpenAIEmbeddings

from ..raptor.tree_structures import Node, RaptorTree
from ..settings import settings


logger = logging.getLogger(__name__)


class RaptorVectorStore:
    def __init__(
            self,
            embedding_model: Embeddings | None = None,
            store_type: Literal["faiss", "chroma"] | None = None,
            persist_directory: str | Path | None = None
    ):
        """Initialize the vector store manager.

        Args:
            embedding_model: LangChain embedding model.
            store_type: Type of vector store ("faiss" or "chroma").
            persist_directory: Directory for persisting the index.
        """
        if embedding_model is None:
            embedding_model = OpenAIEmbeddings(
                model=settings.embedding_model,
            )
        self.embedding_model = embedding_model

        self.store_type = store_type or settings.vector_store_type
        self.persist_directory = Path(persist_directory or settings.vector_store_path)

        self._vector_store: VectorStore | None = None

        logger.info(
            f"Initialized RaptorVectorStore: type={self.store_type}, "
            f"persist_dir={self.persist_directory}"
        )

    @property
    def vector_store(self) -> VectorStore | None:
        return self._vector_store

    @property
    def is_initialized(self) -> bool:
        return self._vector_store is not None

    def add_nodes(
            self,
            nodes: list[Node],
            **kwargs: Any
    ):
        """Add nodes to the vector store.

        Converts nodes to Documents and adds them to the index.

        Args:
            nodes: List of Node objects to add.
            **kwargs: Additional arguments for the vector store.
        """

        documents = [node.to_document() for node in nodes]
        self.add_documents(documents, **kwargs)

    def add_documents(
            self,
            documents: list[Document],
            **kwargs
    ) -> None:
        if not documents:
            logger.warning("No documents to add")
            return
        if self._vector_store is None:
            self._create_vector_store(documents)

        else:
            self._vector_store.add_documents(documents, **kwargs)

    def _create_vector_store(
            self,
            documents: list[Document]
    ) -> None:
        if self.store_type == "faiss":
            self._vector_store = FAISS.from_documents(
                documents,
                embedding=self.embedding_model
            )
        elif self.store_type == "chroma":
            self.persist_directory.mkdir(parents=True, exist_ok=True)
            self._vector_store = Chroma.from_documents(
                documents,
                self.embedding_model,
                persist_directory=str(self.persist_directory)
            )
        else:
            raise ValueError("Unknown store type")

        logger.info(f"Created {self.store_type} vector store")


    def add_tree(self, tree: RaptorTree):
        """Add all nodes from a RAPTOR tree to the vector store.

        This implements the Collapsed Tree strategy: all nodes
        (leaves + summaries) are indexed together.

        Args:
            tree: RaptorTree to index.
        """
        logger.info(f"Adding tree with {tree.total_nodes} nodes to vector store")

        all_nodes = tree.collapse()

        self.add_nodes(all_nodes)

    def similarity_search(
            self,
            query: str,
            k: int | None = None,
            **kwargs
    ) -> list[Document]:
        """Search for similar documents.

        Args:
            query: Query string.
            k: Number of results to return. Defaults to settings.top_k.
            **kwargs: Additional search arguments.

        Returns:
            List of similar Documents.

        Raises:
            ValueError: If vector store is not initialized.
        """
        if not self.is_initialized:
            raise ValueError("Vector store is not initialized!")
        k = k or settings.top_k

        return cast(list[Document], self._vector_store.similarity_search(query, k=k, **kwargs))

    def similarity_search_with_score(
            self,
            query: str,
            k: int | None = None,
            **kwargs
    ) -> list[tuple[Document, float]]:
        if not self.is_initialized:
            raise ValueError("Vector store is not initialized")
        k = k or settings.top_k

        return cast(
            list[tuple[Document, float]],
            self.vector_store.similarity_search_with_score(query, k=k, **kwargs)
        )

    def as_retriever(
            self,
            search_type: str = "similarity",
            search_kwargs: dict[str, Any] | None = None
    ):
        """Get a LangChain Retriever interface.

        Args:
            search_type: Type of search ("similarity", "mmr", etc.).
            search_kwargs: Additional search arguments.

        Returns:
            VectorStoreRetriever instance.
        """
        if not self.is_initialized:
            raise ValueError("Vector store is not initialized!")
        search_kwargs = search_kwargs or {"k": settings.top_k}

        return self._vector_store.as_retriever(
            search_type=search_type,
            search_kwargs=search_kwargs
        )

    def save(
            self,
            path: str | Path | None = None
    ):
        """Save the vector store to disk.

        Args:
            path: Path to save to. Defaults to persist_directory.
        """
        if not self.is_initialized:
            raise ValueError("Vector store is not initialized!")

        save_path = Path(path) if path else self.persist_directory
        save_path.mkdir(parents=True, exist_ok=True)

        if self.store_type == "faiss":
            self._vector_store.save_local(str(save_path))
            logger.info(f"Saved FAISS index to {save_path}")
        elif self.store_type == "chroma":
            # Chroma persists automatically
            logger.info(f"Chroma index persisted to {save_path}")

    def load(
            self,
            path: str | Path | None = None
    ):
        """Load a vector store from disk.

        Args:
            path: Path to load from. Defaults to persist_directory.
        """
        load_path = Path(path) if path else self.persist_directory

        if self.store_type == "faiss":
            if not (load_path / "index.faiss").exists():
                raise FileNotFoundError(f"No FAISS index found at {load_path}")

            self._vector_store = FAISS.load_local(
                str(load_path),
                self.embedding_model,
                allow_dangerous_deserialization=True,
            )
            logger.info(f"Loaded FAISS index from {load_path}")

        elif self.store_type == "chroma":
            self._vector_store = Chroma(
                persist_directory=str(load_path),
                embedding_function=self.embedding_model,
            )
            logger.info(f"Loaded Chroma index from {load_path}")

    @classmethod
    def from_tree(
        cls,
        tree: RaptorTree,
        **kwargs: Any
    ) -> "RaptorVectorStore":
        """Create a vector store from a RAPTOR tree.

        Args:
            tree: RaptorTree to index.
            **kwargs: Additional arguments for RaptorVectorStore.

        Returns:
            Initialized RaptorVectorStore with tree indexed.
        """
        store = cls(**kwargs)
        store.add_tree(tree)
        return store