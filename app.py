import os
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

# Use /tmp for SQLite on Render (persistent within session)
db_path = os.environ.get("DATABASE_URL", "sqlite:////tmp/voicebridge.db")
if db_path.startswith("sqlite:///") and not db_path.startswith("sqlite:////"):
    db_path = "sqlite:////tmp/voicebridge.db"

app.config["SECRET_KEY"]                     = cfg.SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"]        = db_path
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"]             = 50 * 1024 * 1024

# ── Inline models ─────────────────────────────────────────────────────────
db = SQLAlchemy()
db.init_app(app)

class User(UserMixin, db.Model):
    __tablename__ = "users"
    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(150), unique=True, nullable=False)
    username   = db.Column(db.String(100), nullable=False)
    password   = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    theme      = db.Column(db.String(10), default="light")
    translations = db.relationship("Translation", backref="user", lazy=True, cascade="all, delete-orphan")
    rag_sessions = db.relationship("RAGSession", backref="user", lazy=True, cascade="all, delete-orphan")

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
    __tablename__ = "translations"
    id              = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    original_text   = db.Column(db.Text, nullable=False)
    translated_text = db.Column(db.Text, nullable=False)
    source_lang     = db.Column(db.String(10), nullable=False)
    target_lang     = db.Column(db.String(10), nullable=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "original_text": self.original_text,
            "translated_text": self.translated_text,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
            "created_at": self.created_at.strftime("%d %b %Y, %I:%M %p"),
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

# ── Lazy pipelines ────────────────────────────────────────────────────────
_trans = _rag = _sum = None

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
        return render_template("index.html", user=current_user)
    return redirect(url_for("login_page"))

@app.route("/login")
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("auth.html", mode="login")

@app.route("/signup")
def signup_page():
    if current_user.is_authenticated:
        return redirect(url_for("index"))
    return render_template("auth.html", mode="signup")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login_page"))

@app.route("/health")
def health():
    return jsonify({"status": "ok", "model": cfg.GROQ_MODEL})

@app.route("/ping")
def ping():
    return "pong", 200

# ── Auth API ──────────────────────────────────────────────────────────────
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
    logger.info(f"New user: {email}")
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
    logger.info(f"Login: {email}")
    return jsonify({"message": "Logged in", "user": user.to_dict()})


@app.route("/api/auth/theme", methods=["POST"])
@login_required
def set_theme():
    data = request.get_json() or {}
    current_user.theme = data.get("theme", "light")
    db.session.commit()
    return jsonify({"theme": current_user.theme})

# ── Translation ───────────────────────────────────────────────────────────
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


@app.route("/api/translate", methods=["POST"])
@login_required
def translate():
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text provided"}), 400
    try:
        result = get_trans().translate(
            text        = data["text"],
            source_lang = data.get("source_lang", "auto"),
            target_lang = data.get("target_lang", "en")
        )
        t = Translation(
            user_id         = current_user.id,
            original_text   = data["text"],
            translated_text = result,
            source_lang     = data.get("source_lang", "auto"),
            target_lang     = data.get("target_lang", "en"),
        )
        db.session.add(t)
        db.session.commit()
        return jsonify({"translated": result, "original": data["text"]})
    except Exception as e:
        logger.error(f"Translate: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/history")
@login_required
def get_history():
    items = (Translation.query
             .filter_by(user_id=current_user.id)
             .order_by(Translation.created_at.desc())
             .limit(50).all())
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
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text provided"}), 400
    try:
        result = get_sum().summarize(data["text"], style=data.get("style", "detailed"))
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
            text=data["text"], session_id=data.get("session_id"),
            metadata={"user_id": current_user.id}
        )
        rs = RAGSession(
            user_id=current_user.id, session_id=sid,
            title=data.get("title", data["text"][:60] + "..."),
            transcript=data["text"]
        )
        db.session.add(rs)
        db.session.commit()
        return jsonify({
            "session_id":     sid,
            "chunks_created": get_rag().get_chunk_count(sid),
            "message":        "Indexed successfully"
        })
    except Exception as e:
        logger.error(f"RAG index: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/rag/ask", methods=["POST"])
@login_required
def rag_ask():
    data = request.get_json()
    if not data or not data.get("question"):
        return jsonify({"error": "No question"}), 400
    if not data.get("session_id"):
        return jsonify({"error": "No session_id"}), 400
    try:
        return jsonify(get_rag().ask(
            question=data["question"],
            session_id=data["session_id"],
            top_k=data.get("top_k", 3)
        ))
    except Exception as e:
        logger.error(f"RAG ask: {e}")
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
        pdf.cell(0, 6, f"User: {current_user.username} | {datetime.now().strftime('%d %b %Y %I:%M %p')}", ln=True)
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
        return send_file(buf, mimetype="application/pdf",
                         as_attachment=True, download_name="voicebridge-export.pdf")
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/improve-text", methods=["POST"])
@login_required
def improve_text():
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text"}), 400
    try:
        from groq import Groq
        client = Groq(api_key=cfg.GROQ_API_KEY)
        res = client.chat.completions.create(
            model=cfg.GROQ_MODEL, max_tokens=1024, temperature=0.3,
            messages=[
                {"role": "system", "content": "Fix grammar and clarity. Return ONLY corrected text."},
                {"role": "user", "content": data["text"]}
            ]
        )
        return jsonify({"improved": res.choices[0].message.content.strip()})
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
        res = client.chat.completions.create(
            model=cfg.GROQ_MODEL, max_tokens=10, temperature=0,
            messages=[
                {"role": "system", "content": "Detect language. Reply ONLY with ISO 639-1 code: en, hi, es, fr etc."},
                {"role": "user", "content": data["text"][:300]}
            ]
        )
        return jsonify({"language": res.choices[0].message.content.strip().lower()[:5]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

        # ═══════════════════════════════════════════════════════
# ADD THESE ROUTES TO YOUR app.py
# Insert them before the "with app.app_context():" line
# ═══════════════════════════════════════════════════════

# ── Landing page (public) ─────────────────────────────────────────────────
@app.route("/landing")
def landing():
    return render_template("landing.html")

# Make landing the default for non-logged-in users
# REPLACE your existing index route with this:
@app.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("landing.html")

# ── Dashboard ─────────────────────────────────────────────────────────────
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html", user=current_user)

# ── App (the translator) ──────────────────────────────────────────────────
@app.route("/app")
@login_required
def app_page():
    return render_template("index.html", user=current_user)

# ── Meeting notes generator ───────────────────────────────────────────────
@app.route("/api/meeting-notes", methods=["POST"])
@login_required
def meeting_notes():
    """
    FEATURE: Generate professional meeting notes from transcript.
    Returns structured: date, attendees (inferred), decisions, action items, next steps.
    """
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text provided"}), 400
    try:
        from groq import Groq
        import json, re
        client = Groq(api_key=cfg.GROQ_API_KEY)
        system = """You are a professional meeting notes writer.
Convert the transcript into structured meeting notes. Return ONLY valid JSON:
{
  "title": "Meeting title inferred from content",
  "date": "Today's date or as mentioned",
  "summary": "2-3 sentence executive summary",
  "key_decisions": ["decision 1", "decision 2"],
  "action_items": [
    {"task": "task description", "owner": "person name or TBD", "deadline": "deadline or TBD"}
  ],
  "next_steps": ["next step 1", "next step 2"],
  "topics_discussed": ["topic 1", "topic 2", "topic 3"]
}"""
        resp = client.chat.completions.create(
            model=cfg.GROQ_MODEL, max_tokens=1024, temperature=0.3,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"Generate meeting notes from:\n\n{data['text']}"}
            ]
        )
        raw = resp.choices[0].message.content.strip()
        raw = re.sub(r"```[a-z]*|```", "", raw).strip()
        result = json.loads(raw)
        return jsonify(result)
    except json.JSONDecodeError:
        return jsonify({"raw": resp.choices[0].message.content.strip()})
    except Exception as e:
        logger.error(f"Meeting notes: {e}")
        return jsonify({"error": str(e)}), 500


# ── Translation confidence score ──────────────────────────────────────────
@app.route("/api/translate-with-confidence", methods=["POST"])
@login_required
def translate_with_confidence():
    """
    USP FEATURE: Translate AND rate confidence + flag ambiguous phrases.
    Returns: translation, confidence score (1-10), ambiguous_phrases, notes
    """
    data = request.get_json()
    if not data or not data.get("text"):
        return jsonify({"error": "No text provided"}), 400
    try:
        from groq import Groq
        import json, re
        target = data.get("target_lang", "en")
        source = data.get("source_lang", "auto")
        lang_names = {
            "en":"English","hi":"Hindi","es":"Spanish","fr":"French",
            "de":"German","ta":"Tamil","te":"Telugu","bn":"Bengali",
            "ja":"Japanese","zh":"Chinese","ar":"Arabic","pt":"Portuguese",
            "ru":"Russian","ko":"Korean","auto":"detected language"
        }
        client = Groq(api_key=cfg.GROQ_API_KEY)
        system = f"""Translate from {lang_names.get(source,'auto')} to {lang_names.get(target,'English')}.
Then rate your translation. Return ONLY valid JSON:
{{
  "translation": "the translated text",
  "confidence": 8,
  "confidence_reason": "why this score",
  "ambiguous_phrases": ["phrase that was hard to translate"],
  "notes": "any important translation notes or cultural context"
}}
Confidence: 9-10=perfect, 7-8=good, 5-6=some ambiguity, below 5=difficult."""

        resp = client.chat.completions.create(
            model=cfg.GROQ_MODEL, max_tokens=1024, temperature=0.1,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": data["text"]}
            ]
        )
        raw    = re.sub(r"```[a-z]*|```", "", resp.choices[0].message.content.strip()).strip()
        result = json.loads(raw)

        # Save to history
        t = Translation(
            user_id=current_user.id,
            original_text=data["text"],
            translated_text=result.get("translation",""),
            source_lang=source, target_lang=target
        )
        db.session.add(t)
        db.session.commit()
        return jsonify(result)
    except Exception as e:
        logger.error(f"Translate+confidence: {e}")
        return jsonify({"error": str(e)}), 500

# ── Init ──────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    logger.info(f"DB ready at {db_path} | Model: {cfg.GROQ_MODEL}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=cfg.PORT, debug=cfg.FLASK_DEBUG)