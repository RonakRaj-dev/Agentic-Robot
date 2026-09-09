from abc import ABC, abstractmethod
from typing import List

class EmbeddingProvider(ABC):
    """Abstract base class for all embedding providers."""
    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        """Generates a dense vector embedding for a single text query."""
        pass

    @abstractmethod
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """Generates embeddings for a batch of text queries."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Returns the dimensionality of the generated embeddings."""
        pass
