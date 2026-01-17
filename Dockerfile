# Используем официальный образ Python 3.11 на базе Debian
FROM python:3.11-slim

# Устанавливаем системные зависимости для PostgreSQL и других пакетов
RUN apt-get update && apt-get install -y \
    postgresql-client \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Устанавливаем gosu для переключения пользователей
RUN wget -O /usr/local/bin/gosu "https://github.com/tianon/gosu/releases/download/1.17/gosu-amd64" \
    && chmod +x /usr/local/bin/gosu

# Создаем пользователя и группу для приложения
RUN groupadd -r maymunai && useradd -r -g maymunai maymunai

# Создаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем исходный код приложения
COPY . .

# Копируем entrypoint скрипт
COPY entrypoint.sh .

# Делаем entrypoint исполняемым
RUN chmod +x entrypoint.sh

# Устанавливаем entrypoint
ENTRYPOINT ["./entrypoint.sh"]

# Определяем переменные окружения
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# Команда запуска приложения
CMD ["python", "main.py"]