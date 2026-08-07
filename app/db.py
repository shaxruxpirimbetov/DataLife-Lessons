import os
import sqlite3

from flask import current_app, g
from werkzeug.security import generate_password_hash

DEFAULT_ADMIN_PASSWORD = "shaxcoder12"

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'student')),
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS lessons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    due_date TEXT,
    created_by INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (created_by) REFERENCES users (id)
);

CREATE TABLE IF NOT EXISTS lesson_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id INTEGER NOT NULL,
    file_type TEXT NOT NULL CHECK(file_type IN ('theory', 'homework')),
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (lesson_id) REFERENCES lessons (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS lesson_access (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    granted_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(lesson_id, user_id),
    FOREIGN KEY (lesson_id) REFERENCES lessons (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lesson_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    original_name TEXT NOT NULL,
    stored_name TEXT NOT NULL,
    comment TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'approved', 'revise')),
    feedback TEXT,
    score INTEGER CHECK(score IS NULL OR (score BETWEEN 0 AND 10)),
    submitted_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (lesson_id) REFERENCES lessons (id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
);
"""


def _ensure_column(conn, table, column, ddl):
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"])
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db_if_needed(app):
    """Создаёт базу и таблицы при первом запуске, плюс администратора."""
    db_path = app.config["DATABASE"]
    is_new = not os.path.exists(db_path)

    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    _ensure_column(conn, "lessons", "due_date", "due_date TEXT")
    _ensure_column(conn, "submissions", "status", "status TEXT NOT NULL DEFAULT 'pending'")
    _ensure_column(conn, "submissions", "feedback", "feedback TEXT")
    _ensure_column(conn, "submissions", "score", "score INTEGER")
    conn.commit()

    if is_new:
        cur = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
        if cur.fetchone()[0] == 0:
            conn.execute(
                "INSERT INTO users (username, password_hash, full_name, role) VALUES (?, ?, ?, 'admin')",
                ("admin", generate_password_hash(DEFAULT_ADMIN_PASSWORD), "Администратор"),
            )
            conn.commit()
            print("=" * 60)
            print(" Создан администратор по умолчанию:")
            print("   логин:   admin")
            print(f"   пароль:  {DEFAULT_ADMIN_PASSWORD}")
            print(" Рекомендуем сменить пароль admin после первого входа.")
            print("=" * 60)

    conn.close()
