import os
import re
from typing import Dict, Any, Tuple, Optional, List, Set
from app.core.normalizer import normalize_text, extract_keywords

# Configurable threshold via environment variable
RELEVANCE_CONFIDENCE_THRESHOLD = float(os.getenv("RELEVANCE_CONFIDENCE_THRESHOLD", "0.65"))

# Explicit out-of-domain trigger phrases (general trivia, jokes, coding prompts, weather, politics, science, geography)
OUT_OF_DOMAIN_PATTERNS = [
    r"\bwho is (the )?(pm|prime minister|president|chief minister|cm|governor)\b",
    r"\bwho won\b",
    r"\bcricket\b|\bipl\b|\bmatch\b|\bfootball\b|\bworld cup\b",
    r"\bweather\b|\btemperature\b|\brain\b|\bforecast\b",
    r"\bjoke\b|\briddle\b|\bfunny\b|\bpoem\b|\bstory\b",
    r"\brecipe\b|\bfood\b|\bcooking\b",
    r"\bwrite (a |an )?(python|java|c\+\+|javascript|code|script|program|function|algorithm)\b",
    r"\bhow to write (code|a program)\b",
    r"\bquantum (physics|mechanics)\b|\bphysics\b|\bchemistry\b|\bbiology\b",
    r"\bcapital of\b|\bpopulation of\b|\bgeography\b",
    r"\bsolve\b|\bmath\b|\bcalculate\b|\bequation\b",
    r"\bwho created\b|\bwho invented\b",
    r"\bnews\b|\bheadline\b|\bpolitics\b|\belection\b"
]

# Category Domain Mappings
CATEGORY_KEYWORDS: Dict[str, Set[str]] = {
    "courses": {
        "course", "courses", "program", "programs", "training", "class", "classes",
        "python", "java", "devops", "aws", "mern", "ai", "ml", "data science",
        "fullstack", "full-stack", "web development", "syllab", "curriculum",
        "duration", "schedule", "online", "offline", "certification", "certificate"
    },
    "placement": {
        "placement", "placements", "job", "jobs", "hiring", "hired", "career",
        "salary", "package", "interview", "recruitment", "company", "companies"
    },
    "admission": {
        "admission", "admissions", "enroll", "enrollment", "join", "joining",
        "fees", "fee", "cost", "price", "pricing", "discount", "scholarship",
        "process", "apply", "register", "registration"
    },
    "contact": {
        "contact", "address", "location", "located", "place", "where", "phone",
        "number", "call", "mobile", "email", "reach", "ameerpet", "mythrivanam",
        "hyderabad"
    },
    "features": {
        "project", "projects", "live project", "trainer", "trainers", "faculty",
        "teacher", "demo", "lab", "hands-on", "support"
    }
}

# Brand and core institution entities
BRAND_KEYWORDS = {"blujay", "blujaytech", "institute", "academy", "ameerpet", "mythrivanam"}

class RelevanceClassifier:
    """
    Layered Relevance Classifier for Blujay Chatbot.
    Determines whether a question is related to Blujay Technologies or should be rejected.
    """
    def __init__(
        self,
        confidence_threshold: Optional[float] = None,
        out_of_domain_patterns: Optional[List[str]] = None,
        category_keywords: Optional[Dict[str, Set[str]]] = None
    ):
        self.confidence_threshold = (
            confidence_threshold if confidence_threshold is not None else RELEVANCE_CONFIDENCE_THRESHOLD
        )
        self.out_of_domain_patterns = out_of_domain_patterns or OUT_OF_DOMAIN_PATTERNS
        self.category_keywords = category_keywords or CATEGORY_KEYWORDS

    def classify(self, question: str, kb_entries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Executes Layered Relevance Check:
        Layer 1: Knowledge base match check
        Layer 2: Blujay-specific entity/keyword/intent check & Out-of-domain check
        Layer 3: Lightweight classification score check
        Returns:
        {
          "relevant": bool,
          "confidence": float,
          "reason": str,
          "category": "courses|admission|placement|contact|features|out_of_domain"
        }
        """
        if not question or not isinstance(question, str) or len(question.strip()) < 2:
            return {
                "relevant": False,
                "confidence": 1.0,
                "reason": "Question is empty or too short",
                "category": "out_of_domain"
            }

        norm_q = normalize_text(question)

        # Layer 1: Knowledge Base Match Check
        if kb_entries:
            try:
                from app.core.knowledge_base import search_exact_question, find_similar_questions
                exact_hit = search_exact_question(question, knowledge_data={"categories": [{"id": "all", "name": "All", "entries": kb_entries}]})
                if exact_hit:
                    return {
                        "relevant": True,
                        "confidence": 1.0,
                        "reason": f"Exact knowledge base match (ID: {exact_hit.get('id', 'kb')})",
                        "category": exact_hit.get("category_id", "courses")
                    }
                similar_hits = find_similar_questions(question, threshold=0.75, knowledge_data={"categories": [{"id": "all", "name": "All", "entries": kb_entries}]})
                if similar_hits:
                    top_hit, _, score = similar_hits[0]
                    return {
                        "relevant": True,
                        "confidence": round(float(score), 4),
                        "reason": f"High similarity knowledge base match (score: {score:.2f})",
                        "category": top_hit.get("category_id", "courses")
                    }
            except Exception:
                pass

        # Layer 2: Out-of-Domain Patterns & Blujay-specific Keywords/Entities
        for pattern in self.out_of_domain_patterns:
            if re.search(pattern, norm_q, re.IGNORECASE):
                return {
                    "relevant": False,
                    "confidence": 0.95,
                    "reason": "Matched explicit out-of-domain pattern",
                    "category": "out_of_domain"
                }

        # Check for Brand / Institution Direct Reference
        has_brand_ref = any(b in norm_q for b in BRAND_KEYWORDS)
        tokens = set(extract_keywords(norm_q))

        # Classify Category & Intent
        matched_categories = []
        for cat_name, keywords in self.category_keywords.items():
            overlap = tokens.intersection(keywords)
            if overlap:
                matched_categories.append((cat_name, len(overlap)))

        if matched_categories:
            matched_categories.sort(key=lambda x: x[1], reverse=True)
            top_category = matched_categories[0][0]
            confidence = 0.95 if has_brand_ref else 0.88
            return {
                "relevant": True,
                "confidence": confidence,
                "reason": f"Matched Blujay domain category keywords ({top_category})",
                "category": top_category
            }

        if has_brand_ref:
            return {
                "relevant": True,
                "confidence": 0.90,
                "reason": "Direct reference to Blujay Technologies or campus location",
                "category": "courses"
            }

        # Layer 3: Lightweight Classification Method for Uncertain Queries
        all_domain_words = set().union(*self.category_keywords.values()).union(BRAND_KEYWORDS)
        overlap_count = len(tokens.intersection(all_domain_words))
        
        score = float(overlap_count) / float(len(tokens)) if len(tokens) > 0 else 0.0

        if score >= self.confidence_threshold:
            return {
                "relevant": True,
                "confidence": round(score, 4),
                "reason": "Lightweight classifier detected sufficient domain vocabulary",
                "category": "courses"
            }

        # Low confidence -> Classify as irrelevant rather than hallucinating
        return {
            "relevant": False,
            "confidence": round(score, 4),
            "reason": "Low relevance confidence score (no Blujay domain match)",
            "category": "out_of_domain"
        }

def check_relevance(question: str, kb_entries: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    """
    Public entry point returning relevance classification dictionary.
    """
    classifier = RelevanceClassifier()
    return classifier.classify(question, kb_entries=kb_entries)

def is_domain_relevant(query: str) -> Tuple[bool, str]:
    """
    Backward-compatible helper returning (is_relevant: bool, reason: str).
    """
    classifier = RelevanceClassifier()
    res = classifier.classify(query)
    return res["relevant"], res["reason"]

