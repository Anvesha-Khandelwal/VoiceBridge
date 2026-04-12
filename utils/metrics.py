"""
utils/metrics.py
CONCEPT: Evaluation Metrics for ML Systems

WHY THIS MATTERS FOR ML INTERVIEWS:
Any ML engineer knows that deploying a model without evaluation is
dangerous. This module shows you understand model evaluation.

WHAT WE MEASURE:
1. Semantic similarity — does the translation preserve meaning?
   Method: embed both texts, compute cosine similarity
   Why: BLEU score requires reference translations; semantic similarity
        works without ground truth

2. Translation confidence — how reliable is this translation?
   Factors: text length, language pair complexity, similarity score

3. RAG retrieval quality — how relevant are the retrieved chunks?
   Method: cosine similarity between query and retrieved chunk embeddings
"""
import logging
import numpy as np
from typing import List, Tuple, Optional

logger = logging.getLogger(__name__)


class TranslationMetrics:
    """
    Evaluates translation quality using semantic similarity.

    CONCEPT: Semantic Similarity
    If we embed the original text and the translated text into the same
    vector space, semantically equivalent texts should have similar vectors.

    Example:
    "Hello how are you" (en) → [0.2, 0.8, 0.3, ...]
    "नमस्ते आप कैसे हो" (hi) → [0.21, 0.79, 0.31, ...]
    Cosine similarity ≈ 0.95 — high, meaning preserved ✓

    vs

    "The cat sat on the mat" → [0.9, 0.1, 0.7, ...]
    "नमस्ते आप कैसे हो" (bad translation) → [0.2, 0.8, 0.3, ...]
    Cosine similarity ≈ 0.3 — low, meaning NOT preserved ✗

    NOTE: This works because multilingual embedding models are trained
    to place semantically equivalent sentences from different languages
    near each other in vector space. (LASER, LaBSE, mUSE papers)

    We use all-MiniLM-L6-v2 which has decent multilingual capability,
    though for production you'd use a dedicated multilingual model
    like paraphrase-multilingual-MiniLM-L12-v2.
    """

    def __init__(self, embedding_model=None):
        self._embedder = embedding_model  # injected from EmbeddingModel

    def semantic_similarity(self, text1: str, text2: str) -> float:
        """
        Compute cosine similarity between two texts.
        Returns float in [-1, 1], higher = more similar meaning.
        Typical good translation: > 0.75
        """
        if not self._embedder:
            return -1.0  # unavailable

        try:
            embs = self._embedder.embed([text1, text2])
            # Dot product of L2-normalized vectors = cosine similarity
            score = float(np.dot(embs[0], embs[1]))
            return round(score, 3)
        except Exception as e:
            logger.warning(f"Similarity computation failed: {e}")
            return -1.0

    def quality_label(self, score: float) -> dict:
        """
        Convert similarity score to human-readable quality label.
        Thresholds based on empirical testing on multilingual pairs.
        """
        if score < 0:
            return {"label": "Unknown", "color": "gray", "description": "Could not compute"}
        elif score >= 0.80:
            return {"label": "Excellent", "color": "green",
                    "description": "Meaning fully preserved"}
        elif score >= 0.65:
            return {"label": "Good", "color": "blue",
                    "description": "Meaning mostly preserved"}
        elif score >= 0.50:
            return {"label": "Fair", "color": "amber",
                    "description": "Some meaning may be lost"}
        else:
            return {"label": "Poor", "color": "red",
                    "description": "Significant meaning loss detected"}

    def evaluate_translation(self, original: str, translated: str) -> dict:
        """Full evaluation report for a translation."""
        score = self.semantic_similarity(original, translated)
        quality = self.quality_label(score)
        return {
            "semantic_similarity": score,
            "quality_label":       quality["label"],
            "quality_color":       quality["color"],
            "description":         quality["description"],
        }


class RAGMetrics:
    """
    Evaluates RAG retrieval quality.

    CONCEPT: Retrieval Precision
    When we retrieve k chunks for a question, how relevant are they?
    We measure this using the cosine similarity scores from FAISS.

    Mean Reciprocal Rank (MRR): standard IR metric
    If the best chunk is at rank 1: MRR = 1.0
    If the best chunk is at rank 2: MRR = 0.5
    If the best chunk is at rank 3: MRR = 0.33
    """

    @staticmethod
    def mean_relevance(retrieved_chunks: List[dict]) -> float:
        """Average relevance score of retrieved chunks."""
        if not retrieved_chunks:
            return 0.0
        scores = [c.get("score", 0.0) for c in retrieved_chunks]
        return round(float(np.mean(scores)), 3)

    @staticmethod
    def top_k_precision(retrieved_chunks: List[dict],
                        threshold: float = 0.60) -> float:
        """
        What fraction of retrieved chunks are actually relevant?
        (above similarity threshold)
        """
        if not retrieved_chunks:
            return 0.0
        relevant = sum(1 for c in retrieved_chunks
                       if c.get("score", 0.0) >= threshold)
        return round(relevant / len(retrieved_chunks), 3)

    @staticmethod
    def retrieval_report(retrieved_chunks: List[dict]) -> dict:
        """Full retrieval quality report."""
        if not retrieved_chunks:
            return {"status": "no_chunks", "mean_relevance": 0.0}

        scores = [c.get("score", 0.0) for c in retrieved_chunks]
        return {
            "num_retrieved":   len(retrieved_chunks),
            "mean_relevance":  round(float(np.mean(scores)), 3),
            "max_relevance":   round(float(np.max(scores)),  3),
            "min_relevance":   round(float(np.min(scores)),  3),
            "precision_at_k":  RAGMetrics.top_k_precision(retrieved_chunks),
            "quality":         "high" if np.mean(scores) > 0.70
                               else "medium" if np.mean(scores) > 0.50
                               else "low",
        }