"""
Data Life Learning Centre — платформа публикации уроков
Запуск: python run.py
"""
import os
import secrets

from app import create_app
from app.db import init_db_if_needed

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        init_db_if_needed(app)

    port = int(os.environ.get("PORT", 5000))
    print("=" * 60)
    print(" Data Life Learning Centre")
    print(f" Сайт запущен: http://127.0.0.1:{port}")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=False)
