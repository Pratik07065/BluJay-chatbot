import re
from typing import Dict, Any, Tuple

INJECTION_PATTERNS = [
    # 1. Instruction Override
    r"\bignore\s+(all\s+|any\s+|previous\s+|your\s+)*(instructions?|prompts?|rules?|directives?|guidelines?)\b",
    r"\bforget\s+(all\s+|your\s+)*(system\s+)?(prompts?|instructions?|rules?)\b",
    r"\boverride\s+(the\s+|your\s+)*(system\s+)?(prompts?|instructions?|rules?|safety)\b",
    r"\bdisregard\s+(all\s+|previous\s+|your\s+)*(prompts?|instructions?|rules?)\b",
    r"\breset\s+(your\s+)*(prompts?|instructions?|state)\b",

    # 2. Persona Hijacking / Jailbreak
    r"\byou\s+are\s+now\s+(a\s+)?(general\s+ai|unrestricted|dan|jailbroken|godmode)\b",
    r"\bact\s+as\s+(a\s+)?(general|unrestricted|chatgpt|gpt|developer\s+mode)\b",
    r"\bswitch\s+to\s+(developer\s+mode|unrestricted\s+mode|debug\s+mode)\b",
    r"\bpretend\s+(you\s+are|to\s+be)\s+(a\s+)?(general|unrestricted|different)\b",

    # 3. Knowledge Source Bypass
    r"\banswer\s+using\s+(your\s+own|general|external|internet)\s+(knowledge|data|information)\b",
    r"\buse\s+(internet|general|external|your\s+own)\s+(knowledge|data|information)\s+instead\b",
    r"\bignore\s+(the\s+)?(context|supplied\s+knowledge|blujay\s+knowledge)\b",

    # 4. Secret / System Info Extraction
    r"\breveal\s+(your\s+)*(system\s+)?(prompts?|instructions?|context|api\s+keys?|groq\s+key)\b",
    r"\bshow\s+(me\s+)?(your\s+)*(api\s+keys?|groq\s+key|system\s+prompts?|instructions?)\b",
    r"\btell\s+me\s+what\s+(instructions?|system\s+prompt)\s+you\s+(received|have)\b",
    r"\bprint\s+(your\s+)*(system\s+prompt|instructions?|api\s+key)\b",
    r"\bwhat\s+(is|are)\s+your\s+(system\s+prompt|instructions?|api\s+key|groq\s+key)\b",
    r"\bdisplay\s+(hidden\s+)?(context|instructions?|prompts?)\b",

    # 5. Injection Delimiters & Code Injection
    r"```\s*(system|instruction|prompt)",
    r"\[system\s*instruction\]",
    r"<\s*system\s*>",
    r"\b(eval|exec|import\s+os|system\(|__import__)\b"
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

SECURITY_FALLBACK_RESPONSE = (
    "I am the official inquiry assistant for Blujay Technologies. "
    "I can only help you with questions about Blujay's courses, training programs, "
    "admissions, fees, location, and placement support."
)

class SecurityGuard:
    """
    Guards the chatbot against prompt injection attacks, persona hijacking,
    system prompt leaks, and API key extraction attempts.
    """
    @staticmethod
    def is_prompt_injection(text: str) -> Tuple[bool, str]:
        if not text or not isinstance(text, str):
            return False, ""

        norm_text = text.lower().strip()

        for pattern in COMPILED_PATTERNS:
            if pattern.search(norm_text):
                return True, f"Matched prompt injection pattern: '{pattern.pattern}'"

        return False, ""

def check_input_security(text: str) -> Dict[str, Any]:
    is_attack, reason = SecurityGuard.is_prompt_injection(text)
    if is_attack:
        return {
            "safe": False,
            "reason": reason,
            "response": SECURITY_FALLBACK_RESPONSE
        }
    return {
        "safe": True,
        "reason": "",
        "response": ""
    }
