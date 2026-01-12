# from mars.tools.docs_tools.raptor import RaptorRAGChain
# from mars.tools.docs_tools.raptor.retrieval.qdrant_vector_store import QdrantRaptorVectorStore
#
# vs = QdrantRaptorVectorStore(collection_name="raptor_docs", url="http://localhost:6333")
# vs.load()  # connect tới collection đã có
#
# rag = RaptorRAGChain(vs)
# print(rag.invoke("What tasks does paper BittDistill evaluate on?"))
from mars.graph.node import DELEGATE_PROMPT

print(DELEGATE_PROMPT)