import os
from loguru import logger
from ai_teacher_robot.rag.vector_store.qdrant_store import QdrantStore
from ai_teacher_robot.rag.vector_store.chroma_store import ChromaStore
from ai_teacher_robot.rag.vector_store.faiss_store import FaissStore

class VectorStoreFactory:
    """Factory to instantiate different vector stores based on environment settings."""
    @staticmethod
    def get_vector_store(store_type: str = None, collection_name: str = "curriculum_embeddings", dimension: int = 384):
        if not store_type:
            store_type = os.environ.get("VECTOR_STORE_TYPE", "qdrant").lower()

        logger.info(f"Instantiating vector store type: '{store_type}' for collection: '{collection_name}'")
        
        if store_type == "chroma":
            return ChromaStore(collection_name=collection_name, dimension=dimension)
        elif store_type == "faiss":
            return FaissStore(collection_name=collection_name, dimension=dimension)
        else:
            # Default to Qdrant
            return QdrantStore(collection_name=collection_name, dimension=dimension)
