from mars.tools.docs_tools.raptor import DocumentIngestion, TreeBuilder, RaptorVectorStore


ingestion = DocumentIngestion()
chunks = ingestion.load_directory("mars/tools/docs_tools/raptor/data")

builder = TreeBuilder()
tree = builder.build_tree(chunks)

# Index to vector store
vector_store = RaptorVectorStore()
vector_store.add_tree(tree)
vector_store.save()