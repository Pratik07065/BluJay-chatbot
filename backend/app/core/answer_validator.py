import os
import re
import json
from typing import Dict, Any, Optional, Union, List, Set
from app.core.normalizer import normalize_text, extract_keywords

VALIDATION_CONFIDENCE_THRESHOLD = float(os.getenv("VALIDATION_CONFIDENCE_THRESHOLD", "0.80"))

# Regex patterns for detecting specific claims that require strict context verification
FEE_PATTERNS = [
    r"(\$|₹|rs\.?|rupees|inr)\s*\d+([\d,]*\d+)?",
    r"\d+([\d,]*\d+)?\s*(rupees|inr|usd)",
    r"\bfee(s)?\s*(is|are|of)?\s*\d+"
]

PERCENTAGE_PATTERNS = [
    r"\d+(\.\d+)?%",
    r"\b\d+\s*percent\b"
]

SALARY_PATTERNS = [
    r"\d+(\.\d+)?\s*(lpa|lakhs|lakh|per annum|per year|k/month)",
    r"(\$|₹|rs\.?)\s*\d+([\d,]*\d+)?\s*(lpa|per annum)"
]

GUARANTEE_PATTERNS = [
    r"\b100%\s*(job|placement)?\s*guarantee\b",
    r"\bguaranteed\s*(job|placement|salary|refund)\b",
    r"\bmoney\s*back\s*guarantee\b"
]

DATE_PATTERNS = [
    r"\b(january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}(st|nd|rd|th)?(,\s*\d{4})?\b",
    r"\b\d{1,2}(st|nd|rd|th)?\s+(january|february|march|april|may|june|july|august|september|october|november|december)\b"
]

CONTACT_PATTERNS = [
    r"\+?\d{1,3}[\s-]?\d{10}",
    r"\b\d{5}\s*\d{5}\b",
    r"[\w\.-]+@[\w\.-]+\.\w+"
]

UNSUPPORTED_COURSES = {
    "blockchain", "cybersecurity", "ethical hacking", "flutter", "swift", "golang", "ruby on rails"
}

class AnswerValidator:
    """
    Validates LLM-generated answers against supplied Blujay RAG context
    to detect hallucinations and unsupported claims before saving into knowledge.json.
    """
    def __init__(self, confidence_threshold: Optional[float] = None):
        self.confidence_threshold = (
            confidence_threshold if confidence_threshold is not None else VALIDATION_CONFIDENCE_THRESHOLD
        )

    def validate(
        self,
        answer: str,
        context: Union[str, Dict[str, Any], List[Any]]
    ) -> Dict[str, Any]:
        """
        Validates an answer against context.
        Returns:
        {
          "valid": bool,
          "confidence": float,
          "reason": str
        }
        """
        if not answer or not isinstance(answer, str) or not answer.strip():
            return {
                "valid": False,
                "confidence": 0.0,
                "reason": "Answer is empty"
            }

        norm_answer = answer.lower().strip()

        # Format context into searchable text
        if isinstance(context, (dict, list)):
            context_text = json.dumps(context, ensure_ascii=False).lower()
        else:
            context_text = str(context).lower().strip()

        unsupported_reasons = []
        total_claims = 0
        unsupported_claims = 0

        # Check 1: Fee / Cost Claims
        for pattern in FEE_PATTERNS:
            matches = re.finditer(pattern, norm_answer)
            for m in matches:
                total_claims += 1
                claim_str = m.group(0)
                if claim_str not in context_text and re.sub(r"[^\d]", "", claim_str) not in context_text:
                    unsupported_claims += 1
                    unsupported_reasons.append(f"Invented fee claim: '{claim_str}'")

        # Check 2: Percentage / Statistics Claims
        for pattern in PERCENTAGE_PATTERNS:
            matches = re.finditer(pattern, norm_answer)
            for m in matches:
                total_claims += 1
                claim_str = m.group(0)
                if claim_str not in context_text:
                    unsupported_claims += 1
                    unsupported_reasons.append(f"Invented placement/percentage statistic: '{claim_str}'")

        # Check 3: Salary / Package Claims
        for pattern in SALARY_PATTERNS:
            matches = re.finditer(pattern, norm_answer)
            for m in matches:
                total_claims += 1
                claim_str = m.group(0)
                if claim_str not in context_text:
                    unsupported_claims += 1
                    unsupported_reasons.append(f"Invented salary/package claim: '{claim_str}'")

        # Check 4: Guarantees
        for pattern in GUARANTEE_PATTERNS:
            matches = re.finditer(pattern, norm_answer)
            for m in matches:
                total_claims += 1
                claim_str = m.group(0)
                if claim_str not in context_text:
                    unsupported_claims += 1
                    unsupported_reasons.append(f"Invented guarantee claim: '{claim_str}'")

        # Check 5: Specific Start Dates / Timeframes
        for pattern in DATE_PATTERNS:
            matches = re.finditer(pattern, norm_answer)
            for m in matches:
                total_claims += 1
                claim_str = m.group(0)
                if claim_str not in context_text:
                    unsupported_claims += 1
                    unsupported_reasons.append(f"Invented date/batch timeframe: '{claim_str}'")

        # Check 6: Contact Information
        for pattern in CONTACT_PATTERNS:
            matches = re.finditer(pattern, norm_answer)
            for m in matches:
                total_claims += 1
                claim_str = m.group(0)
                clean_claim = re.sub(r"[^\w@.]", "", claim_str)
                clean_context = re.sub(r"[^\w@.]", "", context_text)
                if clean_claim not in clean_context and claim_str not in context_text:
                    unsupported_claims += 1
                    unsupported_reasons.append(f"Invented contact details: '{claim_str}'")

        # Check 7: Invented Course Details
        for course in UNSUPPORTED_COURSES:
            if course in norm_answer and course not in context_text:
                total_claims += 1
                unsupported_claims += 1
                unsupported_reasons.append(f"Invented unsupported course: '{course}'")

        # Check 8: Overall Keyword Overlap / Factual Grounding
        answer_keywords = set(extract_keywords(norm_answer))
        context_keywords = set(extract_keywords(context_text))
        
        if answer_keywords and context_keywords:
            grounded_keywords = answer_keywords.intersection(context_keywords)
            grounding_ratio = float(len(grounded_keywords)) / float(len(answer_keywords))
        else:
            grounding_ratio = 1.0

        if unsupported_claims > 0:
            confidence = max(0.0, 1.0 - (float(unsupported_claims) * 0.40))
        else:
            confidence = min(1.0, 0.5 * grounding_ratio + 0.5)

        if unsupported_claims > 0 or confidence < self.confidence_threshold:
            reason_msg = "; ".join(unsupported_reasons) if unsupported_reasons else f"Low grounding ratio ({grounding_ratio:.2f})"
            return {
                "valid": False,
                "confidence": round(confidence, 4),
                "reason": f"Detected unsupported claims: {reason_msg}"
            }

        return {
            "valid": True,
            "confidence": round(confidence, 4),
            "reason": "Answer is supported by supplied Blujay context"
        }

def validate_answer(
    answer: str,
    context: Union[str, Dict[str, Any], List[Any]],
    confidence_threshold: Optional[float] = None
) -> Dict[str, Any]:
    """
    Public function to validate an LLM generated answer against context.
    """
    validator = AnswerValidator(confidence_threshold=confidence_threshold)
    return validator.validate(answer, context)
