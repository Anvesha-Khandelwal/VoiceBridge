"""
models/embedding_model.py
CONCEPT: Text Embeddings (Vector Representations)

WHAT ARE EMBEDDINGS?
Text like "Hello how are you" can't be stored in a math database.
We need to convert it to numbers. But not random numbers — numbers
that CAPTURE MEANING.

Example:
"King"   → [0.2, 0.8, 0.1, ...]
"Queen"  → [0.2, 0.8, 0.3, ...]  ← very similar to King!
"Apple"  → [0.9, 0.1, 0.7, ...]  ← very different

Sentences about similar topics will have SIMILAR vectors.
This lets us find "relevant" chunks without exact keyword matching.

MODEL: all-MiniLM-L6-v2
- 384 dimensions (each text becomes 384 numbers)
- Very fast, runs on CPU
- Great quality for semantic search
- Only 80MB in size
"""
import logging
from typing import List
import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingModel:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        self._model = None
        self.dimension = 384  # all-MiniLM-L6-v2 outputs 384-dim vectors
        logger.info(f"EmbeddingModel ready (model={model_name}, lazy-load)")

    def embed(self, texts: List[str]) -> np.ndarray:
        """
        Convert a list of texts into embedding vectors.

        Input:  ["Hello world", "How are you"]
        Output: numpy array of shape (2, 384)
                [[0.1, 0.3, ...], [0.2, 0.8, ...]]
        """
        model = self._load()
        # encode() runs the transformer model on each text
        embeddings = model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,  # L2 normalize → cosine similarity = dot product
            show_progress_bar=False
        )
        return embeddings.astype(np.float32)

    def embed_single(self, text: str) -> np.ndarray:
        """Embed a single string. Returns shape (384,)"""
        return self.embed([text])[0]

    def _load(self):
        """Load sentence-transformers model — cached after first load."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            logger.info(f"Loading embedding model '{self.model_name}'...")
            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded.")
        return self._model
