import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.knowledge_base import (
    normalize_question,
    load_knowledge,
    save_knowledge,
    get_all_entries,
    search_exact_question,
    search_by_keywords,
    add_knowledge_entry,
    find_similar_questions
)

