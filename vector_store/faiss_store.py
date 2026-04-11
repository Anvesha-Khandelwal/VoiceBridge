"""
vector_store/faiss_store.py
CONCEPT: Vector Database using FAISS

WHAT IS FAISS?
Facebook AI Similarity Search — a library for finding the most
similar vectors in a large collection, very fast.

WHY DO WE NEED IT?
After embedding our transcript chunks into vectors, we need
a way to quickly find which chunks are most similar to a question.

HOW SIMILARITY SEARCH WORKS:
1. Store: We have 20 transcript chunks → 20 vectors in FAISS index
2. Query: User asks "What did I say about pricing?"
3. Embed: Question → vector [0.2, 0.9, 0.1, ...]
4. Search: FAISS compares question vector against all 20 chunk vectors
5. Return: Top 3 most similar chunks (by cosine similarity score)

We store multiple sessions (one per transcript) using a dictionary.
"""
import logging
from typing import List, Dict, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class FAISSStore:
    def __init__(self, dimension: int = 384):
        """
        dimension: must match your embedding model output size
        all-MiniLM-L6-v2 → 384
        """
        self.dimension = dimension
        # Each session = one transcript with its own FAISS index
        # { session_id: {"index": faiss_index, "chunks": [...], "metadata": [...]} }
        self.sessions: Dict = {}

    def create_session(self, session_id: str):
        """Create a new empty FAISS index for a session."""
        import faiss
        # IndexFlatIP = Inner Product similarity (= cosine when normalized)
        index = faiss.IndexFlatIP(self.dimension)
        self.sessions[session_id] = {
            "index": index,
            "chunks": [],       # original text chunks
            "metadata": []      # extra info per chunk
        }
        logger.info(f"Created FAISS session: {session_id}")

    def add_chunks(self, session_id: str, chunks: List[str],
                   embeddings: np.ndarray, metadata: List[Dict] = None):
        """
        Add text chunks and their embeddings to the FAISS index.

        chunks:     ["text of chunk 1", "text of chunk 2", ...]
        embeddings: numpy array shape (n_chunks, dimension)
        """
        if session_id not in self.sessions:
            self.create_session(session_id)

        session = self.sessions[session_id]
        session["index"].add(embeddings)           # add vectors to FAISS
        session["chunks"].extend(chunks)           # store original text
        session["metadata"].extend(metadata or [{} for _ in chunks])
        logger.info(f"Added {len(chunks)} chunks to session {session_id}")

    def search(self, session_id: str, query_embedding: np.ndarray,
               top_k: int = 3) -> List[Dict]:
        """
        Find the top_k most similar chunks to the query.

        Returns list of:
        {
            "chunk": "the original text",
            "score": 0.87,          ← similarity score (0-1, higher=better)
            "rank": 1,
            "metadata": {...}
        }
        """
        if session_id not in self.sessions:
            raise ValueError(f"Session '{session_id}' not found. Index a transcript first.")

        session = self.sessions[session_id]
        n_stored = session["index"].ntotal

        if n_stored == 0:
            return []

        # Don't ask for more results than we have chunks
        k = min(top_k, n_stored)

        # FAISS search: returns distances and indices of top-k nearest vectors
        query = query_embedding.reshape(1, -1).astype(np.float32)
        scores, indices = session["index"].search(query, k)

        results = []
        for rank, (score, idx) in enumerate(zip(scores[0], indices[0])):
            if idx >= 0:  # FAISS returns -1 for empty slots
                results.append({
                    "chunk": session["chunks"][idx],
                    "score": float(score),
                    "rank": rank + 1,
                    "metadata": session["metadata"][idx]
                })

        return results

    def get_chunk_count(self, session_id: str) -> int:
        if session_id not in self.sessions:
            return 0
        return self.sessions[session_id]["index"].ntotal

    def clear_session(self, session_id: Optional[str] = None):
        if session_id:
            self.sessions.pop(session_id, None)
            logger.info(f"Cleared session: {session_id}")
        else:
            self.sessions.clear()
            logger.info("Cleared all sessions")

    def list_sessions(self) -> List[str]:
        return list(self.sessions.keys())
