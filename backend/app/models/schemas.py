from typing import List, Optional
from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    question: str = Field(..., description="User's query string", min_length=1)

class ChatResponse(BaseModel):
    question: str
    answer: str
    source: str = Field(..., description="Source of answer: 'knowledge_base' | 'groq' | 'relevance_filter' | 'fallback'")
    is_relevant: bool = True
    confidence_score: Optional[float] = None
    cost_saved: bool = False

class QAPair(BaseModel):
    id: str
    canonical_question: str
    similar_phrasings: List[str] = []
    normalized_keywords: List[str] = []
    answer: str
    category: str = "general"
    source: str = "user_query"
    created_at: str
    hit_count: int = 1

class KnowledgeBaseData(BaseModel):
    version: str = "1.0"
    last_updated: str
    qa_pairs: List[QAPair]
