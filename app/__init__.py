import os
import secrets
from datetime import date, timedelta

from flask import Flask


def due_status(due_date):
    """Возвращает 'overdue' / 'soon' / 'normal' для бейджа срока сдачи."""
    if not due_date:
        return None
    try:
        parsed = date.fromisoformat(due_date)
    except ValueError:
        return None
    today = date.today()
    if parsed < today:
        return "overdue"
    if parsed <= today + timedelta(days=2):
        return "soon"
    return "normal"


def create_app():
    app = Flask(__name__, instance_relative_config=True)

    os.makedirs(app.instance_path, exist_ok=True)
    os.makedirs(os.path.join(app.instance_path, "uploads", "lessons"), exist_ok=True)
    os.makedirs(os.path.join(app.instance_path, "uploads", "submissions"), exist_ok=True)

    # Секретный ключ сессии — генерируется один раз и сохраняется на диск
    secret_path = os.path.join(app.instance_path, "secret.key")
    if not os.path.exists(secret_path):
        with open(secret_path, "w") as f:
            f.write(secrets.token_hex(32))
    with open(secret_path) as f:
        app.config["SECRET_KEY"] = f.read().strip()

    app.config["DATABASE"] = os.path.join(app.instance_path, "app.db")
    app.config["UPLOAD_LESSONS"] = os.path.join(app.instance_path, "uploads", "lessons")
    app.config["UPLOAD_SUBMISSIONS"] = os.path.join(app.instance_path, "uploads", "submissions")
    app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB на файл

    from app.auth import auth_bp
    from app.routes_admin import admin_bp
    from app.routes_student import student_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(student_bp)

    from app.db import close_db
    app.teardown_appcontext(close_db)

    app.jinja_env.filters["due_status"] = due_status

    return app
