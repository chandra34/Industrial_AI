"""BM25 sparse search index service using bm25s.

Manages per-user BM25 indices on local disk. Each user gets an independent
index directory under ``settings.resolved_bm25_index_dir/{user_id}/``.

The index is rebuilt (not incrementally patched) whenever documents are added
or removed because BM25 does not support in-place mutation.  For typical
corpus sizes (< 100 000 chunks) this takes well under a second.
"""

from __future__ import annotations

import logging
import re
import shutil
import threading
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import bm25s

from backend.config.settings import Settings

if TYPE_CHECKING:
    from backend.rag.chunking import ChunkRecord

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class BM25SearchHit:
    """A single BM25 retrieval result."""
    chunk_text: str
    score: float


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class BM25Service:
    """Build, persist, load, and query per-user BM25 indices."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._base_dir: Path = settings.resolved_bm25_index_dir
        self._base_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize stemmer object if PyStemmer is installed
        self._stemmer_name = settings.bm25_stemmer
        self._stemmer_obj = None
        if self._stemmer_name:
            try:
                import Stemmer
                self._stemmer_obj = Stemmer.Stemmer(self._stemmer_name)
            except Exception as exc:
                logger.warning("Failed to initialize stemmer '%s': %s. BM25 will run without stemming.", self._stemmer_name, exc)

        # Locks to prevent race conditions on file updates
        self._locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
        self._global_lock = threading.Lock()
        
        logger.info(
            "BM25Service initialised (index_dir=%s, stemmer=%s)",
            self._base_dir,
            self._stemmer_name,
        )

    # -- locks helper -------------------------------------------------------

    def _get_lock(self, user_id: str) -> threading.Lock:
        """Thread-safe retrieval of a per-user Lock."""
        with self._global_lock:
            return self._locks[user_id]

    # -- path helpers -------------------------------------------------------

    def _sanitize_user_id(self, user_id: str) -> str:
        """Ensure user_id is alphanumeric with only dots, hyphens, and underscores."""
        if not user_id or not re.fullmatch(r"[A-Za-z0-9._-]+", user_id):
            raise ValueError("Invalid user_id: contains disallowed characters")
        return user_id

    def _index_path(self, user_id: str) -> Path:
        """Return the directory that stores a user's BM25 index."""
        safe_user_id = self._sanitize_user_id(user_id)
        return self._base_dir / safe_user_id

    # -- core operations ----------------------------------------------------

    def build_index(self, user_id: str, corpus: list[str]) -> None:
        """Tokenise *corpus* and persist a fresh BM25 index for *user_id*.

        Parameters
        ----------
        user_id:
            Owner of the index.
        corpus:
            Plain-text chunks to index.
        """
        if not corpus:
            logger.warning("build_index called with empty corpus for user %s – skipping", user_id)
            return

        corpus_tokens = bm25s.tokenize(corpus, stemmer=self._stemmer_obj)
        retriever = bm25s.BM25(corpus=corpus)
        retriever.index(corpus_tokens)

        save_dir = self._index_path(user_id)
        if save_dir.exists():
            shutil.rmtree(save_dir, ignore_errors=True)
        save_dir.mkdir(parents=True, exist_ok=True)
        retriever.save(str(save_dir), corpus=corpus)
        logger.info(
            "Built BM25 index for user %s (%d chunks, saved to %s)",
            user_id,
            len(corpus),
            save_dir,
        )

    def add_to_index(self, user_id: str, new_chunks: list[ChunkRecord]) -> None:
        """Append *new_chunks* to the user's existing index (rebuild).

        If no existing index is found, a brand-new one is created.
        """
        new_texts = [c.text for c in new_chunks if c.text.strip()]
        if not new_texts:
            return

        with self._get_lock(user_id):
            existing_corpus = self._load_corpus(user_id)
            combined_corpus = existing_corpus + new_texts
            self.build_index(user_id, combined_corpus)

    def search(self, user_id: str, query: str, top_k: int = 5) -> list[BM25SearchHit]:
        """Retrieve the top-*k* BM25 hits for *query* from the user's index."""
        with self._get_lock(user_id):
            idx_path = self._index_path(user_id)
            if not idx_path.exists():
                logger.warning("No BM25 index found for user %s at %s", user_id, idx_path)
                return []

            retriever = bm25s.BM25.load(str(idx_path), load_corpus=True)
            corpus = retriever.corpus  # list[str] saved alongside the index

            if not corpus or len(corpus) == 0:
                return []

            query_tokens = bm25s.tokenize(query, stemmer=self._stemmer_obj)
            
            # Ensure k is at least 1 and within corpus limits
            k_val = min(top_k, len(corpus))
            if k_val <= 0:
                return []

            results, scores = retriever.retrieve(query_tokens, k=k_val, corpus=corpus)

        hits: list[BM25SearchHit] = []
        # results and scores are 2-D arrays (one row per query)
        if len(results) > 0 and len(scores) > 0:
            for doc, score in zip(results[0], scores[0]):
                if isinstance(doc, dict) and "text" in doc:
                    text = doc["text"]
                else:
                    text = str(doc) if not isinstance(doc, str) else doc
                hits.append(BM25SearchHit(chunk_text=text, score=float(score)))

        return hits

    def delete_document_from_index(
        self,
        user_id: str,
        remaining_chunks: list[ChunkRecord],
    ) -> None:
        """Rebuild the user's BM25 index from *remaining_chunks*.

        Called after a document has been removed from Milvus.  If no chunks
        remain, the index directory is deleted entirely.
        """
        with self._get_lock(user_id):
            if not remaining_chunks:
                idx_path = self._index_path(user_id)
                if idx_path.exists():
                    shutil.rmtree(idx_path, ignore_errors=True)
                    logger.info("Removed BM25 index directory for user %s (no remaining chunks)", user_id)
                return

            corpus = [c.text for c in remaining_chunks if c.text.strip()]
            self.build_index(user_id, corpus)

    # -- private helpers ----------------------------------------------------

    def _load_corpus(self, user_id: str) -> list[str]:
        """Load the previously-saved corpus for *user_id*, or return ``[]``."""
        idx_path = self._index_path(user_id)
        if not idx_path.exists():
            return []

        try:
            retriever = bm25s.BM25.load(str(idx_path), load_corpus=True)
            corpus = retriever.corpus
            if corpus is None:
                return []
            return [
                doc["text"] if isinstance(doc, dict) and "text" in doc else str(doc)
                for doc in corpus
            ]
        except Exception:
            logger.exception("Failed to load existing BM25 index for user %s", user_id)
            return []
