import os
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple, Union
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.knowledge_base import normalize_question, extract_keywords_from_text

# Configurable thresholds via environment variables
EXACT_MATCH = float(os.getenv("EXACT_MATCH", os.getenv("EXACT_MATCH_THRESHOLD", "1.0")))
KEYWORD_MATCH_THRESHOLD = float(os.getenv("KEYWORD_MATCH_THRESHOLD", "0.75"))
SEMANTIC_MATCH_THRESHOLD = float(os.getenv("SEMANTIC_MATCH_THRESHOLD", "0.85"))

def calculate_fuzzy_score(query: str, target: str) -> float:
    """
    Returns RapidFuzz token set ratio normalized to 0.0 - 1.0 scale.
    """
    norm_q = normalize_question(query)
    norm_t = normalize_question(target)
    if not norm_q or not norm_t:
        return 0.0
    ratio = fuzz.token_set_ratio(norm_q, norm_t)
    return ratio / 100.0

def calculate_tfidf_score(query: str, corpus: List[str]) -> List[float]:
    """
    Calculates TF-IDF cosine similarity between query and a list of target strings.
    """
    if not corpus:
        return []
    
    norm_query = normalize_question(query)
    norm_corpus = [normalize_question(c) for c in corpus]

    try:
        vectorizer = TfidfVectorizer().fit(norm_corpus + [norm_query])
        corpus_vecs = vectorizer.transform(norm_corpus)
        query_vec = vectorizer.transform([norm_query])
        similarities = cosine_similarity(query_vec, corpus_vecs)[0]
        return [float(s) for s in similarities]
    except Exception:
        return [0.0] * len(corpus)

class BaseEmbeddingProvider(ABC):
    """
    Abstract Base Class for Embedding / Semantic Similarity Providers.
    Allows modular swapping of semantic embedding providers (e.g. TF-IDF, SentenceTransformers, OpenAI).
    """
    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Returns vector representation for a given text."""
        pass

    @abstractmethod
    def compute_similarity(self, text1: str, text2: str) -> float:
        """Computes semantic similarity score (0.0 to 1.0) between text1 and text2."""
        pass

class TFIDFEmbeddingProvider(BaseEmbeddingProvider):
    """
    Default lightweight TF-IDF & Fuzzy Cosine Similarity Embedding Provider.
    No external API calls required.
    """
    def embed_text(self, text: str) -> List[float]:
        norm = normalize_question(text)
        if not norm:
            return []
        tokens = norm.split()
        return [float(len(t)) for t in tokens]

    def compute_similarity(self, text1: str, text2: str) -> float:
        norm1 = normalize_question(text1)
        norm2 = normalize_question(text2)
        if not norm1 or not norm2:
            return 0.0

        fuzzy_score = fuzz.token_set_ratio(norm1, norm2) / 100.0
        try:
            vectorizer = TfidfVectorizer().fit([norm1, norm2])
            vecs = vectorizer.transform([norm1, norm2])
            tfidf_sim = float(cosine_similarity(vecs[0], vecs[1])[0][0])
        except Exception:
            tfidf_sim = 0.0

        return float(max(fuzzy_score * 0.95, (0.5 * fuzzy_score) + (0.5 * tfidf_sim)))

DefaultEmbeddingProvider = TFIDFEmbeddingProvider

class SimilarityEngine:
    """
    3-Stage Similarity Engine for Blujay Chatbot Knowledge Matching:
    Stage 1: Exact Normalized Question Match (score = 1.0)
    Stage 2: Keyword Similarity (threshold = KEYWORD_MATCH_THRESHOLD, default 0.75)
    Stage 3: Semantic Similarity (threshold = SEMANTIC_MATCH_THRESHOLD, default 0.85)
    """
    def __init__(
        self,
        exact_threshold: Optional[float] = None,
        keyword_threshold: Optional[float] = None,
        semantic_threshold: Optional[float] = None,
        embedding_provider: Optional[BaseEmbeddingProvider] = None,
        threshold: Optional[float] = None
    ):
        self.exact_threshold = exact_threshold if exact_threshold is not None else EXACT_MATCH
        self.keyword_threshold = keyword_threshold if keyword_threshold is not None else KEYWORD_MATCH_THRESHOLD
        
        # Support legacy threshold param or explicit semantic_threshold
        if semantic_threshold is not None:
            self.semantic_threshold = semantic_threshold
        elif threshold is not None:
            self.semantic_threshold = threshold
        else:
            self.semantic_threshold = SEMANTIC_MATCH_THRESHOLD

        self.embedding_provider = embedding_provider or DefaultEmbeddingProvider()

    def _extract_entry_questions(self, entry: Any) -> List[str]:
        if isinstance(entry, dict):
            return entry.get("questions", [])
        if hasattr(entry, "canonical_question"):
            questions = [entry.canonical_question]
            if hasattr(entry, "similar_phrasings"):
                questions.extend(list(entry.similar_phrasings))
            return questions
        return []

    def _extract_entry_keywords(self, entry: Any) -> List[str]:
        if isinstance(entry, dict):
            kw = list(entry.get("keywords", []))
            for q in entry.get("questions", []):
                kw.extend(extract_keywords_from_text(q))
            return list(dict.fromkeys(kw))
        if hasattr(entry, "normalized_keywords"):
            kw = list(entry.normalized_keywords)
            for q in self._extract_entry_questions(entry):
                kw.extend(extract_keywords_from_text(q))
            return list(dict.fromkeys(kw))
        return []

    def _to_entry_dict(self, entry: Any) -> Dict[str, Any]:
        if isinstance(entry, dict):
            return dict(entry)
        if hasattr(entry, "model_dump"):
            return entry.model_dump()
        if hasattr(entry, "__dict__"):
            return dict(entry.__dict__)
        return {"entry": str(entry)}

    def find_match(self, query: str, entries: List[Any]) -> Dict[str, Any]:
        """
        Executes the 3-stage matching pipeline:
        Returns:
        {
            "matched": bool,
            "score": float,
            "entry": dict or None,
            "match_type": "exact|keyword|semantic|none"
        }
        """
        if not query or not query.strip() or not entries:
            return {
                "matched": False,
                "score": 0.0,
                "entry": None,
                "match_type": "none"
            }

        norm_query = normalize_question(query)

        # Stage 1: Exact Normalized Question Match
        if norm_query:
            for entry in entries:
                questions = self._extract_entry_questions(entry)
                for q in questions:
                    if normalize_question(q) == norm_query:
                        return {
                            "matched": True,
                            "score": round(float(self.exact_threshold), 4),
                            "entry": self._to_entry_dict(entry),
                            "match_type": "exact"
                        }

        # Stage 2: Keyword Similarity
        query_kw = set(extract_keywords_from_text(query))
        best_kw_entry = None
        best_kw_score = 0.0

        if query_kw:
            for entry in entries:
                entry_kw = set(self._extract_entry_keywords(entry))
                if entry_kw:
                    intersection = query_kw.intersection(entry_kw)
                    if intersection:
                        query_coverage = len(intersection) / float(len(query_kw))
                        jaccard = len(intersection) / float(len(query_kw.union(entry_kw)))
                        score = max(query_coverage, 0.7 * query_coverage + 0.3 * jaccard)
                        if score > best_kw_score:
                            best_kw_score = score
                            best_kw_entry = entry

        if best_kw_entry is not None and best_kw_score >= self.keyword_threshold:
            return {
                "matched": True,
                "score": round(float(best_kw_score), 4),
                "entry": self._to_entry_dict(best_kw_entry),
                "match_type": "keyword"
            }

        # Stage 3: Semantic Similarity
        best_semantic_entry = None
        best_semantic_score = 0.0

        for entry in entries:
            questions = self._extract_entry_questions(entry)
            for q in questions:
                sim_score = self.embedding_provider.compute_similarity(query, q)
                if sim_score > best_semantic_score:
                    best_semantic_score = sim_score
                    best_semantic_entry = entry

        if best_semantic_entry is not None and best_semantic_score >= self.semantic_threshold:
            return {
                "matched": True,
                "score": round(float(best_semantic_score), 4),
                "entry": self._to_entry_dict(best_semantic_entry),
                "match_type": "semantic"
            }

        # Fallback / No Match
        highest_score = max(best_kw_score, best_semantic_score)
        return {
            "matched": False,
            "score": round(float(highest_score), 4),
            "entry": None,
            "match_type": "none"
        }

    def find_best_match(self, query: str, entries: List[Any]) -> Tuple[Optional[Any], float]:
        """
        Backward-compatibility wrapper returning (best_entry_object, score).
        """
        result = self.find_match(query, entries)
        if result["matched"]:
            matched_dict = result["entry"]
            if matched_dict and entries:
                for original_item in entries:
                    if hasattr(original_item, "id") and isinstance(matched_dict, dict):
                        if getattr(original_item, "id") == matched_dict.get("id"):
                            return original_item, result["score"]
                    elif isinstance(matched_dict, dict) and isinstance(original_item, dict):
                        if original_item.get("id") == matched_dict.get("id"):
                            return original_item, result["score"]
                    elif original_item == matched_dict:
                        return original_item, result["score"]
            return result["entry"], result["score"]
        return None, result["score"]

