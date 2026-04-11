"""
pipeline/rag_pipeline.py
CONCEPT: Retrieval Augmented Generation (RAG)

This is the most important file in the project for your resume.
RAG = Retrieval + Augmented + Generation

FULL FLOW:
─────────────────────────────────────────────────────────────
INDEX PHASE (happens once per transcript):
  Transcript text
      ↓
  Split into chunks (chunking_utils)
  ["I talked about pricing...", "The team discussed...", ...]
      ↓
  Embed each chunk (embedding_model → sentence-transformers)
  [[0.2, 0.8, ...], [0.1, 0.9, ...], ...]
      ↓
  Store in FAISS vector index (faiss_store)

QUERY PHASE (happens on each question):
  User question: "What did you say about pricing?"
      ↓
  Embed the question → vector [0.3, 0.7, ...]
      ↓
  FAISS similarity search → find top 3 most similar chunks
  ["chunk about pricing 1", "chunk about pricing 2", ...]
      ↓
  Build prompt: system + retrieved chunks + question
      ↓
  Send to Groq LLM
      ↓
  LLM answers using ONLY the retrieved chunks as context
      ↓
  Return answer + sources (which chunks were used)
─────────────────────────────────────────────────────────────

WHY RAG IS BETTER THAN JUST ASKING THE LLM:
- LLM alone: can hallucinate, doesn't know YOUR transcript
- RAG: grounds the answer in YOUR actual words
- Every answer is traceable back to a specific part of transcript
"""
import uuid
import logging
from typing import Optional
from groq import Groq

from models.embedding_model import EmbeddingModel
from vector_store.faiss_store import FAISSStore
from utils.chunking_utils import ChunkingUtils

logger = logging.getLogger(__name__)


class RAGPipeline:
    def __init__(self, config):
        self.config = config
        self.embedding_model = EmbeddingModel(model_name=config.EMBEDDING_MODEL)
        self.vector_store = FAISSStore(dimension=384)
        self.groq_client = Groq(api_key=config.GROQ_API_KEY)
        self.groq_model = config.GROQ_MODEL
        logger.info("RAGPipeline ready")

    # ── INDEXING ──────────────────────────────────────────────────────────

    def index_transcript(self, text: str, session_id: Optional[str] = None,
                         metadata: dict = None) -> str:
        """
        STEP 1 of RAG: Index a transcript into the vector store.

        1. Split text into chunks
        2. Embed each chunk using sentence-transformers
        3. Store vectors in FAISS

        Returns session_id (use this for all future queries on this transcript)
        """
        if session_id is None:
            session_id = str(uuid.uuid4())[:8]  # short unique ID

        # Step 1: Chunk the transcript
        chunk_data = ChunkingUtils.chunk_with_metadata(
            text,
            chunk_size=self.config.CHUNK_SIZE,
            overlap=self.config.CHUNK_OVERLAP
        )

        if not chunk_data:
            raise ValueError("No chunks created — text might be empty")

        chunks = [c["text"] for c in chunk_data]
        chunk_metadata = [
            {**c, **(metadata or {}), "session_id": session_id}
            for c in chunk_data
        ]

        logger.info(f"Indexing {len(chunks)} chunks for session {session_id}")

        # Step 2: Embed all chunks at once (batch for efficiency)
        embeddings = self.embedding_model.embed(chunks)

        # Step 3: Store in FAISS
        self.vector_store.add_chunks(session_id, chunks, embeddings, chunk_metadata)

        logger.info(f"Indexed {len(chunks)} chunks into session {session_id}")
        return session_id

    # ── QUERYING ──────────────────────────────────────────────────────────

    def ask(self, question: str, session_id: str, top_k: int = 3) -> dict:
        """
        STEP 2 of RAG: Answer a question using the indexed transcript.

        1. Embed the question
        2. FAISS similarity search → retrieve top_k relevant chunks
        3. Build prompt with retrieved context
        4. Send to Groq LLM → get answer
        5. Return answer + source chunks (for transparency)
        """
        if not question.strip():
            return {"error": "Empty question"}

        # Step 1: Embed the question
        question_embedding = self.embedding_model.embed_single(question)

        # Step 2: Retrieve most relevant chunks from FAISS
        retrieved = self.vector_store.search(
            session_id=session_id,
            query_embedding=question_embedding,
            top_k=top_k
        )

        if not retrieved:
            return {
                "answer": "No relevant content found. Please index a transcript first.",
                "sources": [],
                "session_id": session_id
            }

        # Step 3: Build RAG prompt
        # PROMPT ENGINEERING: We inject the retrieved chunks as context
        # This "augments" the LLM's generation with real retrieved information
        context = "\n\n---\n\n".join([
            f"[Chunk {r['rank']} | Relevance: {r['score']:.2f}]\n{r['chunk']}"
            for r in retrieved
        ])

        system_prompt = """You are an AI assistant that answers questions about spoken transcripts.
You will be given relevant excerpts from a transcript and a question.

RULES:
- Answer ONLY based on the provided transcript excerpts
- If the answer isn't in the excerpts, say "I couldn't find that in the transcript"
- Be specific and quote relevant parts when helpful
- Be concise but complete"""

        user_prompt = f"""TRANSCRIPT EXCERPTS:
{context}

QUESTION: {question}

Answer based on the transcript excerpts above:"""

        # Step 4: LLM generates answer from retrieved context
        response = self.groq_client.chat.completions.create(
            model=self.groq_model,
            max_tokens=512,
            temperature=0.2,  # low temperature for factual answers
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )

        answer = response.choices[0].message.content.strip()

        return {
            "answer": answer,
            "question": question,
            "sources": [
                {
                    "chunk": r["chunk"][:200] + "..." if len(r["chunk"]) > 200 else r["chunk"],
                    "relevance_score": round(r["score"], 3),
                    "rank": r["rank"]
                }
                for r in retrieved
            ],
            "session_id": session_id,
            "chunks_searched": self.vector_store.get_chunk_count(session_id)
        }

    def get_chunk_count(self, session_id: str) -> int:
        return self.vector_store.get_chunk_count(session_id)

    def clear_session(self, session_id: Optional[str] = None):
        self.vector_store.clear_session(session_id)
