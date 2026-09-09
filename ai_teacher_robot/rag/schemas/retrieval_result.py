from typing import Optional, Dict, Any
from pydantic import BaseModel

class RetrievalResult(BaseModel):
    chunk_id: str
    document_id: str
    chunk_text: str
    page_number: int
    chapter: str
    topic: str
    score: float
    metadata: Dict[str, Any] = {}
