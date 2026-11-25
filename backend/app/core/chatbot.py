from pathlib import Path
from typing import Dict, Any, Optional, Union

from app.core.answer_validator import validate_answer
from app.core.groq_client import generate_blujay_answer, FALLBACK_RESPONSE
from app.core.vector_store import VectorStore
from app.core.security_guard import check_input_security
from app.config import OUT_OF_DOMAIN_RESPONSE


class ChatbotOrchestrator:
    """
    Main Orchestration Layer for Blujay Chatbot.
    Uses ChromaDB Semantic Cache for repeated/similar questions and ChromaDB RAG
    for grounded Groq LLM generation with strict out-of-domain rejection.
    """

    def __init__(self, kb_file_path: Optional[Union[str, Path]] = None):
        self.kb_file_path = kb_file_path
        self.vector_store = VectorStore()
        self.vector_store.index_knowledge_base(kb_file_path=self.kb_file_path)

    def process_question(
        self,
        question: str,
        file_path: Optional[Union[str, Path]] = None,
    ) -> Dict[str, Any]:
        # Step 1: Validate input
        if not question or not isinstance(question, str) or not question.strip():
            return {
                "answer": "Please provide a valid question.",
                "source": "fallback",
                "groq_called": False,
                "cached": False,
                "category": "out_of_domain",
                "confidence": 0.0,
            }

        raw_question = question.strip()

        # Step 2: Security Gate - Intercept prompt injection attacks
        sec_res = check_input_security(raw_question)
        if not sec_res["safe"]:
            return {
                "answer": sec_res["response"],
                "source": "security_gate",
                "groq_called": False,
                "cached": False,
                "category": "out_of_domain",
                "confidence": 0.0,
            }

        # Step 3: Fast L1 cache check before computing any embeddings (<0.1ms)
        cache_res = self.vector_store.lookup_cache(raw_question)
        if cache_res.get("hit") and cache_res.get("distance", 1.0) == 0.0:
            return {
                "answer": cache_res["answer"],
                "source": "semantic_cache",
                "groq_called": False,
                "cached": True,
                "category": cache_res.get("category", "general"),
                "confidence": 1.0,
            }

        # Step 3b: Compute query embedding ONCE and share across Semantic Cache & RAG
        query_emb = self.vector_store.embed_query(raw_question)

        cache_res = self.vector_store.lookup_cache(raw_question, query_embedding=query_emb)
        if cache_res.get("hit"):
            return {
                "answer": cache_res["answer"],
                "source": "semantic_cache",
                "groq_called": False,
                "cached": True,
                "category": cache_res.get("category", "general"),
                "confidence": round(1.0 - cache_res.get("distance", 0.0), 4),
            }

        # Step 4: RAG Retrieval & Domain Gate via ChromaDB Vector Store (reuses query_emb)
        rag_res = self.vector_store.retrieve(raw_question, top_k=3, query_embedding=query_emb)
        if not rag_res["relevant"]:
            return {
                "answer": OUT_OF_DOMAIN_RESPONSE,
                "source": "fallback",
                "groq_called": False,
                "cached": False,
                "category": "out_of_domain",
                "confidence": max(0.0, 1.0 - rag_res.get("best_distance", 1.0)),
            }

        # Step 5: Format retrieved ChromaDB chunks as grounded context for Groq
        retrieved_context = [
            {
                "category": ctx["category"],
                "content": ctx["document"],
                "relevance_score": round(1.0 - ctx["distance"], 4),
            }
            for ctx in rag_res["contexts"]
        ]
        category = rag_res.get("category", "general")

        # Step 6: Call Groq LLM with strict system instructions and RAG context
        generated_answer = generate_blujay_answer(
            question=raw_question,
            context=retrieved_context,
        )

        # Step 7: Validate generated answer
        is_invalid_answer = (
            not generated_answer
            or FALLBACK_RESPONSE in generated_answer
            or OUT_OF_DOMAIN_RESPONSE in generated_answer
            or "information is currently unavailable" in generated_answer.lower()
        )
        if is_invalid_answer:
            return {
                "answer": FALLBACK_RESPONSE,
                "source": "fallback",
                "groq_called": True,
                "cached": False,
                "category": category,
                "confidence": 0.0,
            }

        val_res = validate_answer(generated_answer, retrieved_context)
        if not val_res["valid"]:
            return {
                "answer": FALLBACK_RESPONSE,
                "source": "fallback",
                "groq_called": True,
                "cached": False,
                "category": category,
                "confidence": 0.0,
            }

        # Step 8: Store valid response in ChromaDB Semantic Cache for future repeated queries
        self.vector_store.add_to_cache(raw_question, generated_answer, category=category)

        return {
            "answer": generated_answer,
            "source": "groq",
            "groq_called": True,
            "cached": False,
            "category": category,
            "confidence": 0.90,
        }


_default_orchestrator: Optional[ChatbotOrchestrator] = None


def get_orchestrator(file_path: Optional[Union[str, Path]] = None) -> ChatbotOrchestrator:
    global _default_orchestrator
    if file_path is not None:
        return ChatbotOrchestrator(kb_file_path=file_path)
    if _default_orchestrator is None:
        _default_orchestrator = ChatbotOrchestrator()
    return _default_orchestrator


def process_question(
    question: str,
    file_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """
    Main entry point function to process a question through the Blujay Chatbot pipeline.
    """
    return get_orchestrator(file_path=file_path).process_question(question, file_path=file_path)
