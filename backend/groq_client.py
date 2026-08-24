import sys
from pathlib import Path

# Ensure backend directory is in sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.core.groq_client import (
    GroqClient,
    GroqService,
    generate_blujay_answer,
    BLUJAY_SYSTEM_PROMPT,
    FALLBACK_RESPONSE,
    GROQ_API_KEY,
    GROQ_MODEL
)
