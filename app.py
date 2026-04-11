import os
import logging
from flask import (Flask, render_template, request, jsonify,
                   redirect, url_for, send_file)
from flask_cors import CORS
from flask_login import (LoginManager, login_user, logout_user,
                         login_required, current_user)
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

from config.config import Config
cfg = Config()

app.config["SECRET_KEY"]                     = cfg.SECRET_KEY
app.config["SQLALCHEMY_DATABASE_URI"]        = cfg.DATABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"]             = 50 * 1024 * 1024

from auth.models import db, User, Translation, RAGSession
db.init_app(app)

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
    return jsonify({"status": "ok"})

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
        logger.info(f"Translating with model: {cfg.GROQ_MODEL}")
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
        logger.error(f"Translate error: {e}")
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
        logger.info(f"Summarizing with model: {cfg.GROQ_MODEL}")
        result = get_sum().summarize(
            text  = data["text"],
            style = data.get("style", "detailed")
        )
        return jsonify(result)
    except Exception as e:
        logger.error(f"Summarize error: {e}")
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
            question   = data["question"],
            session_id = data["session_id"],
            top_k      = data.get("top_k", 3)
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
    from datetime import datetime
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
        pdf.cell(0, 6,
            f"Exported: {datetime.now().strftime('%d %b %Y, %I:%M %p')} | "
            f"User: {current_user.username}", ln=True)
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
                         as_attachment=True,
                         download_name="voicebridge-export.pdf")
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
                {"role": "system", "content":
                    "Fix grammar, spelling and clarity. "
                    "Keep the same language and meaning. "
                    "Return ONLY the corrected text."},
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
                {"role": "system", "content":
                    "Detect the language. Reply with ONLY the ISO 639-1 code like: en, hi, es, fr"},
                {"role": "user", "content": data["text"][:300]}
            ]
        )
        return jsonify({"language": res.choices[0].message.content.strip().lower()[:5]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Init ──────────────────────────────────────────────────────────────────
with app.app_context():
    db.create_all()
    logger.info(f"Database ready | Model: {cfg.GROQ_MODEL}")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=cfg.PORT, debug=cfg.FLASK_DEBUG)