from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id         = db.Column(db.Integer, primary_key=True)
    email      = db.Column(db.String(150), unique=True, nullable=False)
    username   = db.Column(db.String(100), nullable=False)
    password   = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    theme      = db.Column(db.String(10), default="light")

    translations = db.relationship("Translation", backref="user",
                                   lazy=True, cascade="all, delete-orphan")
    rag_sessions = db.relationship("RAGSession", backref="user",
                                   lazy=True, cascade="all, delete-orphan")

    def set_password(self, raw_password):
        self.password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password, raw_password)

    def to_dict(self):
        return {
            "id":         self.id,
            "email":      self.email,
            "username":   self.username,
            "theme":      self.theme,
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
            "id":              self.id,
            "original_text":   self.original_text,
            "translated_text": self.translated_text,
            "source_lang":     self.source_lang,
            "target_lang":     self.target_lang,
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
            "id":         self.id,
            "session_id": self.session_id,
            "title":      self.title,
            "created_at": self.created_at.strftime("%d %b %Y, %I:%M %p"),
            "word_count": len(self.transcript.split()),
        }