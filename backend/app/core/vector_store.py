import os
import re
import json
import logging
from functools import lru_cache
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
L1_CACHE_MAX_SIZE = 512


def _normalize_cache_key(text: str) -> str:
    """Normalizes text for ultra-fast L1 exact/punctuation-insensitive cache lookup."""
    cleaned = re.sub(r"[^\w\s]", "", text.lower()).strip()
    return re.sub(r"\s+", " ", cleaned)


class VectorStore:
    """
    ChromaDB-backed Vector Store for Blujay Technologies RAG & Semantic Cache pipeline.
    Optimized with:
      1. L1 in-memory normalized cache (<0.1ms for repeated queries).
      2. Single-pass query embedding shared across semantic cache & RAG retrieval.
      3. Startup model warm-up to eliminate cold-start embedding latency.
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

        # L1 in-memory cache mapping normalized question -> {answer, category}
        self._l1_cache: Dict[str, Dict[str, str]] = {}

        # LRU-cached embedding function so identical strings are never embedded twice
        self._embed_cached = lru_cache(maxsize=L1_CACHE_MAX_SIZE)(self._compute_embedding)

        # Pre-warm ONNX embedding model & load L1 cache from existing Chroma semantic cache
        self._warmup()

    def _compute_embedding(self, text: str) -> tuple:
        vec = self._embedding_fn([text])[0]
        return tuple(float(x) for x in vec)

    def embed_query(self, text: str) -> List[float]:
        """Computes (or retrieves cached) embedding vector for a query string."""
        return list(self._embed_cached(text.strip()))

    def _warmup(self) -> None:
        """Pre-loads ONNX session and populates L1 cache from persisted semantic cache."""
        try:
            self._embed_cached("warmup")
            if self._cache_collection.count() > 0:
                existing = self._cache_collection.get(include=["documents", "metadatas"])
                for doc, meta in zip(existing.get("documents", []), existing.get("metadatas", [])):
                    if doc and meta and meta.get("answer"):
                        key = _normalize_cache_key(doc)
                        if key:
                            self._l1_cache[key] = {
                                "answer": meta["answer"],
                                "category": meta.get("category", "general"),
                            }
        except Exception as e:
            logger.warning(f"VectorStore warmup warning: {e}")

    def _put_l1(self, question: str, answer: str, category: str) -> None:
        key = _normalize_cache_key(question)
        if not key:
            return
        if len(self._l1_cache) >= L1_CACHE_MAX_SIZE:
            # Evict oldest entry (Python 3.7+ dict preserves insertion order)
            self._l1_cache.pop(next(iter(self._l1_cache)))
        self._l1_cache[key] = {"answer": answer, "category": category}

    def index_knowledge_base(
        self,
        kb_file_path: Optional[Union[str, Path]] = None,
        force_reindex: bool = False,
    ) -> int:
        """
        Indexes all knowledge base entries into ChromaDB and seeds the semantic cache.
        Skips indexing if the collection already has documents unless force_reindex=True.
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

            documents.append(doc_text)
            metadatas.append({
                "category": str(category),
                "answer": str(answer),
                "primary_question": str(questions[0]) if questions else "",
                "source": "knowledge_base",
            })
            ids.append(f"kb_{idx}")

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
                    q_clean = q.strip()
                    cache_docs.append(q_clean)
                    cache_metas.append({
                        "answer": str(answer),
                        "category": str(category),
                        "source": "knowledge_base",
                    })
                    cache_ids.append(f"kb_q_{idx}_{q_idx}")
                    self._put_l1(q_clean, str(answer), str(category))

        if cache_docs:
            self._cache_collection.upsert(
                documents=cache_docs,
                metadatas=cache_metas,
                ids=cache_ids,
            )
            logger.info(f"Seeded {len(cache_docs)} FAQ questions into semantic cache '{CACHE_COLLECTION_NAME}'.")

        return len(documents)

    def lookup_cache(
        self,
        query: str,
        max_distance: float = CACHE_MAX_DISTANCE,
        query_embedding: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Checks L1 normalized cache first (<0.1ms), then ChromaDB semantic cache.
        """
        if not query or not query.strip():
            return {"hit": False}

        # L1 instant lookup (zero embedding overhead)
        l1_key = _normalize_cache_key(query)
        if l1_key in self._l1_cache:
            entry = self._l1_cache[l1_key]
            return {
                "hit": True,
                "answer": entry["answer"],
                "category": entry["category"],
                "distance": 0.0,
            }

        if self._cache_collection.count() == 0:
            return {"hit": False}

        emb = query_embedding if query_embedding is not None else self.embed_query(query)
        results = self._cache_collection.query(
            query_embeddings=[emb],
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
            answer = meta.get("answer", "")
            category = meta.get("category", "general")
            # Promote this phrasing into L1 cache so next repeat is <0.1ms
            self._put_l1(query, answer, category)
            return {
                "hit": True,
                "answer": answer,
                "category": category,
                "distance": round(dist, 4),
            }

        return {"hit": False}

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        max_distance: float = RAG_MAX_DISTANCE,
        query_embedding: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        """
        Queries ChromaDB for the top_k most relevant documents using a pre-computed embedding.
        Filters out results whose cosine distance exceeds max_distance.
        """
        if not query or not query.strip():
            return {"relevant": False, "contexts": [], "best_distance": 1.0, "category": "out_of_domain"}

        if self._collection.count() == 0:
            self.index_knowledge_base()

        if self._collection.count() == 0:
            return {"relevant": False, "contexts": [], "best_distance": 1.0, "category": "out_of_domain"}

        emb = query_embedding if query_embedding is not None else self.embed_query(query)
        n_results = min(top_k, self._collection.count())
        results = self._collection.query(
            query_embeddings=[emb],
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

    def add_to_cache(
        self,
        question: str,
        answer: str,
        category: str = "general",
    ) -> None:
        """
        Stores a newly generated (question, answer) pair in both L1 cache and ChromaDB semantic cache.
        """
        if not question or not question.strip() or not answer or not answer.strip():
            return

        q_clean = question.strip()
        self._put_l1(q_clean, str(answer), str(category))

        doc_id = f"llm_{abs(hash(q_clean.lower()))}"
        self._cache_collection.upsert(
            documents=[q_clean],
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
            "l1_cache_entries": len(self._l1_cache),
        }

    def clear_cache(self, reseed: bool = True) -> int:
        """Clears the semantic cache collection and L1 cache, optionally re-seeding FAQ questions."""
        self._l1_cache.clear()
        existing_ids = self._cache_collection.get()["ids"]
        if existing_ids:
            self._cache_collection.delete(ids=existing_ids)
        if reseed:
            self.index_knowledge_base(force_reindex=True)
        return self._cache_collection.count()
