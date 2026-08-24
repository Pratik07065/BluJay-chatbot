import os
from pathlib import Path
from typing import Dict, Any, Optional, Union

from app.core.knowledge_base import (
    load_knowledge,
    get_all_entries,
    search_exact_question,
    search_by_keywords,
    add_knowledge_entry,
    normalize_question
)
from app.core.similarity import SimilarityEngine
from app.core.relevance import check_relevance
from app.core.answer_validator import validate_answer
from app.core.groq_client import generate_blujay_answer, FALLBACK_RESPONSE
from app.core.knowledge_manager import pending_kb_manager
from app.config import OUT_OF_DOMAIN_RESPONSE


from app.core.security_guard import check_input_security, SECURITY_FALLBACK_RESPONSE

class ChatbotOrchestrator:
    """
    Main Orchestration Layer for Blujay Chatbot.
    Executes the 14-step processing pipeline.
    """
    def __init__(self, kb_file_path: Optional[Union[str, Path]] = None):
        self.kb_file_path = kb_file_path
        self.similarity_engine = SimilarityEngine()

    def process_question(
        self,
        question: str,
        file_path: Optional[Union[str, Path]] = None
    ) -> Dict[str, Any]:
        target_file = file_path or self.kb_file_path

        # Step 1: Validate input
        if not question or not isinstance(question, str) or not question.strip():
            return {
                "answer": "Please provide a valid question.",
                "source": "fallback",
                "groq_called": False,
                "cached": False,
                "category": "out_of_domain",
                "confidence": 0.0
            }

        raw_question = question.strip()

        # Step 1b: Security Gate - Intercept prompt injection attacks
        sec_res = check_input_security(raw_question)
        if not sec_res["safe"]:
            return {
                "answer": sec_res["response"],
                "source": "security_gate",
                "groq_called": False,
                "cached": False,
                "category": "out_of_domain",
                "confidence": 0.0
            }


        # Step 2: Normalize question
        norm_q = normalize_question(raw_question)

        # Step 3 & 4: Search exact match in knowledge.json
        exact_entry = search_exact_question(raw_question, file_path=target_file)
        if exact_entry:
            return {
                "answer": exact_entry["answer"],
                "source": "knowledge_base",
                "groq_called": False,
                "cached": True,
                "category": exact_entry.get("category_id") or exact_entry.get("category_name") or "general",
                "confidence": 1.0
            }

        # Step 5 & 6: Perform similarity search
        all_entries = get_all_entries(file_path=target_file)
        sim_res = self.similarity_engine.find_match(raw_question, all_entries)

        if sim_res["matched"] and sim_res["entry"]:
            matched_entry = sim_res["entry"]
            return {
                "answer": matched_entry["answer"],
                "source": "knowledge_base",
                "groq_called": False,
                "cached": True,
                "category": matched_entry.get("category_id") or matched_entry.get("category_name") or "general",
                "confidence": sim_res["score"]
            }

        # Step 7: Perform relevance classification
        rel_res = check_relevance(raw_question, kb_entries=all_entries)

        # Step 8: If irrelevant -> Return polite domain-restriction response (Do NOT call Groq, Do NOT save)
        if not rel_res["relevant"]:
            return {
                "answer": OUT_OF_DOMAIN_RESPONSE,
                "source": "fallback",
                "groq_called": False,
                "cached": False,
                "category": "out_of_domain",
                "confidence": rel_res.get("confidence", 0.0)
            }

        # Step 9: Retrieve most relevant Blujay knowledge context
        kw_match = search_by_keywords(raw_question, file_path=target_file)
        if kw_match:
            retrieved_context = {
                "category": kw_match.get("category_name", "Blujay Information"),
                "questions": kw_match.get("questions", []),
                "answer": kw_match.get("answer", ""),
                "keywords": kw_match.get("keywords", [])
            }
        else:
            retrieved_context = [
                {
                    "question": e.get("questions", [""])[0],
                    "answer": e.get("answer", "")
                }
                for e in all_entries[:5]
            ] if all_entries else "{}"

        # Step 10: Call Groq with strict system instructions, user question, and retrieved context
        generated_answer = generate_blujay_answer(
            question=raw_question,
            context=retrieved_context
        )

        # Step 11 & 12: Validate generated answer
        is_invalid_answer = (
            not generated_answer or
            FALLBACK_RESPONSE in generated_answer or
            OUT_OF_DOMAIN_RESPONSE in generated_answer or
            "information is currently unavailable" in generated_answer.lower()
        )

        if is_invalid_answer:
            return {
                "answer": FALLBACK_RESPONSE,
                "source": "fallback",
                "groq_called": True,
                "cached": False,
                "category": rel_res.get("category", "general"),
                "confidence": 0.0
            }

        # Step 11b: Answer Validation Layer (Detect unsupported claims/hallucinations)
        val_res = validate_answer(generated_answer, retrieved_context)
        if not val_res["valid"]:
            return {
                "answer": FALLBACK_RESPONSE,
                "source": "fallback",
                "groq_called": True,
                "cached": False,
                "category": rel_res.get("category", "general"),
                "confidence": 0.0
            }

        # Step 13: Save valid Groq answer to pending_knowledge.json for admin staging
        pending_kb_manager.add_pending_entry(
            question=raw_question,
            answer=generated_answer,
            context=retrieved_context,
            category=rel_res.get("category", "general"),
            source="groq_api",
            confidence=0.90
        )

        # Step 14: Return result dictionary
        return {
            "answer": generated_answer,
            "source": "groq",
            "groq_called": True,
            "cached": False,
            "category": rel_res.get("category", "general"),
            "confidence": 0.90
        }



def process_question(
    question: str,
    file_path: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """
    Main entry point function to process a question through the Blujay Chatbot pipeline.
    """
    orchestrator = ChatbotOrchestrator(kb_file_path=file_path)
    return orchestrator.process_question(question, file_path=file_path)
