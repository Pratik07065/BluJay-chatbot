import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.relevance import (
    RelevanceClassifier,
    check_relevance,
    is_domain_relevant,
    RELEVANCE_CONFIDENCE_THRESHOLD,
    OUT_OF_DOMAIN_PATTERNS,
    CATEGORY_KEYWORDS,
    BRAND_KEYWORDS
)
