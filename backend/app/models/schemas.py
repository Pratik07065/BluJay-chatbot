from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., description="User's query string", min_length=1)


class ChatResponse(BaseModel):
    question: str
    answer: str
    source: str = Field(
        ...,
        description="Source of answer: 'semantic_cache' | 'groq' | 'security_gate' | 'relevance_filter' | 'fallback'",
    )
    is_relevant: bool = True
    confidence_score: Optional[float] = None
    cost_saved: bool = False
