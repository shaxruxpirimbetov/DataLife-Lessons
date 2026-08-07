import os
import uuid
from functools import wraps

from flask import current_app, flash, g, redirect, session, url_for
from werkzeug.utils import secure_filename

from app.db import get_db


def load_logged_in_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        db = get_db()
        g.user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("auth.login"))
        if g.user["role"] != "admin":
            flash("Доступ только для преподавателя.", "error")
            return redirect(url_for("student.dashboard"))
        return view(*args, **kwargs)
    return wrapped


def save_file(file_storage, folder):
    """Сохраняет файл в folder под уникальным именем, возвращает (original_name, stored_name)."""
    os.makedirs(folder, exist_ok=True)
    original_name = secure_filename(file_storage.filename) or "file"
    ext = ""
    if "." in original_name:
        ext = "." + original_name.rsplit(".", 1)[1]
    stored_name = f"{uuid.uuid4().hex}{ext}"
    file_storage.save(os.path.join(folder, stored_name))
    return original_name, stored_name


def has_lesson_access(db, lesson_id, user):
    if user["role"] == "admin":
        return True
    row = db.execute(
        "SELECT 1 FROM lesson_access WHERE lesson_id = ? AND user_id = ?",
        (lesson_id, user["id"]),
    ).fetchone()
    return row is not None
