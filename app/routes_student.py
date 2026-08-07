import os

from flask import (
    Blueprint, abort, current_app, flash, g, redirect, render_template,
    request, send_from_directory, url_for
)

from app.db import get_db
from app.utils import has_lesson_access, login_required, save_file

student_bp = Blueprint("student", __name__)


@student_bp.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    if g.user["role"] == "admin":
        return redirect(url_for("admin.dashboard"))

    lessons = db.execute(
        "SELECT l.* FROM lessons l "
        "JOIN lesson_access a ON a.lesson_id = l.id "
        "WHERE a.user_id = ? ORDER BY l.created_at DESC",
        (g.user["id"],),
    ).fetchall()
    return render_template("student_dashboard.html", lessons=lessons)


@student_bp.route("/lessons/<int:lesson_id>", methods=["GET", "POST"])
@login_required
def lesson_view(lesson_id):
    db = get_db()
    lesson = db.execute("SELECT * FROM lessons WHERE id = ?", (lesson_id,)).fetchone()
    if lesson is None:
        abort(404)

    if not has_lesson_access(db, lesson_id, g.user):
        flash("У вас нет доступа к этому уроку.", "error")
        return redirect(url_for("student.dashboard"))

    if request.method == "POST":
        comment = request.form.get("comment", "").strip()
        uploaded = request.files.get("file")

        if not uploaded or uploaded.filename == "":
            flash("Прикрепите файл с домашним заданием.", "error")
        else:
            folder = os.path.join(
                current_app.config["UPLOAD_SUBMISSIONS"], str(lesson_id), str(g.user["id"])
            )
            original_name, stored_name = save_file(uploaded, folder)
            db.execute(
                "INSERT INTO submissions (lesson_id, user_id, original_name, stored_name, comment) "
                "VALUES (?, ?, ?, ?, ?)",
                (lesson_id, g.user["id"], original_name, stored_name, comment),
            )
            db.commit()
            flash("Домашнее задание отправлено.", "success")
        return redirect(url_for("student.lesson_view", lesson_id=lesson_id))

    theory_files = db.execute(
        "SELECT * FROM lesson_files WHERE lesson_id = ? AND file_type = 'theory' ORDER BY uploaded_at",
        (lesson_id,),
    ).fetchall()
    homework_files = db.execute(
        "SELECT * FROM lesson_files WHERE lesson_id = ? AND file_type = 'homework' ORDER BY uploaded_at",
        (lesson_id,),
    ).fetchall()
    my_submissions = db.execute(
        "SELECT * FROM submissions WHERE lesson_id = ? AND user_id = ? ORDER BY submitted_at DESC",
        (lesson_id, g.user["id"]),
    ).fetchall()

    return render_template(
        "student_lesson.html",
        lesson=lesson,
        theory_files=theory_files,
        homework_files=homework_files,
        my_submissions=my_submissions,
    )


@student_bp.route("/dashboard/statistics")
@login_required
def statistics():
    db = get_db()
    if g.user["role"] == "admin":
        return redirect(url_for("admin.statistics"))

    counts = db.execute(
        "SELECT COUNT(*) AS total, "
        "SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) AS approved, "
        "SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending, "
        "SUM(CASE WHEN status = 'revise' THEN 1 ELSE 0 END) AS revise, "
        "AVG(score) AS avg_score "
        "FROM submissions WHERE user_id = ?",
        (g.user["id"],),
    ).fetchone()

    lessons_count = db.execute(
        "SELECT COUNT(*) FROM lesson_access WHERE user_id = ?", (g.user["id"],)
    ).fetchone()[0]

    lesson_scores = db.execute(
        "SELECT l.title AS label, MAX(s.score) AS value "
        "FROM lessons l "
        "JOIN lesson_access a ON a.lesson_id = l.id AND a.user_id = ? "
        "LEFT JOIN submissions s ON s.lesson_id = l.id AND s.user_id = a.user_id "
        "WHERE a.user_id = ? "
        "GROUP BY l.id "
        "HAVING value IS NOT NULL "
        "ORDER BY l.created_at",
        (g.user["id"], g.user["id"]),
    ).fetchall()

    return render_template(
        "student_statistics.html",
        counts=counts,
        lessons_count=lessons_count,
        lesson_scores=lesson_scores,
    )


@student_bp.route("/lessons/<int:lesson_id>/download/<path:stored_name>")
@login_required
def download_file(lesson_id, stored_name):
    db = get_db()
    if not has_lesson_access(db, lesson_id, g.user):
        abort(403)

    f = db.execute(
        "SELECT * FROM lesson_files WHERE lesson_id = ? AND stored_name = ?", (lesson_id, stored_name)
    ).fetchone()
    if f is None:
        abort(404)

    folder = os.path.join(current_app.config["UPLOAD_LESSONS"], str(lesson_id))
    return send_from_directory(folder, stored_name, as_attachment=True, download_name=f["original_name"])
