"""
Скрипт для заполнения БД тестовыми данными.
Запуск: python seed.py [--reset]

--reset  — удалить все данные (кроме админа) перед заполнением.
"""
import argparse
import random
import sys
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db, init_db_if_needed

STUDENTS = [
    ("ivanov", "Иван Иванов"),
    ("petrova", "Мария Петрова"),
    ("sidorov", "Алексей Сидоров"),
    ("kuznetsova", "Ольга Кузнецова"),
    ("smirnov", "Дмитрий Смирнов"),
    ("volkova", "Анна Волкова"),
    ("morozov", "Сергей Морозов"),
    ("fedorova", "Екатерина Фёдорова"),
]

LESSONS = [
    {
        "title": "Введение в Python",
        "description": "Основы синтаксиса, переменные, типы данных.",
        "due_offset": -5,
    },
    {
        "title": "Циклы и условия",
        "description": "Конструкции if/else, for, while на практике.",
        "due_offset": -1,
    },
    {
        "title": "Функции и модули",
        "description": "Как писать переиспользуемый код.",
        "due_offset": 2,
    },
    {
        "title": "Работа с файлами",
        "description": "Чтение и запись файлов, работа с CSV.",
        "due_offset": 7,
    },
]

DEFAULT_PASSWORD = "student123"

STATUSES = ["pending", "approved", "approved", "revise"]


def seed(reset: bool):
    app = create_app()
    with app.app_context():
        init_db_if_needed(app)
        db = get_db()

        if reset:
            db.execute("DELETE FROM submissions")
            db.execute("DELETE FROM lesson_access")
            db.execute("DELETE FROM lesson_files")
            db.execute("DELETE FROM lessons")
            db.execute("DELETE FROM users WHERE role = 'student'")
            db.commit()
            print("Старые тестовые данные удалены.")

        admin = db.execute("SELECT id FROM users WHERE role = 'admin' LIMIT 1").fetchone()
        if admin is None:
            print("Не найден администратор — что-то пошло не так с init_db_if_needed.")
            sys.exit(1)
        admin_id = admin["id"]

        # ---- Студенты ----
        student_ids = []
        for username, full_name in STUDENTS:
            existing = db.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
            if existing:
                student_ids.append(existing["id"])
                continue
            cur = db.execute(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, 'student')",
                (username, generate_password_hash(DEFAULT_PASSWORD), full_name),
            )
            student_ids.append(cur.lastrowid)
        db.commit()
        print(f"Студентов создано/найдено: {len(student_ids)} (пароль у всех: {DEFAULT_PASSWORD})")

        # ---- Уроки ----
        lesson_ids = []
        for lesson in LESSONS:
            due_date = (date.today() + timedelta(days=lesson["due_offset"])).isoformat()
            cur = db.execute(
                "INSERT INTO lessons (title, description, due_date, created_by) VALUES (?, ?, ?, ?)",
                (lesson["title"], lesson["description"], due_date, admin_id),
            )
            lesson_ids.append(cur.lastrowid)
        db.commit()
        print(f"Уроков создано: {len(lesson_ids)}")

        # ---- Доступ студентов к урокам ----
        for lesson_id in lesson_ids:
            for student_id in student_ids:
                # каждому студенту открываем доступ с вероятностью 80%
                if random.random() < 0.8:
                    db.execute(
                        "INSERT OR IGNORE INTO lesson_access (lesson_id, user_id) VALUES (?, ?)",
                        (lesson_id, student_id),
                    )
        db.commit()

        # ---- Сдачи домашних заданий ----
        submissions_created = 0
        for lesson_id in lesson_ids:
            granted = db.execute(
                "SELECT user_id FROM lesson_access WHERE lesson_id = ?", (lesson_id,)
            ).fetchall()
            for row in granted:
                if random.random() < 0.7:  # не все сдают
                    status = random.choice(STATUSES)
                    score = random.randint(5, 10) if status == "approved" else None
                    feedback = None
                    if status == "revise":
                        feedback = "Нужно доработать: проверь граничные случаи."
                    elif status == "approved":
                        feedback = "Отличная работа!"
                    db.execute(
                        "INSERT INTO submissions "
                        "(lesson_id, user_id, original_name, stored_name, comment, status, feedback, score) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            lesson_id,
                            row["user_id"],
                            "homework.txt",
                            f"seed_{lesson_id}_{row['user_id']}.txt",
                            "Тестовая сдача (сгенерировано seed-скриптом).",
                            status,
                            feedback,
                            score,
                        ),
                    )
                    submissions_created += 1
        db.commit()
        print(f"Сдач домашних заданий создано: {submissions_created}")

        print("=" * 60)
        print("Готово! Тестовые данные добавлены.")
        print(f"Логины студентов: {', '.join(u for u, _ in STUDENTS)}")
        print(f"Пароль для всех студентов: {DEFAULT_PASSWORD}")
        print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Заполнение БД тестовыми данными.")
    parser.add_argument("--reset", action="store_true", help="Удалить старые тестовые данные перед заполнением.")
    args = parser.parse_args()
    seed(args.reset)
