import copy
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, cast

import tiktoken
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from .clustering import RaptorClustering
from .summarization import SummarizationChain
from .tree_structures import Node, RaptorTree
from ..settings import settings

logger = logging.getLogger(__name__)


class TreeBuilder:
    """Builds RAPTOR hierarchical tree from document chunks.

    This class orchestrates the recursive tree building process:
    1. Create leaf nodes from chunks
    2. Generate embeddings for nodes
    3. Cluster nodes using RAPTOR clustering
    4. Summarize each cluster to create parent nodes
    5. Repeat until a single root cluster remains
    """

    def __init__(
        self,
        embedding_model: Embeddings | None = None,
        summarization_chain: SummarizationChain | None = None,
        clustering: RaptorClustering | None = None,
        tokenizer: tiktoken.Encoding | None = None,
        max_tokens: int | None = None,
        num_layers: int | None = None,
        summarization_length: int | None = None,
        embedding_model_name: str = "default",
        use_multithreading: bool = True,
    ) -> None:
        """Initialize the tree builder.

        Args:
            embedding_model: LangChain embedding model.
            summarization_chain: Summarization chain for creating summaries.
            clustering: Clustering algorithm instance.
            tokenizer: Tiktoken tokenizer for token counting.
            max_tokens: Maximum tokens per chunk.
            num_layers: Maximum number of tree layers.
            summarization_length: Max tokens for summaries.
            embedding_model_name: Name key for storing embeddings.
            use_multithreading: Enable parallel processing.
        """
        # Initialize embedding model
        if embedding_model is None:
            self.embedding_model: Embeddings = OpenAIEmbeddings(
                model=settings.embedding_model,
            )
        else:
            self.embedding_model = embedding_model

        # Initialize other components
        self.summarization_chain = summarization_chain or SummarizationChain()
        self.clustering = clustering or RaptorClustering()

        # Configuration
        self.tokenizer = tokenizer or tiktoken.get_encoding("cl100k_base")
        self.max_tokens = max_tokens or settings.max_tokens
        self.num_layers = num_layers or settings.num_layers
        self.summarization_length = summarization_length or settings.summarization_length
        self.embedding_model_name = embedding_model_name
        self.use_multithreading = use_multithreading

        logger.info(
            f"Initialized TreeBuilder: max_tokens={self.max_tokens}, "
            f"num_layers={self.num_layers}, "
            f"summarization_length={self.summarization_length}"
        )
    
    def _count_tokens(self, text: str) -> int:
        return len(self.tokenizer.encode(text))
    
    def _create_embedding(self, text: str) -> list[float]:
        return cast(list[float], self.embedding_model.embed_query(text))
    
    def _create_node(
            self,
            index: int,
            text: str,
            level: int = 0,
            children: set[int] | None = None 
    ) -> Node:
        embedding = self._create_embedding(text)

        node = Node(
            text=text,
            index=index,
            level=level,
            children=children or set(),
            embeddings={self.embedding_model_name: embedding},
        )

        return node
    
    def create_leaf_node(
            self,
            chunks: list[str] | list[Document]
    ) -> dict[int, Node]:
        """Create leaf nodes from text chunks.

        Args:
            chunks: List of text strings or Documents.

        Returns:
            Dictionary mapping indices to leaf nodes.
        """
        logger.info(f"Creating {len(chunks)} leaf nodes")

        # Convert Documents to strings if needed
        texts = [chunk.page_content if isinstance(chunk, Document) else chunk for chunk in chunks]

        if self.use_multithreading:
            return self._create_leaf_nodes_parallel(texts)
        else:
            return self._create_leaf_nodes_sequential(texts)

    def _create_leaf_nodes_sequential(
            self,
            texts: list[str],
    ) -> dict[int, Node]:
        leaf_nodes: dict[int, Node] = {}

        for index, text in enumerate(texts):
            node = self._create_node(index=index, text=text, level=0)
            leaf_nodes[index] = node

        return leaf_nodes
    
    def _create_leaf_nodes_parallel(
            self,
            texts: list[str]
    ) -> dict[int, Node]:
        leaf_nodes: dict[int, Node] = {}

        with ThreadPoolExecutor() as executor:
            future_to_index = {
                executor.submit(self._create_node, index, text, 0): index
                for index, text in enumerate(texts)
            }

            for future in as_completed(future_to_index):
                index = future_to_index[future]
                try:
                    node = future.result()
                    leaf_nodes[index] = node
                except Exception as e:
                    logger.error(f"Error creating node {index}: {e}")
                    raise

        return leaf_nodes
    
    def _summarize_cluster(
            self,
            nodes: list[Node]
    ) -> str:
        texts = [node.text for node in nodes]
        return self.summarization_chain.summarize(texts)
    
    def _build_layer(
            self,
            current_nodes: dict[int, Node],
            layer: int,
            next_index: int
    ) -> tuple[dict[int, Node], int]:
        """Build a single layer of the tree.

        Args:
            current_nodes: Nodes at the current layer.
            layer: Current layer number.
            next_index: Next available node index.

        Returns:
            Tuple of (new layer nodes, next index).
        """
        logger.info(f"Building layer {layer + 1}")

        node_list = list(current_nodes.values())

        if len(node_list) <= self.clustering.reduction_dimension + 1:
            logger.info(
                f"Cannot create more layers: only {len(node_list)} nodes. "
                f"Stopping at layer {layer}."
            )
            return {}, next_index
        
        clusters = self.clustering.cluster_nodes(
            node_list,
            self.embedding_model_name
        )

        logger.info(f"Created {len(clusters)} clusters at layer {layer + 1}")

        new_layer_nodes: dict[int, Node] = {}

        for cluster in clusters:
            if not cluster:
                continue
            summary = self._summarize_cluster(cluster)

            children_indices = {node.index for node in cluster}
            parent_node = self._create_node(
                index=next_index,
                text=summary,
                level=layer + 1,
                children=children_indices
            )

            new_layer_nodes[next_index] = parent_node

            logger.debug(
                f"Created node {next_index} at layer {layer + 1} "
                f"with {len(children_indices)} children"
            )

            next_index += 1

        return new_layer_nodes, next_index
    
    def build_tree(
            self,
            chunks: list[str] | list[Document]
    ) -> RaptorTree:
        """Build the complete RAPTOR tree from chunks.

        Args:
            chunks: List of text chunks or Documents.

        Returns:
            Complete RaptorTree structure.
        """
        logger.info(f"Building RAPTOR tree from {len(chunks)} chunks")

        leaf_nodes = self.create_leaf_node(chunks)
        logger.info(f"Created {len(leaf_nodes)} leaf nodes")

        # Initialize tree structure
        all_nodes = copy.deepcopy(leaf_nodes)
        layer_to_nodes: dict[int, list[Node]] = {0: list(leaf_nodes.values())}

        current_level_nodes = leaf_nodes
        next_index = len(leaf_nodes)

        for layer in range(self.num_layers):
            new_layer_nodes, next_index = self._build_layer(
                current_level_nodes,
                layer,
                next_index
            )

            if not new_layer_nodes:
                break

            layer_to_nodes[layer + 1] = list(new_layer_nodes.values())
            all_nodes.update(new_layer_nodes)
            current_level_nodes = new_layer_nodes
        
        tree = RaptorTree(
            all_nodes=all_nodes,
            root_nodes=current_level_nodes,
            leaf_nodes=leaf_nodes,
            num_layers=len(layer_to_nodes),
            layer_to_nodes=layer_to_nodes,
        )

        logger.info(f"Built tree with {tree.total_nodes} total nodes, " f"{tree.num_layers} layers")

        return tree

    def build_from_documents(
        self,
        documents: list[Document],
    ) -> RaptorTree:
        """Build tree from LangChain Documents.

        Args:
            documents: List of LangChain Document objects.

        Returns:
            Complete RaptorTree structure.
        """
        return self.build_tree(documents)
    
    def build_from_text(
        self,
        text: str,
    ) -> RaptorTree:
        """Build tree from raw text.

        Splits the text into chunks first, then builds the tree.

        Args:
            text: Raw text string.

        Returns:
            Complete RaptorTree structure.
        """
        from ..ingestion import create_chunks_from_text

        chunks = create_chunks_from_text(
            text,
            chunk_size=self.max_tokens,
        )

        return self.build_tree(chunks)
    

def build_raptor_tree(
    chunks: list[str] | list[Document],
    **kwargs: Any,
) -> RaptorTree:
    """Convenience function to build a RAPTOR tree.

    Args:
        chunks: List of text chunks or Documents.
        **kwargs: Additional arguments for TreeBuilder.

    Returns:
        Complete RaptorTree structure.
    """
    builder = TreeBuilder(**kwargs)
    return builder.build_tree(chunks)