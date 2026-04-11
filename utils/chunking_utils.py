"""
utils/chunking_utils.py
CONCEPT: Text Chunking for RAG

WHY DO WE CHUNK?
LLMs and embedding models have token limits. A 30-minute transcript
might be 15,000 words — too large to embed as one piece.

We split it into overlapping chunks so:
1. Each chunk fits in the embedding model
2. Overlap ensures context isn't lost at boundaries
3. FAISS can find the specific relevant chunk

EXAMPLE with chunk_size=100, overlap=20:
Text: "ABCDEFGHIJ..." (200 chars)
Chunk 1: chars 0-100
Chunk 2: chars 80-180   ← 20-char overlap with chunk 1
Chunk 3: chars 160-200  ← 20-char overlap with chunk 2
"""
import re
from typing import List


class ChunkingUtils:

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500,
                   overlap: int = 100) -> List[str]:
        """
        Split text into overlapping chunks.
        Tries to split at sentence boundaries for cleaner chunks.
        """
        if not text or not text.strip():
            return []

        text = text.strip()

        # Short text: return as single chunk
        if len(text) <= chunk_size:
            return [text]

        # Split into sentences first (cleaner boundaries)
        sentences = ChunkingUtils._split_sentences(text)

        chunks = []
        current_chunk = []
        current_len = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            # If adding this sentence exceeds chunk size, save current chunk
            if current_len + sentence_len > chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk).strip()
                if chunk_text:
                    chunks.append(chunk_text)

                # Overlap: keep last few sentences for context continuity
                overlap_sentences = []
                overlap_len = 0
                for s in reversed(current_chunk):
                    if overlap_len + len(s) <= overlap:
                        overlap_sentences.insert(0, s)
                        overlap_len += len(s)
                    else:
                        break

                current_chunk = overlap_sentences
                current_len = overlap_len

            current_chunk.append(sentence)
            current_len += sentence_len

        # Don't forget the last chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk).strip()
            if chunk_text:
                chunks.append(chunk_text)

        return chunks

    @staticmethod
    def _split_sentences(text: str) -> List[str]:
        """Split text into sentences using punctuation."""
        # Split on . ! ? followed by space or end of string
        sentences = re.split(r'(?<=[.!?])\s+', text)
        # Filter empty strings, strip whitespace
        return [s.strip() for s in sentences if s.strip()]

    @staticmethod
    def chunk_with_metadata(text: str, chunk_size: int = 500,
                            overlap: int = 100) -> List[dict]:
        """
        Return chunks with position metadata.
        Useful for citing which part of transcript an answer came from.
        """
        chunks = ChunkingUtils.chunk_text(text, chunk_size, overlap)
        result = []
        char_pos = 0

        for i, chunk in enumerate(chunks):
            start = text.find(chunk[:50], char_pos)  # approximate position
            result.append({
                "text": chunk,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "char_start": max(0, start),
            })
            if start > 0:
                char_pos = start

        return result
