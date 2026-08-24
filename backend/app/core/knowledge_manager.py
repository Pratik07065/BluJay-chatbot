import os
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from filelock import FileLock

from app.config import KB_JSON_PATH
from app.core.knowledge_base import add_knowledge_entry

PENDING_KB_PATH = Path(os.getenv("PENDING_KB_JSON_PATH", str(Path(KB_JSON_PATH).parent / "pending_knowledge.json")))
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "blujay_admin_secret_key_2026")

class PendingKnowledgeManager:
    """
    Manages staging of unverified Groq answers in pending_knowledge.json
    and admin workflows (approve, reject, edit, promote to knowledge.json).
    """
    def __init__(self, pending_path: Optional[Path] = None, verified_path: Optional[Path] = None):
        self.pending_path = Path(pending_path or PENDING_KB_PATH)
        self.verified_path = Path(verified_path or KB_JSON_PATH)
        self.lock_path = Path(str(self.pending_path) + ".lock")
        self._ensure_file_exists()

    def _ensure_file_exists(self):
        self.pending_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.pending_path.exists() or self.pending_path.stat().st_size == 0:
            initial_data = {
                "version": "1.0",
                "pending_entries": []
            }
            with FileLock(str(self.lock_path), timeout=10):
                with open(self.pending_path, "w", encoding="utf-8") as f:
                    json.dump(initial_data, f, indent=2, ensure_ascii=False)

    def load_pending(self) -> Dict[str, Any]:
        self._ensure_file_exists()
        with FileLock(str(self.lock_path), timeout=10):
            try:
                with open(self.pending_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                return {"version": "1.0", "pending_entries": []}

    def save_pending(self, data: Dict[str, Any]):
        self.pending_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.pending_path.with_suffix(".tmp")
        with FileLock(str(self.lock_path), timeout=10):
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            temp_path.replace(self.pending_path)

    def add_pending_entry(
        self,
        question: str,
        answer: str,
        context: Any,
        category: str = "general",
        source: str = "groq_api",
        confidence: float = 0.90
    ) -> Dict[str, Any]:
        data = self.load_pending()
        entries = data.get("pending_entries", [])

        norm_q = question.strip().lower()
        for e in entries:
            if e.get("question", "").strip().lower() == norm_q and e.get("status") == "pending":
                return e

        entry_id = f"pending_{int(time.time())}_{len(entries)+1}"
        new_entry = {
            "id": entry_id,
            "question": question.strip(),
            "answer": answer.strip(),
            "context": context,
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "confidence": round(confidence, 4),
            "source": source,
            "status": "pending"
        }

        entries.append(new_entry)
        data["pending_entries"] = entries
        self.save_pending(data)
        return new_entry

    def list_pending(self, status: Optional[str] = "pending") -> List[Dict[str, Any]]:
        data = self.load_pending()
        entries = data.get("pending_entries", [])
        if status:
            return [e for e in entries if e.get("status") == status]
        return entries

    def get_pending_by_id(self, entry_id: str) -> Optional[Dict[str, Any]]:
        entries = self.list_pending(status=None)
        for e in entries:
            if e.get("id") == entry_id:
                return e
        return None

    def edit_pending(
        self,
        entry_id: str,
        new_answer: Optional[str] = None,
        new_category: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        data = self.load_pending()
        entries = data.get("pending_entries", [])
        target_entry = None

        for e in entries:
            if e.get("id") == entry_id:
                if new_answer and new_answer.strip():
                    e["answer"] = new_answer.strip()
                if new_category and new_category.strip():
                    e["category"] = new_category.strip()
                e["updated_at"] = datetime.now().isoformat()
                target_entry = e
                break

        if target_entry:
            data["pending_entries"] = entries
            self.save_pending(data)
        return target_entry

    def reject_pending(self, entry_id: str) -> bool:
        data = self.load_pending()
        entries = data.get("pending_entries", [])
        found = False

        for e in entries:
            if e.get("id") == entry_id:
                e["status"] = "rejected"
                e["updated_at"] = datetime.now().isoformat()
                found = True
                break

        if found:
            data["pending_entries"] = entries
            self.save_pending(data)
        return found

    def approve_and_promote(self, entry_id: str) -> Optional[Dict[str, Any]]:
        data = self.load_pending()
        entries = data.get("pending_entries", [])
        target_entry = None

        for e in entries:
            if e.get("id") == entry_id:
                e["status"] = "approved"
                e["updated_at"] = datetime.now().isoformat()
                target_entry = e
                break

        if not target_entry:
            return None

        # Save pending status change
        data["pending_entries"] = entries
        self.save_pending(data)

        # Move into verified knowledge.json
        add_knowledge_entry(
            question=target_entry["question"],
            answer=target_entry["answer"],
            category=target_entry.get("category", "general"),
            source=target_entry.get("source", "groq_api_approved"),
            file_path=self.verified_path
        )

        return target_entry

# Helper module instance
pending_kb_manager = PendingKnowledgeManager()
