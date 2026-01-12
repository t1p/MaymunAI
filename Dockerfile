# Используем официальный образ Python 3.11 на базе Debian
FROM python:3.11-slim

# Устанавливаем системные зависимости для PostgreSQL и других пакетов
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя и группу для приложения
RUN groupadd -r maymunai && useradd -r -g maymunai maymunai

# Создаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения
COPY . .

# Меняем владельца файлов на созданного пользователя
RUN chown -R maymunai:maymunai /app

# Переключаемся на не-root пользователя
USER maymunai

# Определяем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Команда запуска приложения
CMD ["python", "main.py"]