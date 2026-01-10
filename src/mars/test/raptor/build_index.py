from mars.tools.docs_tools.raptor import DocumentIngestion, TreeBuilder
from mars.tools.docs_tools.raptor.retrieval.qdrant_vector_store import QdrantRaptorVectorStore

ingestion = DocumentIngestion()
chunks = ingestion.load_directory("mars/tools/docs_tools/raptor/data")  # tuỳ bạn

builder = TreeBuilder()
tree = builder.build_tree(chunks)

vs = QdrantRaptorVectorStore(
    collection_name="raptor_docs",
    url="http://localhost:6333",
)
vs.add_tree(tree)
vs.save()
