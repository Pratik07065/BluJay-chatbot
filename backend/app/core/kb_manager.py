import json
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Tuple
from filelock import FileLock

from app.models.schemas import KnowledgeBaseData, QAPair
from app.core.similarity import SimilarityEngine
from app.core.normalizer import extract_keywords
from app.config import KB_JSON_PATH, SIMILARITY_THRESHOLD

class KnowledgeBaseManager:
    def __init__(self, kb_path: Path = KB_JSON_PATH):
        self.kb_path = kb_path
        self.lock_path = Path(str(kb_path) + ".lock")
        self.lock = FileLock(self.lock_path, timeout=10)
        self.similarity_engine = SimilarityEngine(threshold=SIMILARITY_THRESHOLD)
        self.kb_data: KnowledgeBaseData = self._load_kb()

    def _load_kb(self) -> KnowledgeBaseData:
        """
        Loads knowledge_base.json into memory safely.
        """
        if not self.kb_path.exists():
            # Return empty schema if file doesn't exist
            return KnowledgeBaseData(
                version="1.0",
                last_updated=datetime.now(timezone.utc).isoformat(),
                qa_pairs=[]
            )
        
        with self.lock:
            try:
                with open(self.kb_path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
                    return KnowledgeBaseData(**raw_data)
            except Exception as e:
                print(f"[KBManager Error] Failed to load KB: {e}")
                return KnowledgeBaseData(
                    version="1.0",
                    last_updated=datetime.now(timezone.utc).isoformat(),
                    qa_pairs=[]
                )

    def lookup(self, query: str) -> Tuple[Optional[QAPair], float]:
        """
        Searches the knowledge base using the similarity engine.
        Increments hit_count on match.
        """
        best_match, score = self.similarity_engine.find_best_match(query, self.kb_data.qa_pairs)
        if best_match:
            # Increment hit count
            best_match.hit_count += 1
            # Update asynchronously or on save
        return best_match, score

    def add_qa_pair(
        self, question: str, answer: str, category: str = "groq_learned", source: str = "groq_api"
    ) -> QAPair:
        """
        Atomically appends a new QAPair to knowledge_base.json and refreshes memory state.
        """
        new_id = f"qa_{uuid.uuid4().hex[:8]}"
        keywords = extract_keywords(question)
        
        new_pair = QAPair(
            id=new_id,
            canonical_question=question,
            similar_phrasings=[question.lower()],
            normalized_keywords=keywords,
            answer=answer,
            category=category,
            source=source,
            created_at=datetime.now(timezone.utc).isoformat(),
            hit_count=1
        )

        with self.lock:
            # Reload fresh data before modifying
            self.kb_data = self._load_kb()
            self.kb_data.qa_pairs.append(new_pair)
            self.kb_data.last_updated = datetime.now(timezone.utc).isoformat()
            
            # Atomic file write (write to temp file then replace)
            temp_file = self.kb_path.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.kb_data.model_dump(), f, indent=2, ensure_ascii=False)
            
            temp_file.replace(self.kb_path)
            print(f"[KBManager] Successfully saved new Q&A pair '{new_id}' to knowledge_base.json")

        return new_pair
