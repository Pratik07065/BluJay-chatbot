import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "backend" / "data"

GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")


# Knowledge base paths
KB_JSON_PATH = DATA_DIR / "knowledge.json"
BLUJAY_CONTEXT_PATH = DATA_DIR / "blujay_context.json"

# Matching thresholds
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.82"))

# Polite rejection response for out-of-domain queries
OUT_OF_DOMAIN_RESPONSE = (
    "I am an AI inquiry assistant specifically designed for Blujay Technologies. "
    "I can only help with questions regarding Blujay Technologies, our courses, "
    "training programs, curriculum, duration, placement support, trainers, admissions, "
    "and contact information. Please feel free to ask any question about Blujay Technologies!"
)

# Standard fallback response when information is not in knowledge base
FALLBACK_RESPONSE = (
    "The requested information is currently unavailable. "
    "Please contact Blujay Technologies directly at +91 96187 21797 or email info@blujaytech.com. "
    "You can also visit our institute at 5th Floor, Mythrivanam Building, Ameerpet, Hyderabad."
)
