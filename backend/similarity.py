import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.similarity import (
    BaseEmbeddingProvider,
    TFIDFEmbeddingProvider,
    DefaultEmbeddingProvider,
    SimilarityEngine,
    EXACT_MATCH,
    KEYWORD_MATCH_THRESHOLD,
    SEMANTIC_MATCH_THRESHOLD,
    calculate_fuzzy_score,
    calculate_tfidf_score
)
