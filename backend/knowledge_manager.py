import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.knowledge_manager import (
    PendingKnowledgeManager,
    pending_kb_manager,
    ADMIN_API_KEY,
    PENDING_KB_PATH
)
