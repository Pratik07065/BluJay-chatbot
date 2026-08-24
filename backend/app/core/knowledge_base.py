import json
import re
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
from filelock import FileLock
from rapidfuzz import fuzz

def _get_default_knowledge_path() -> Path:
    current_file = Path(__file__).resolve()
    for p in [current_file.parent, current_file.parent.parent, current_file.parent.parent.parent]:
        candidate = p / "data" / "knowledge.json"
        if candidate.exists():
            return candidate
    return current_file.parent.parent.parent / "data" / "knowledge.json"

DEFAULT_KNOWLEDGE_PATH = _get_default_knowledge_path()

# Filler phrases to remove during normalization
FILLER_PHRASES = [
    r"\bcan you (please )?tell me\b",
    r"\bcould you (please )?tell me\b",
    r"\bi want to know\b",
    r"\bi would like to know\b",
    r"\bi'd like to know\b",
    r"\btell me about\b",
    r"\btell me\b",
    r"\bdo you know\b",
    r"\bdo you have\b",
    r"\bcan i get\b",
    r"\bcan i know\b",
    r"\bis there\b",
    r"\bare there\b",
    r"\bwhere is\b",
    r"\bwhere are\b",
    r"\bwhat is\b",
    r"\bwhat are\b",
    r"\bwhich is\b",
    r"\bwhich are\b",
    r"\bplease\b",
    r"\bkindly\b",
    r"\bthank you\b",
    r"\bthanks\b",
]

# Filler words (stopwords & conversational fluff)
FILLER_WORDS = {
    "a", "an", "the", "do", "does", "did", "you", "your", "yours", "me", "my", "we", "our", "us",
    "can", "could", "would", "will", "should", "shall", "may", "might", "must",
    "is", "are", "am", "was", "were", "be", "been", "being",
    "what", "which", "where", "who", "whom", "how", "why", "to", "of", "in", "for", "on", "with",
    "at", "by", "from", "up", "about", "into", "over", "after", "institute", "blujay", "technologies",
    "tech", "company"
}

# Synonym mappings to standardize domain terms
SYNONYM_MAP = {
    "courses": "course",
    "classes": "course",
    "class": "course",
    "programs": "course",
    "program": "course",
    "training": "course",
    "offered": "offer",
    "offering": "offer",
    "offers": "offer",
    "fees": "fee",
    "cost": "fee",
    "costs": "fee",
    "pricing": "fee",
    "price": "fee",
    "charges": "fee",
    "located": "location",
    "location": "location",
    "address": "location",
    "place": "location",
    "situated": "location",
    "contact": "phone",
    "number": "phone",
    "call": "phone",
    "mobile": "phone",
    "placements": "placement",
    "jobs": "placement",
    "job": "placement",
    "hiring": "placement",
    "details": "detail"
}

def normalize_question(question: str) -> str:
    """
    Normalizes a question by:
    - Converting to lowercase
    - Stripping conversational filler phrases & filler words
    - Removing unnecessary punctuation
    - Normalizing whitespace
    - Applying synonym mapping while preserving key domain words
    """
    if not question or not isinstance(question, str):
        return ""

    text = question.lower().strip()
    if not text:
        return ""

    # Remove conversational filler phrases
    for filler in FILLER_PHRASES:
        text = re.sub(filler, " ", text, flags=re.IGNORECASE)

    # Remove non-alphanumeric characters except space and hyphens
    text = re.sub(r"[^\w\s-]", " ", text)

    # Tokenize
    tokens = text.split()

    # Filter filler words while preserving important domain words
    filtered_tokens = [t for t in tokens if t not in FILLER_WORDS]

    # If filtering removed all tokens, fall back to non-empty original tokens
    if not filtered_tokens:
        filtered_tokens = tokens

    # Map synonyms
    normalized_tokens = [SYNONYM_MAP.get(t, t) for t in filtered_tokens]

    return " ".join(normalized_tokens)

def extract_keywords_from_text(text: str) -> List[str]:
    """
    Extracts distinct important keywords from text.
    """
    if not text:
        return []
    normalized = normalize_question(text)
    tokens = normalized.split()
    keywords = [t for t in tokens if len(t) > 1]
    return list(dict.fromkeys(keywords))

def get_default_structure() -> Dict[str, Any]:
    return {
        "version": "1.0",
        "institution": {
            "name": "Blujay Technologies",
            "website": "https://www.blujaytech.com/"
        },
        "categories": []
    }

def load_knowledge(file_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Safely loads knowledge.json.
    Returns default empty structure if file is missing, empty, or malformed.
    """
    target_path = Path(file_path) if file_path else _get_default_knowledge_path()
    if not target_path.exists():
        return get_default_structure()

    lock_path = Path(str(target_path) + ".lock")
    try:
        lock = FileLock(lock_path, timeout=5)
        with lock:
            with open(target_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return get_default_structure()
                data = json.loads(content)
                if not isinstance(data, dict) or "categories" not in data:
                    return get_default_structure()
                return data
    except Exception as e:
        print(f"[KnowledgeBase Error] Failed to load knowledge file safely: {e}")
        return get_default_structure()

def save_knowledge(knowledge_data: Dict[str, Any], file_path: Optional[Union[str, Path]] = None) -> bool:
    """
    Atomically saves knowledge structure to file using file locks.
    Safe against write/permission errors and malformed JSON payloads.
    """
    target_path = Path(file_path) if file_path else _get_default_knowledge_path()
    try:
        target_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path = Path(str(target_path) + ".lock")
        lock = FileLock(lock_path, timeout=5)
        temp_path = target_path.with_suffix(".tmp")
        with lock:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(knowledge_data, f, indent=2, ensure_ascii=False)
            temp_path.replace(target_path)
            return True
    except Exception as e:
        print(f"[KnowledgeBase Error] Failed to save knowledge file safely: {e}")
        if 'temp_path' in locals() and temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        return False

def get_all_entries(
    knowledge_data: Optional[Dict[str, Any]] = None,
    file_path: Optional[Union[str, Path]] = None
) -> List[Dict[str, Any]]:
    """
    Returns a flattened list of all entries across all categories.
    """
    data = knowledge_data or load_knowledge(file_path)
    all_entries = []

    for cat in data.get("categories", []):
        cat_id = cat.get("id", "general")
        cat_name = cat.get("name", "General")
        for entry in cat.get("entries", []):
            entry_copy = dict(entry)
            entry_copy["category_id"] = cat_id
            entry_copy["category_name"] = cat_name
            all_entries.append(entry_copy)

    return all_entries

def search_exact_question(
    question: str,
    knowledge_data: Optional[Dict[str, Any]] = None,
    file_path: Optional[Union[str, Path]] = None
) -> Optional[Dict[str, Any]]:
    """
    Searches for an exact normalized question match in the knowledge base.
    Never modifies the original answer when returning an existing knowledge entry.
    """
    norm_q = normalize_question(question)
    if not norm_q:
        return None

    entries = get_all_entries(knowledge_data, file_path)
    for entry in entries:
        for existing_q in entry.get("questions", []):
            if normalize_question(existing_q) == norm_q:
                return dict(entry)

    return None

def search_by_keywords(
    question: str,
    knowledge_data: Optional[Dict[str, Any]] = None,
    file_path: Optional[Union[str, Path]] = None
) -> Optional[Dict[str, Any]]:
    """
    Searches knowledge base entries matching question keywords.
    """
    query_keywords = set(extract_keywords_from_text(question))
    if not query_keywords:
        return None

    entries = get_all_entries(knowledge_data, file_path)
    best_entry = None
    best_overlap = 0.0

    for entry in entries:
        entry_kw = set(entry.get("keywords", []))
        for q in entry.get("questions", []):
            entry_kw.update(extract_keywords_from_text(q))

        intersection = query_keywords.intersection(entry_kw)
        if intersection:
            overlap_score = len(intersection) / float(len(query_keywords))
            if overlap_score > best_overlap:
                best_overlap = overlap_score
                best_entry = dict(entry)

    if best_overlap >= 0.5:
        return best_entry

    return None

def find_similar_questions(
    question: str,
    threshold: float = 0.70,
    knowledge_data: Optional[Dict[str, Any]] = None,
    file_path: Optional[Union[str, Path]] = None
) -> List[Tuple[Dict[str, Any], str, float]]:
    """
    Finds similar questions in the knowledge base above similarity threshold.
    Returns list of (entry, matching_question_text, score).
    """
    norm_q = normalize_question(question)
    if not norm_q:
        return []

    entries = get_all_entries(knowledge_data, file_path)
    results = []

    for entry in entries:
        for existing_q in entry.get("questions", []):
            norm_existing = normalize_question(existing_q)
            score = fuzz.token_set_ratio(norm_q, norm_existing) / 100.0
            if score >= threshold:
                results.append((dict(entry), existing_q, float(score)))

    results.sort(key=lambda x: x[2], reverse=True)
    return results

def add_knowledge_entry(
    question: str,
    answer: str,
    category: str = "general",
    source: str = "user_contributed",
    file_path: Optional[Union[str, Path]] = None
) -> Dict[str, Any]:
    """
    Adds a new knowledge entry or appends phrasing to an existing entry if similar/duplicate.
    - Prevents duplicate entries
    - Checks for similar existing questions
    - Stores multiple question variants when appropriate
    """
    data = load_knowledge(file_path)

    # Check 1: Exact normalized question match
    exact_match = search_exact_question(question, knowledge_data=data)
    if exact_match:
        return exact_match

    # Check 2: Check if exact answer already exists in knowledge base
    all_entries = get_all_entries(knowledge_data=data)
    for entry in all_entries:
        if entry.get("answer", "").strip() == answer.strip():
            # Add variant phrasing if not present
            if question not in entry.get("questions", []):
                for cat in data.get("categories", []):
                    for item in cat.get("entries", []):
                        if item.get("id") == entry.get("id"):
                            item.setdefault("questions", []).append(question)
                            save_knowledge(data, file_path)
                            return item
            return entry

    # Check 3: Check for highly similar question (threshold >= 0.85)
    similar_matches = find_similar_questions(question, threshold=0.85, knowledge_data=data)
    if similar_matches:
        matched_entry, matched_q, score = similar_matches[0]
        for cat in data.get("categories", []):
            for item in cat.get("entries", []):
                if item.get("id") == matched_entry.get("id"):
                    if question not in item.get("questions", []):
                        item.setdefault("questions", []).append(question)
                        save_knowledge(data, file_path)
                    return item

    # Check 4: No duplicate or similar entry found -> Create new entry
    new_entry_id = f"entry_{uuid.uuid4().hex[:8]}"
    keywords = extract_keywords_from_text(question)

    new_entry = {
        "id": new_entry_id,
        "questions": [question],
        "answer": answer,
        "keywords": keywords,
        "source": source,
        "confidence": 1.0
    }

    cat_found = False
    for cat in data.setdefault("categories", []):
        if cat.get("id") == category or cat.get("name", "").lower() == category.lower():
            cat.setdefault("entries", []).append(new_entry)
            cat_found = True
            break

    if not cat_found:
        new_cat = {
            "id": category.lower().replace(" ", "_"),
            "name": category.title(),
            "entries": [new_entry]
        }
        data["categories"].append(new_cat)

    save_knowledge(data, file_path)
    return new_entry

