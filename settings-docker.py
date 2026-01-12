# Настройки для Docker развертывания MaymunAI
import os

# База данных
DB_CONFIG = {
    "dbname": os.getenv("DB_NAME", "maymunai"),
    "user": os.getenv("DB_USER", "maymun"),
    "password": os.getenv("DB_PASSWORD", "ydYy9^&.q4#P9"),
    "host": os.getenv("DB_HOST", "db"),
    "port": os.getenv("DB_PORT", "5432")
}

# API ключи
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# Проверка обязательных переменных
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")

# Проверка подключения к БД
try:
    import psycopg2
    conn = psycopg2.connect(**DB_CONFIG)
    conn.close()
    print("Database connection successful")
except Exception as e:
    print(f"Database connection failed: {e}")
    print("Please ensure PostgreSQL container is running and accessible")