import os
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Union

import chromadb
from chromadb.utils import embedding_functions

from app.config import DATA_DIR, BLUJAY_CONTEXT_PATH, RAG_MAX_DISTANCE, CACHE_MAX_DISTANCE
from app.core.knowledge_base import get_all_entries

logger = logging.getLogger("BlujayVectorStore")
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [VectorStore] %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

CHROMA_DB_DIR = DATA_DIR / "chroma_db"
COLLECTION_NAME = "blujay_knowledge"
CACHE_COLLECTION_NAME = "blujay_semantic_cache"


class VectorStore:
    """
    ChromaDB-backed Vector Store for Blujay Technologies RAG pipeline.
    Indexes knowledge base entries and retrieves semantically relevant context.
    """

    def __init__(
        self,
        persist_dir: Optional[Union[str, Path]] = None,
        collection_name: str = COLLECTION_NAME,
    ):
        self.persist_dir = Path(persist_dir) if persist_dir else CHROMA_DB_DIR
        self.persist_dir.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name

        self._client = chromadb.PersistentClient(path=str(self.persist_dir))
        self._embedding_fn = embedding_functions.DefaultEmbeddingFunction()
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
        self._cache_collection = self._client.get_or_create_collection(
            name=CACHE_COLLECTION_NAME,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    def index_knowledge_base(
        self,
        kb_file_path: Optional[Union[str, Path]] = None,
        force_reindex: bool = False,
    ) -> int:
        """
        Indexes all knowledge base entries into ChromaDB.
        Skips indexing if the collection already has documents unless force_reindex=True.
        Returns the number of indexed documents.
        """
        if not force_reindex and self._collection.count() > 0:
            return self._collection.count()

        entries = get_all_entries(file_path=kb_file_path)
        documents: List[str] = []
        metadatas: List[Dict[str, Any]] = []
        ids: List[str] = []

        for idx, entry in enumerate(entries):
            questions = entry.get("questions", [])
            answer = entry.get("answer", "")
            keywords = entry.get("keywords", [])
            category = (
                entry.get("category_name")
                or entry.get("category_id")
                or "general"
            )

            if not answer:
                continue

            q_text = " | ".join(questions) if questions else ""
            kw_text = ", ".join(keywords) if keywords else ""
            doc_text = f"Category: {category}\nQuestions: {q_text}\nKeywords: {kw_text}\nAnswer: {answer}"

            doc_id = f"kb_{idx}"
            documents.append(doc_text)
            metadatas.append({
                "category": str(category),
                "answer": str(answer),
                "primary_question": str(questions[0]) if questions else "",
                "source": "knowledge_base",
            })
            ids.append(doc_id)

        # Also index blujay_context.json if it exists
        if BLUJAY_CONTEXT_PATH.exists():
            try:
                with open(BLUJAY_CONTEXT_PATH, "r", encoding="utf-8") as f:
                    ctx_data = json.load(f)
                if isinstance(ctx_data, dict):
                    for key, val in ctx_data.items():
                        val_str = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val)
                        documents.append(f"Blujay {key}: {val_str}")
                        metadatas.append({
                            "category": str(key),
                            "answer": val_str,
                            "primary_question": str(key),
                            "source": "blujay_context",
                        })
                        ids.append(f"ctx_{key}")
            except Exception as e:
                logger.warning(f"Could not index blujay_context.json: {e}")

        if not documents:
            logger.warning("No documents found to index into ChromaDB.")
            return 0

        if force_reindex and self._collection.count() > 0:
            existing_ids = self._collection.get()["ids"]
            if existing_ids:
                self._collection.delete(ids=existing_ids)

        self._collection.upsert(
            documents=documents,
            metadatas=metadatas,
            ids=ids,
        )
        logger.info(f"Indexed {len(documents)} documents into ChromaDB collection '{self.collection_name}'.")

        # Seed semantic cache with known FAQ questions from the knowledge base
        cache_docs: List[str] = []
        cache_metas: List[Dict[str, Any]] = []
        cache_ids: List[str] = []
        for idx, entry in enumerate(entries):
            answer = entry.get("answer", "")
            category = entry.get("category_name") or entry.get("category_id") or "general"
            if not answer:
                continue
            for q_idx, q in enumerate(entry.get("questions", [])):
                if q and q.strip():
                    cache_docs.append(q.strip())
                    cache_metas.append({
                        "answer": str(answer),
                        "category": str(category),
                        "source": "knowledge_base",
                    })
                    cache_ids.append(f"kb_q_{idx}_{q_idx}")

        if cache_docs:
            self._cache_collection.upsert(
                documents=cache_docs,
                metadatas=cache_metas,
                ids=cache_ids,
            )
            logger.info(f"Seeded {len(cache_docs)} FAQ questions into semantic cache '{CACHE_COLLECTION_NAME}'.")

        return len(documents)

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        max_distance: float = RAG_MAX_DISTANCE,
    ) -> Dict[str, Any]:
        """
        Queries ChromaDB for the top_k most relevant documents.
        Filters out results whose cosine distance exceeds max_distance.

        Returns:
            {
                "relevant": bool,
                "contexts": List[Dict[str, Any]],
                "best_distance": float,
                "category": str
            }
        """
        if not query or not query.strip():
            return {"relevant": False, "contexts": [], "best_distance": 1.0, "category": "out_of_domain"}

        if self._collection.count() == 0:
            self.index_knowledge_base()

        if self._collection.count() == 0:
            return {"relevant": False, "contexts": [], "best_distance": 1.0, "category": "out_of_domain"}

        n_results = min(top_k, self._collection.count())
        results = self._collection.query(
            query_texts=[query.strip()],
            n_results=n_results,
            include=["documents", "metadatas", "distances"],
        )

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        filtered_contexts: List[Dict[str, Any]] = []
        best_distance = min(dists) if dists else 1.0

        for doc, meta, dist in zip(docs, metas, dists):
            if dist <= max_distance:
                filtered_contexts.append({
                    "document": doc,
                    "category": meta.get("category", "general"),
                    "answer": meta.get("answer", ""),
                    "distance": round(float(dist), 4),
                })

        if not filtered_contexts:
            return {
                "relevant": False,
                "contexts": [],
                "best_distance": round(float(best_distance), 4),
                "category": "out_of_domain",
            }

        return {
            "relevant": True,
            "contexts": filtered_contexts,
            "best_distance": round(float(best_distance), 4),
            "category": filtered_contexts[0]["category"],
        }

    def lookup_cache(
        self,
        query: str,
        max_distance: float = CACHE_MAX_DISTANCE,
    ) -> Dict[str, Any]:
        """
        Checks the ChromaDB semantic cache for a semantically similar question.
        If found within max_distance, returns the cached answer without calling the LLM.
        """
        if not query or not query.strip() or self._cache_collection.count() == 0:
            return {"hit": False}

        results = self._cache_collection.query(
            query_texts=[query.strip()],
            n_results=1,
            include=["metadatas", "distances"],
        )

        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        if not metas or not dists:
            return {"hit": False}

        dist = float(dists[0])
        if dist <= max_distance:
            meta = metas[0]
            return {
                "hit": True,
                "answer": meta.get("answer", ""),
                "category": meta.get("category", "general"),
                "distance": round(dist, 4),
            }

        return {"hit": False}

    def add_to_cache(
        self,
        question: str,
        answer: str,
        category: str = "general",
    ) -> None:
        """
        Stores a newly generated (question, answer) pair in the ChromaDB semantic cache
        so future semantically similar queries are served without calling the LLM.
        """
        if not question or not question.strip() or not answer or not answer.strip():
            return

        doc_id = f"llm_{abs(hash(question.strip().lower()))}"
        self._cache_collection.upsert(
            documents=[question.strip()],
            metadatas=[{
                "answer": str(answer),
                "category": str(category),
                "source": "semantic_cache",
            }],
            ids=[doc_id],
        )

    def get_stats(self) -> Dict[str, int]:
        """Returns document counts for the RAG knowledge base and semantic cache collections."""
        return {
            "kb_documents": self._collection.count(),
            "semantic_cache_entries": self._cache_collection.count(),
        }

    def clear_cache(self, reseed: bool = True) -> int:
        """Clears the semantic cache collection and optionally re-seeds FAQ questions."""
        existing_ids = self._cache_collection.get()["ids"]
        if existing_ids:
            self._cache_collection.delete(ids=existing_ids)
        if reseed:
            self.index_knowledge_base(force_reindex=True)
        return self._cache_collection.count()
