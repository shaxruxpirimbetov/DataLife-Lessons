import os
import secrets

from flask import (
    Blueprint, current_app, flash, g, redirect, render_template,
    request, send_from_directory, url_for
)
from werkzeug.security import generate_password_hash

from app.db import get_db
from app.utils import admin_required, save_file

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/dashboard")
@admin_required
def dashboard():
    db = get_db()
    lessons = db.execute(
        "SELECT l.*, "
        "(SELECT COUNT(*) FROM lesson_access WHERE lesson_id = l.id) AS student_count, "
        "(SELECT COUNT(*) FROM submissions WHERE lesson_id = l.id) AS submission_count "
        "FROM lessons l ORDER BY l.created_at DESC"
    ).fetchall()
    student_count = db.execute("SELECT COUNT(*) FROM users WHERE role = 'student'").fetchone()[0]
    return render_template("admin_dashboard.html", lessons=lessons, student_count=student_count)


@admin_bp.route("/students")
@admin_required
def students():
    db = get_db()
    rows = db.execute(
        "SELECT u.id, u.full_name, u.username, "
        "(SELECT COUNT(*) FROM lesson_access WHERE user_id = u.id) AS lessons_count, "
        "COUNT(s.id) AS submissions_count, "
        "SUM(CASE WHEN s.status = 'approved' THEN 1 ELSE 0 END) AS approved_count, "
        "SUM(CASE WHEN s.status = 'pending' THEN 1 ELSE 0 END) AS pending_count, "
        "SUM(CASE WHEN s.status = 'revise' THEN 1 ELSE 0 END) AS revise_count, "
        "AVG(s.score) AS avg_score "
        "FROM users u "
        "LEFT JOIN submissions s ON s.user_id = u.id "
        "WHERE u.role = 'student' "
        "GROUP BY u.id "
        "ORDER BY u.full_name"
    ).fetchall()
    return render_template("admin_students.html", students=rows)


@admin_bp.route("/statistics")
@admin_required
def statistics():
    db = get_db()

    totals = db.execute(
        "SELECT "
        "(SELECT COUNT(*) FROM lessons) AS lessons_count, "
        "(SELECT COUNT(*) FROM users WHERE role = 'student') AS students_count, "
        "(SELECT COUNT(*) FROM submissions) AS submissions_count, "
        "(SELECT AVG(score) FROM submissions WHERE score IS NOT NULL) AS avg_score"
    ).fetchone()

    status_counts = db.execute(
        "SELECT "
        "SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved, "
        "SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending, "
        "SUM(CASE WHEN status = 'revise' THEN 1 ELSE 0 END) AS revise "
        "FROM submissions"
    ).fetchone()

    lesson_scores = db.execute(
        "SELECT l.title AS label, ROUND(AVG(s.score), 1) AS value "
        "FROM lessons l "
        "LEFT JOIN submissions s ON s.lesson_id = l.id AND s.score IS NOT NULL "
        "GROUP BY l.id "
        "HAVING value IS NOT NULL "
        "ORDER BY l.created_at"
    ).fetchall()

    return render_template(
        "admin_statistics.html",
        totals=totals,
        status_counts=status_counts,
        lesson_scores=lesson_scores,
    )


# ---------- Пользователи ----------

@admin_bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    db = get_db()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip()
        role = request.form.get("role", "student")
        password = request.form.get("password", "").strip() or secrets.token_urlsafe(6)

        if not full_name or not username:
            flash("Заполните имя и логин.", "error")
        elif role not in ("admin", "student"):
            flash("Некорректная роль.", "error")
        else:
            existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                flash("Такой логин уже занят.", "error")
            else:
                db.execute(
                    "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, ?)",
                    (username, generate_password_hash(password), full_name, role),
                )
                db.commit()
                flash(f"Пользователь создан. Логин: {username} · Пароль: {password}", "success")
        return redirect(url_for("admin.users"))

    all_users = db.execute("SELECT * FROM users ORDER BY role DESC, full_name ASC").fetchall()
    return render_template("admin_users.html", users=all_users)


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def reset_password(user_id):
    db = get_db()
    user = db.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if user is None:
        flash("Пользователь не найден.", "error")
        return redirect(url_for("admin.users"))

    new_password = secrets.token_urlsafe(6)
    db.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(new_password), user_id))
    db.commit()
    flash(f"Новый пароль для {user['username']}: {new_password}", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def delete_user(user_id):
    db = get_db()
    if user_id == g.user["id"]:
        flash("Нельзя удалить свой собственный аккаунт.", "error")
        return redirect(url_for("admin.users"))
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()
    flash("Пользователь удалён.", "success")
    return redirect(url_for("admin.users"))


# ---------- Уроки ----------

@admin_bp.route("/lessons/new", methods=["GET", "POST"])
@admin_required
def new_lesson():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        due_date = request.form.get("due_date", "").strip() or None

        if not title:
            flash("Укажите название урока.", "error")
            return render_template("admin_lesson_new.html")

        db = get_db()
        cur = db.execute(
            "INSERT INTO lessons (title, description, due_date, created_by) VALUES (?, ?, ?, ?)",
            (title, description, due_date, g.user["id"]),
        )
        db.commit()
        flash("Урок создан. Теперь добавьте файлы и откройте доступ ученикам.", "success")
        return redirect(url_for("admin.lesson_detail", lesson_id=cur.lastrowid))

    return render_template("admin_lesson_new.html")


@admin_bp.route("/lessons/<int:lesson_id>")
@admin_required
def lesson_detail(lesson_id):
    db = get_db()
    lesson = db.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    if lesson is None:
        flash("Урок не найден.", "error")
        return redirect(url_for("admin.dashboard"))

    theory_files = db.execute(
        "SELECT * FROM lesson_files WHERE lesson_id = ? AND file_type = 'theory' ORDER BY uploaded_at",
        (lesson_id,),
    ).fetchall()
    homework_files = db.execute(
        "SELECT * FROM lesson_files WHERE lesson_id = ? AND file_type = 'homework' ORDER BY uploaded_at",
        (lesson_id,),
    ).fetchall()

    all_students = db.execute("SELECT * FROM users WHERE role = 'student' ORDER BY full_name").fetchall()
    granted_ids = {
        row["user_id"]
        for row in db.execute("SELECT user_id FROM lesson_access WHERE lesson_id = ?", (lesson_id,)).fetchall()
    }

    submissions = db.execute(
        "SELECT s.*, u.full_name FROM submissions s "
        "JOIN users u ON u.id = s.user_id "
        "WHERE s.lesson_id = ? ORDER BY s.submitted_at DESC",
        (lesson_id,),
    ).fetchall()

    return render_template(
        "admin_lesson_detail.html",
        lesson=lesson,
        theory_files=theory_files,
        homework_files=homework_files,
        all_students=all_students,
        granted_ids=granted_ids,
        submissions=submissions,
    )


@admin_bp.route("/lessons/<int:lesson_id>/edit", methods=["POST"])
@admin_required
def edit_lesson(lesson_id):
    title = request.form.get("title", "").strip()
    description = request.form.get("description", "").strip()
    due_date = request.form.get("due_date", "").strip() or None
    db = get_db()
    if not title:
        flash("Название не может быть пустым.", "error")
    else:
        db.execute(
            "UPDATE lessons SET title = ?, description = ?, due_date = ? WHERE id = ?",
            (title, description, due_date, lesson_id),
        )
        db.commit()
        flash("Урок обновлён.", "success")
    return redirect(url_for("admin.lesson_detail", lesson_id=lesson_id))


@admin_bp.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
@admin_required
def delete_lesson(lesson_id):
    db = get_db()
    db.execute("DELETE FROM lessons WHERE id = ?", (lesson_id,))
    db.commit()
    flash("Урок удалён.", "success")
    return redirect(url_for("admin.dashboard"))


@admin_bp.route("/lessons/<int:lesson_id>/files", methods=["POST"])
@admin_required
def upload_lesson_file(lesson_id):
    db = get_db()
    lesson = db.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    if lesson is None:
        flash("Урок не найден.", "error")
        return redirect(url_for("admin.dashboard"))

    file_type = request.form.get("file_type")
    uploaded = request.files.get("file")

    if file_type not in ("theory", "homework") or not uploaded or uploaded.filename == "":
        flash("Выберите файл и тип.", "error")
        return redirect(url_for("admin.lesson_detail", lesson_id=lesson_id))

    folder = os.path.join(current_app.config["UPLOAD_LESSONS"], str(lesson_id))
    original_name, stored_name = save_file(uploaded, folder)

    db.execute(
        "INSERT INTO lesson_files (lesson_id, file_type, original_name, stored_name) VALUES (?, ?, ?, ?)",
        (lesson_id, file_type, original_name, stored_name),
    )
    db.commit()
    flash("Файл добавлен к уроку.", "success")
    return redirect(url_for("admin.lesson_detail", lesson_id=lesson_id))


@admin_bp.route("/lessons/<int:lesson_id>/files/<int:file_id>/delete", methods=["POST"])
@admin_required
def delete_lesson_file(lesson_id, file_id):
    db = get_db()
    f = db.execute(
        "SELECT * FROM lesson_files WHERE id = ? AND lesson_id = ?", (file_id, lesson_id)
    ).fetchone()
    if f:
        path = os.path.join(current_app.config["UPLOAD_LESSONS"], str(lesson_id), f["stored_name"])
        if os.path.exists(path):
            os.remove(path)
        db.execute("DELETE FROM lesson_files WHERE id = ?", (file_id,))
        db.commit()
        flash("Файл удалён.", "success")
    return redirect(url_for("admin.lesson_detail", lesson_id=lesson_id))


@admin_bp.route("/lessons/<int:lesson_id>/access", methods=["POST"])
@admin_required
def update_access(lesson_id):
    db = get_db()
    selected_ids = set(int(x) for x in request.form.getlist("student_ids"))

    current_ids = {
        row["user_id"]
        for row in db.execute("SELECT user_id FROM lesson_access WHERE lesson_id = ?", (lesson_id,)).fetchall()
    }

    to_add = selected_ids - current_ids
    to_remove = current_ids - selected_ids

    for uid in to_add:
        db.execute("INSERT INTO lesson_access (lesson_id, user_id) VALUES (?, ?)", (lesson_id, uid))
    for uid in to_remove:
        db.execute("DELETE FROM lesson_access WHERE lesson_id = ? AND user_id = ?", (lesson_id, uid))
    db.commit()

    flash("Доступ к уроку обновлён.", "success")
    return redirect(url_for("admin.lesson_detail", lesson_id=lesson_id))


@admin_bp.route("/lessons/<int:lesson_id>/submissions/<int:submission_id>/review", methods=["POST"])
@admin_required
def review_submission(lesson_id, submission_id):
    db = get_db()
    status = request.form.get("status")
    feedback = request.form.get("feedback", "").strip() or None
    score_raw = request.form.get("score", "").strip()

    if status not in ("pending", "approved", "revise"):
        flash("Некорректный статус проверки.", "error")
        return redirect(url_for("admin.lesson_detail", lesson_id=lesson_id))

    score = None
    if score_raw:
        try:
            score = int(score_raw)
        except ValueError:
            score = None
        if score is None or not (0 <= score <= 10):
            flash("Балл должен быть числом от 0 до 10.", "error")
            return redirect(url_for("admin.lesson_detail", lesson_id=lesson_id))

    db.execute(
        "UPDATE submissions SET status = ?, feedback = ?, score = ? WHERE id = ? AND lesson_id = ?",
        (status, feedback, score, submission_id, lesson_id),
    )
    db.commit()
    flash("Проверка сохранена.", "success")
    return redirect(url_for("admin.lesson_detail", lesson_id=lesson_id))


@admin_bp.route("/download/lesson/<int:lesson_id>/<path:stored_name>")
@admin_required
def download_lesson_file(lesson_id, stored_name):
    db = get_db()
    f = db.execute(
        "SELECT * FROM lesson_files WHERE lesson_id = ? AND stored_name = ?", (lesson_id, stored_name)
    ).fetchone()
    folder = os.path.join(current_app.config["UPLOAD_LESSONS"], str(lesson_id))
    if f:
        return send_from_directory(folder, stored_name, as_attachment=True, download_name=f["original_name"])
    return send_from_directory(folder, stored_name)


@admin_bp.route("/download/submission/<int:lesson_id>/<int:user_id>/<path:stored_name>")
@admin_required
def download_submission_file(lesson_id, user_id, stored_name):
    db = get_db()
    s = db.execute(
        "SELECT * FROM submissions WHERE lesson_id = ? AND user_id = ? AND stored_name = ?",
        (lesson_id, user_id, stored_name),
    ).fetchone()
    folder = os.path.join(current_app.config["UPLOAD_SUBMISSIONS"], str(lesson_id), str(user_id))
    if s:
        return send_from_directory(folder, stored_name, as_attachment=True, download_name=s["original_name"])
    return send_from_directory(folder, stored_name)
