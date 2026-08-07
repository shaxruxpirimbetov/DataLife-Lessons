from flask import Blueprint, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.db import get_db
from app.utils import load_logged_in_user, login_required

auth_bp = Blueprint("auth", __name__)


@auth_bp.before_app_request
def before_request():
    load_logged_in_user()


@auth_bp.route("/", methods=["GET"])
def index():
    if g.user is None:
        return redirect(url_for("auth.login"))
    if g.user["role"] == "admin":
        return redirect(url_for("admin.dashboard"))
    return redirect(url_for("student.dashboard"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("auth.index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        db = get_db()
        user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Неверный логин или пароль.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            session.permanent = True
            return redirect(url_for("auth.index"))

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))


@auth_bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not full_name:
            flash("Укажите имя.", "error")
        elif not check_password_hash(g.user["password_hash"], current_password):
            flash("Текущий пароль указан неверно.", "error")
        elif new_password and new_password != confirm_password:
            flash("Новый пароль и подтверждение не совпадают.", "error")
        elif new_password and len(new_password) < 6:
            flash("Новый пароль должен быть не короче 6 символов.", "error")
        else:
            if new_password:
                db.execute(
                    "UPDATE users SET full_name = ?, password_hash = ? WHERE id = ?",
                    (full_name, generate_password_hash(new_password), g.user["id"]),
                )
            else:
                db.execute(
                    "UPDATE users SET full_name = ? WHERE id = ?",
                    (full_name, g.user["id"]),
                )
            db.commit()
            flash("Данные обновлены.", "success")
            return redirect(url_for("auth.profile"))

    return render_template("profile.html")
