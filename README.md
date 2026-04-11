# VoiceBridge AI 🎤→🌍

> A production-grade Voice Intelligence Platform built with ASR, NLP, LLM, and RAG.

**Live Demo:** [your-app.onrender.com](https://your-app.onrender.com)

---

## What It Does

| Feature | Tech Used | Concept |
|---|---|---|
| Voice → Text | OpenAI Whisper | ASR (Automatic Speech Recognition) |
| Text Translation | Groq + LLaMA3 | LLM, Prompt Engineering |
| Speech Summarization | Groq + LLaMA3 | Text Summarization, Structured Output |
| Ask Your Transcript | FAISS + sentence-transformers + Groq | RAG (Retrieval Augmented Generation) |
| Semantic Search | FAISS vector index | Vector Embeddings, Similarity Search |

---

## Tech Stack

```
Backend:      Python + Flask
ASR:          OpenAI Whisper (base model)
LLM:          Groq API — LLaMA3-8b (free tier)
Embeddings:   sentence-transformers (all-MiniLM-L6-v2)
Vector DB:    FAISS (Facebook AI Similarity Search)
Frontend:     HTML + CSS + Vanilla JS
Deployment:   Render.com (free tier)
```

---

## Project Structure

```
VoiceBridge/
├── app.py                              # Flask server + all API routes
├── requirements.txt
├── render.yaml                         # Deployment config
├── .env.example
│
├── config/config.py                    # All settings
│
├── models/
│   ├── speech_model.py                 # Whisper ASR wrapper
│   ├── translation_model.py            # Groq LLM translation
│   └── embedding_model.py             # sentence-transformers
│
├── pipeline/
│   ├── translation_pipeline.py         # Audio → text → translate
│   ├── summarization_pipeline.py       # Transcript → structured summary
│   └── rag_pipeline.py                # Full RAG: index + retrieve + generate
│
├── vector_store/
│   └── faiss_store.py                  # FAISS vector database
│
├── utils/
│   ├── audio_utils.py                  # ffmpeg audio preprocessing
│   ├── text_utils.py                   # Text helpers
│   └── chunking_utils.py              # Split text for RAG
│
├── static/
│   ├── css/style.css
│   └── js/app.js
│
└── templates/index.html
```

---

## Running Locally

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/VoiceBridge.git
cd VoiceBridge
```

### 2. Create virtual environment
```powershell
# Windows
python -m venv venv
venv\Scripts\Activate.ps1

# Mac/Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Install ffmpeg (required for audio processing)
```bash
# Windows: download from https://ffmpeg.org → add to PATH
# Mac:     brew install ffmpeg
# Ubuntu:  sudo apt install ffmpeg
```

### 5. Set up environment
```bash
cp .env.example .env
# Edit .env → add your GROQ_API_KEY from console.groq.com (free)
```

### 6. Run
```bash
python app.py
# Open http://localhost:5000
```

---

## Deploying to Render (Free Live URL)

1. Push this repo to GitHub
2. Go to [render.com](https://render.com) → New → Web Service
3. Connect your GitHub repo
4. Render auto-detects `render.yaml`
5. Go to Environment → add `GROQ_API_KEY`
6. Deploy → get your live URL in ~5 minutes

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/transcribe` | Audio file → text (Whisper) |
| POST | `/api/translate` | Text → translated text (Groq) |
| POST | `/api/summarize` | Text → structured summary (Groq) |
| POST | `/api/rag/index` | Index transcript into FAISS |
| POST | `/api/rag/ask` | Ask question over indexed transcript |

---

## How RAG Works (Interview Answer)

```
1. INDEX: Transcript → split into chunks → embed with sentence-transformers
          → store vectors in FAISS

2. QUERY: Question → embed → FAISS similarity search → retrieve top 3 chunks
          → send chunks + question to LLM → grounded answer
```

The key insight: the LLM never guesses. It only answers from retrieved transcript chunks.

---

## License
MIT
