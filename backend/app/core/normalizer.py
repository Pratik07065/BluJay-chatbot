import re
from typing import List, Set

# Common English stopwords to strip for keyword extraction
STOPWORDS: Set[str] = {
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "shall",
    "should", "can", "could", "may", "might", "must", "to", "of", "in",
    "for", "on", "with", "at", "by", "from", "up", "about", "into", "over",
    "after", "me", "my", "myself", "we", "our", "ours", "you", "your",
    "yours", "he", "him", "his", "she", "her", "hers", "it", "its", "they",
    "them", "their", "this", "that", "these", "those", "tell", "give", "know",
    "please", "can", "could", "want", "like", "need"
}

# Domain synonym map to standardize variations
SYNONYMS = {
    "fees": "fee",
    "cost": "fee",
    "price": "fee",
    "charging": "fee",
    "pricing": "fee",
    "charges": "fee",
    "location": "address",
    "located": "address",
    "place": "address",
    "where": "address",
    "branches": "branch",
    "centre": "center",
    "contact": "phone",
    "call": "phone",
    "mobile": "phone",
    "number": "phone",
    "placements": "placement",
    "jobs": "job",
    "hiring": "placement",
    "courses": "course",
    "class": "course",
    "classes": "course",
    "training": "course",
    "programs": "course",
    "program": "course",
    "institutes": "institute",
    "academy": "institute",
    "coaching": "institute"
}

def normalize_text(text: str) -> str:
    """
    Normalizes input query by lowercasing, stripping punctuation,
    replacing synonyms, and collapsing spaces.
    """
    if not text:
        return ""
    
    # Lowercase
    cleaned = text.lower().strip()
    
    # Replace non-alphanumeric chars with space except hyphen
    cleaned = re.sub(r"[^\w\s-]", " ", cleaned)
    
    # Split into tokens
    tokens = cleaned.split()
    
    # Map synonyms
    normalized_tokens = [SYNONYMS.get(t, t) for t in tokens]
    
    # Join with single space
    return " ".join(normalized_tokens)

def extract_keywords(text: str) -> List[str]:
    """
    Extracts key tokens from normalized text by removing stopwords.
    """
    normalized = normalize_text(text)
    tokens = normalized.split()
    keywords = [t for t in tokens if t not in STOPWORDS and len(t) > 1]
    return keywords
