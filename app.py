"""
app.py — VoiceBridge AI — Complete fixed version
"""
import os
import time
import logging
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, send_file)
from flask_cors import CORS
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

from config.config import Config
cfg = Config()

db_url = os.environ.get("DATABASE_URL", "sqlite:////tmp/voicebridge.db")
if db_url.startswith("sqlite:///") and not db_url.startswith("sqlite:////"):
    db_url = "sqlite:////tmp/voicebridge.db"

app.config["SECRET_KEY"]                     = cfg.SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"]        = db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"]             = 50 * 1024 * 1024

_START_TIME = time.time()

# ── DB Models ─────────────────────────────────────────────────────────────
db = SQLAlchemy()
db.init_app(app)


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id           = db.Column(db.Integer, primary_key=True)
    email        = db.Column(db.String(150), unique=True, nullable=False)
    username     = db.Column(db.String(100), nullable=False)
    password     = db.Column(db.String(256), nullable=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    theme        = db.Column(db.String(10), default="light")
    translations = db.relationship("Translation", backref="user",
                                   lazy=True, cascade="all, delete-orphan")
    rag_sessions = db.relationship("RAGSession", backref="user",
                                   lazy=True, cascade="all, delete-orphan")

    def set_password(self, raw):
        self.password = generate_password_hash(raw)

    def check_password(self, raw):
        return check_password_hash(self.password, raw)

    def to_dict(self):
        return {
            "id": self.id, "email": self.email,
            "username": self.username, "theme": self.theme,
            "created_at": self.created_at.isoformat(),
        }


class Translation(db.Model):
    __tablename__   = "translations"
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_text   = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=False)
    source_lang     = db.Column(db.String(10), nullable=False)
    target_lang     = db.Column(db.String(10), nullable=False)
    quality_score   = db.Column(db.Float, nullable=True)
    latency_ms      = db.Column(db.Float, nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "original_text":   self.original_text,
            "translated_text": self.translated_text,
            "source_lang":     self.source_lang,
            "target_lang":     self.target_lang,
            "quality_score":   self.quality_score,
            "created_at":      self.created_at.strftime("%d %b %Y, %I:%M %p"),
        }


class RAGSession(db.Model):
    __tablename__ = "rag_sessions"
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    session_id = db.Column(db.String(20), nullable=False)
    title      = db.Column(db.String(200), default="Untitled Session")
    transcript = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id, "session_id": self.session_id,
            "title": self.title,
            "created_at": self.created_at.strftime("%d %b %Y, %I:%M %p"),
            "word_count": len(self.transcript.split()),
        }


# ── Login manager ─────────────────────────────────────────────────────────
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login_page"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ── Lazy pipelines — shared embedding model ───────────────────────────────
_trans = _rag = _sum = _embedding = None


def get_embedding():
    global _embedding
    if not _embedding:
        from models.embedding_model import EmbeddingModel
        _embedding = EmbeddingModel(model_name=cfg.EMBEDDING_MODEL)
    return _embedding


def get_trans():
    global _trans
    if not _trans:
        from pipeline.translation_pipeline import TranslationPipeline
        _trans = TranslationPipeline(cfg)
    return _trans


def get_rag():
    global _rag
    if not _rag:
        from pipeline.rag_pipeline import RAGPipeline
        _rag = RAGPipeline(cfg)
        _rag.embedding_model = get_embedding()
    return _rag


def get_sum():
    global _sum
    if not _sum:
        from pipeline.summarization_pipeline import SummarizationPipeline
        _sum = SummarizationPipeline(cfg)
    return _sum


# ── Pages ─────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")


@app.route("/app")
@login_required
def app_page():
    return render_template("index.html", user=current_user)


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)


@app.route("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="login")


@app.route("/signup")
def signup_page():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("auth.html", mode="signup")


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login_page"))


# ── Health ────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    import platform
    from utils.request_logger import get_stats
    uptime_s        = int(time.time() - _START_TIME)
    hours, rem      = divmod(uptime_s, 3600)
    mins, secs      = divmod(rem, 60)
    db_ok = True
    try:
        db.session.execute(db.text("SELECT 1"))
    except Exception:
        db_ok = False
    return jsonify({
        "status":  "healthy" if db_ok else "degraded",
        "uptime":  f"{hours}h {mins}m {secs}s",
        "models": {
            "llm":       cfg.GROQ_MODEL,
            "asr":       f"whisper-{cfg.WHISPER_MODEL_SIZE}",
            "embedding": cfg.EMBEDDING_MODEL,
            "vector_db": "FAISS IndexFlatIP (dim=384)",
        },
        "database":      "ok" if db_ok else "error",
        "python":        platform.python_version(),
        "request_stats": get_stats(),
    })


@app.route("/ping")
def ping():
    return "pong", 200


# ── Auth ──────────────────────────────────────────────────────────────────
@app.route("/api/auth/signup", methods=["POST"])
def signup():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    email    = data.get("email", "").strip().lower()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    if not email or not username or not password:
        return jsonify({"error": "All fields required"}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be 6+ characters"}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already registered"}), 400
    user = User(email=email, username=username)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    login_user(user)
    return jsonify({"message": "Account created", "user": user.to_dict()})


@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data"}), 400
    email    = data.get("email", "").strip().lower()
    password = data.get("password", "")
    user     = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid email or password"}), 401
    login_user(user, remember=data.get("remember", False))
    return jsonify({"message": "Logged in", "user": user.to_dict()})


@app.route("/api/auth/theme", methods=["POST"])
@login_required
def set_theme():
    data = request.get_json() or {}
    current_user.theme = data.get("theme", "light")
    db.session.commit()
    return jsonify({"theme": current_user.theme})


# ── Translation ───────────────────────────────────────────────────────────
@app.route("/api/translate", methods=["POST"])
@login_required
def translate():
    from utils.request_logger import log_request, Timer
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text provided"}), 400
    try:
        with Timer() as t:
            result = get_trans().translate(
                text        = data["text"],
                source_lang = data.get("source_lang", "auto"),
                target_lang = data.get("target_lang", "en")
            )
        log_request("/api/translate", cfg.GROQ_MODEL, t.elapsed_ms, True,
                    user_id=current_user.id)

        # Quality score via semantic similarity
        quality_score = None
        try:
            from utils.metrics import TranslationMetrics
            quality_score = TranslationMetrics(
                get_embedding()
            ).semantic_similarity(data["text"], result)
        except Exception:
            pass

        rec = Translation(
            user_id         = current_user.id,
            original_text   = data["text"],
            translated_text = result,
            source_lang     = data.get("source_lang", "auto"),
            target_lang     = data.get("target_lang", "en"),
            quality_score   = quality_score,
            latency_ms      = t.elapsed_ms,
        )
        db.session.add(rec)
        db.session.commit()

        return jsonify({
            "translated":    result,
            "original":      data["text"],
            "latency_ms":    round(t.elapsed_ms, 1),
            "quality_score": quality_score,
        })
    except Exception as e:
        logger.error(f"Translate: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/transcribe", methods=["POST"])
@login_required
def transcribe():
    if "audio" not in request.files:
        return jsonify({"error": "No audio file"}), 400
    try:
        lang = request.form.get("lang") or None
        text = get_trans().speech_to_text(request.files["audio"], language=lang)
        return jsonify({"text": text})
    except Exception as e:
        logger.error(f"Transcribe: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/history")
@login_required
def get_history():
    limit = request.args.get("limit", 50, type=int)
    items = (Translation.query
             .filter_by(user_id=current_user.id)
             .order_by(Translation.created_at.desc())
             .limit(limit).all())
    return jsonify([t.to_dict() for t in items])


@app.route("/api/history/<int:tid>", methods=["DELETE"])
@login_required
def delete_history(tid):
    t = Translation.query.filter_by(id=tid, user_id=current_user.id).first()
    if not t:
        return jsonify({"error": "Not found"}), 404
    db.session.delete(t)
    db.session.commit()
    return jsonify({"message": "Deleted"})


# ── Summarize ─────────────────────────────────────────────────────────────
@app.route("/api/summarize", methods=["POST"])
@login_required
def summarize():
    from utils.request_logger import log_request, Timer
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text provided"}), 400
    try:
        with Timer() as t:
            result = get_sum().summarize(
                data["text"], style=data.get("style", "detailed")
            )
        log_request("/api/summarize", cfg.GROQ_MODEL, t.elapsed_ms, True,
                    user_id=current_user.id)
        result["latency_ms"] = round(t.elapsed_ms, 1)
        return jsonify(result)
    except Exception as e:
        logger.error(f"Summarize: {e}")
        return jsonify({"error": str(e)}), 500


# ── RAG ───────────────────────────────────────────────────────────────────
@app.route("/api/rag/index", methods=["POST"])
@login_required
def rag_index():
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text"}), 400
    try:
        sid = get_rag().index_transcript(
            text       = data["text"],
            session_id = data.get("session_id"),
            metadata   = {"user_id": current_user.id}
        )
        rs = RAGSession(
            user_id    = current_user.id,
            session_id = sid,
            title      = data.get("title", data["text"][:60] + "..."),
            transcript = data["text"]
        )
        db.session.add(rs)
        db.session.commit()
        return jsonify({
            "session_id":     sid,
            "chunks_created": get_rag().get_chunk_count(sid)
        })
    except Exception as e:
        logger.error(f"RAG index: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/rag/ask", methods=["POST"])
@login_required
def rag_ask():
    from utils.request_logger import log_request, Timer
    from utils.metrics import RAGMetrics
    data = request.get_json()
    if not data or not data.get("question"):
        return jsonify({"error": "No question"}), 400
    if not data.get("session_id"):
        return jsonify({"error": "No session_id"}), 400
    try:
        with Timer() as t:
            result = get_rag().ask(
                question   = data["question"],
                session_id = data["session_id"],
                top_k      = data.get("top_k", 3)
            )
        log_request("/api/rag/ask", cfg.GROQ_MODEL, t.elapsed_ms, True,
                    user_id=current_user.id)
        if result.get("sources"):
            result["retrieval_metrics"] = RAGMetrics.retrieval_report(
                result["sources"]
            )
        result["latency_ms"] = round(t.elapsed_ms, 1)
        return jsonify(result)
    except Exception as e:
        logger.error(f"RAG ask: {e}")
        return jsonify({"error": str(e)}), 500


# ── Meeting Notes ─────────────────────────────────────────────────────────
@app.route("/api/meeting-notes", methods=["POST"])
@login_required
def meeting_notes():
    import json, re
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text"}), 400
    try:
        from groq import Groq
        client = Groq(api_key=cfg.GROQ_API_KEY)
        system = (
            'Convert this transcript into professional meeting notes. '
            'Return ONLY valid JSON with no markdown:\n'
            '{"title":"meeting title","summary":"2-3 sentence summary",'
            '"key_decisions":["decision1"],'
            '"action_items":[{"task":"task","owner":"person or TBD","deadline":"TBD"}],'
            '"next_steps":["step1"],"topics_discussed":["topic1"]}'
        )
        resp = client.chat.completions.create(
            model    = cfg.GROQ_MODEL,
            max_tokens = 1024,
            temperature = 0.3,
            messages = [
                {"role": "system", "content": system},
                {"role": "user",   "content": f"Transcript:\n\n{data['text']}"}
            ]
        )
        raw = re.sub(r"```[a-z]*|```", "", resp.choices[0].message.content).strip()
        return jsonify(json.loads(raw))
    except json.JSONDecodeError:
        return jsonify({"raw": resp.choices[0].message.content.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Translation with Confidence Score ────────────────────────────────────
@app.route("/api/translate-with-confidence", methods=["POST"])
@login_required
def translate_with_confidence():
    import json, re
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text"}), 400
    try:
        from groq import Groq
        lang_names = {
            "en": "English",    "hi": "Hindi",      "es": "Spanish",
            "fr": "French",     "de": "German",     "ta": "Tamil",
            "te": "Telugu",     "bn": "Bengali",    "ja": "Japanese",
            "zh": "Chinese",    "ar": "Arabic",     "pt": "Portuguese",
            "ru": "Russian",    "ko": "Korean",     "auto": "detected language"
        }
        client = Groq(api_key=cfg.GROQ_API_KEY)
        src = data.get("source_lang", "auto")
        tgt = data.get("target_lang", "en")

        # Step 1: Translate
        trans_resp = client.chat.completions.create(
            model       = cfg.GROQ_MODEL,
            max_tokens  = 512,
            temperature = 0.1,
            messages    = [
                {
                    "role":    "system",
                    "content": (
                        f"Translate from {lang_names.get(src, 'the source language')} "
                        f"to {lang_names.get(tgt, 'English')}. "
                        f"Return ONLY the translated text."
                    )
                },
                {"role": "user", "content": data["text"]}
            ]
        )
        translation = trans_resp.choices[0].message.content.strip()

        # Step 2: Rate confidence
        rate_resp = client.chat.completions.create(
            model       = cfg.GROQ_MODEL,
            max_tokens  = 200,
            temperature = 0.1,
            messages    = [
                {
                    "role":    "system",
                    "content": (
                        'Rate this translation quality. '
                        'Return ONLY valid JSON with no markdown: '
                        '{"confidence":8,"reason":"brief reason",'
                        '"ambiguous":[],"notes":""}'
                    )
                },
                {
                    "role":    "user",
                    "content": (
                        f"Original: {data['text']}\n"
                        f"Translation: {translation}"
                    )
                }
            ]
        )
        raw = re.sub(r"```[a-z]*|```", "",
                     rate_resp.choices[0].message.content).strip()
        try:
            rating = json.loads(raw)
        except Exception:
            rating = {
                "confidence": 7,
                "reason":     "Translation completed",
                "ambiguous":  [],
                "notes":      ""
            }

        # Step 3: Semantic similarity
        semantic_sim = None
        try:
            from utils.metrics import TranslationMetrics
            semantic_sim = TranslationMetrics(
                get_embedding()
            ).semantic_similarity(data["text"], translation)
        except Exception:
            pass

        # Save to history
        rec = Translation(
            user_id         = current_user.id,
            original_text   = data["text"],
            translated_text = translation,
            source_lang     = src,
            target_lang     = tgt,
            quality_score   = rating.get("confidence"),
        )
        db.session.add(rec)
        db.session.commit()

        return jsonify({
            "translation":        translation,
            "confidence":         rating.get("confidence", 7),
            "confidence_reason":  rating.get("reason", ""),
            "ambiguous_phrases":  rating.get("ambiguous", []),
            "notes":              rating.get("notes", ""),
            "semantic_similarity": semantic_sim,
        })
    except Exception as e:
        logger.error(f"Translate+confidence: {e}")
        return jsonify({"error": str(e)}), 500


# ── Text improvements ─────────────────────────────────────────────────────
@app.route("/api/improve-text", methods=["POST"])
@login_required
def improve_text():
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text"}), 400
    try:
        from groq import Groq
        client = Groq(api_key=cfg.GROQ_API_KEY)
        resp = client.chat.completions.create(
            model       = cfg.GROQ_MODEL,
            max_tokens  = 1024,
            temperature = 0.3,
            messages    = [
                {"role": "system",
                 "content": "Fix grammar, spelling and clarity. Return ONLY corrected text."},
                {"role": "user", "content": data["text"]}
            ]
        )
        return jsonify({"improved": resp.choices[0].message.content.strip()})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/detect-language", methods=["POST"])
@login_required
def detect_language():
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text"}), 400
    try:
        from groq import Groq
        client = Groq(api_key=cfg.GROQ_API_KEY)
        resp = client.chat.completions.create(
            model       = cfg.GROQ_MODEL,
            max_tokens  = 10,
            temperature = 0,
            messages    = [
                {"role": "system",
                 "content": "Detect language. Reply ONLY with ISO 639-1 code: en, hi, es, fr etc."},
                {"role": "user", "content": data["text"][:300]}
            ]
        )
        return jsonify({
            "language": resp.choices[0].message.content.strip().lower()[:5]
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── PDF Export ────────────────────────────────────────────────────────────
@app.route("/api/export/pdf", methods=["POST"])
@login_required
def export_pdf():
    import io
    from fpdf import FPDF
    data = request.get_json() or {}
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.set_font("Helvetica", "B", 20)
        pdf.set_text_color(14, 165, 233)
        pdf.cell(0, 12, "VoiceBridge AI - Export", ln=True)
        pdf.set_draw_color(14, 165, 233)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(
            0, 6,
            f"User: {current_user.username} | "
            f"{datetime.now().strftime('%d %b %Y %I:%M %p')}",
            ln=True
        )
        pdf.ln(4)

        def section(title, text):
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(14, 165, 233)
            pdf.cell(0, 8, title, ln=True)
            pdf.set_font("Helvetica", "", 11)
            pdf.set_text_color(30, 30, 30)
            safe = str(text).encode("latin-1", errors="replace").decode("latin-1")
            pdf.multi_cell(0, 7, safe)
            pdf.ln(4)

        if data.get("original"):   section("Original Text", data["original"])
        if data.get("translated"): section("Translation",   data["translated"])
        if data.get("summary"):    section("Summary",       data["summary"])

        buf = io.BytesIO(bytes(pdf.output()))
        buf.seek(0)
        return send_file(
            buf, mimetype="application/pdf",
            as_attachment=True,
            download_name="voicebridge-export.pdf"
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Startup ───────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    logger.info(f"VoiceBridge AI ready | model={cfg.GROQ_MODEL} | db={db_url}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=cfg.PORT, debug=cfg.FLASK_DEBUG)