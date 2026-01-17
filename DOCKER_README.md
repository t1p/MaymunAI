# Docker Setup для MaymunAI

Этот документ описывает, как запустить MaymunAI с использованием Docker для обеспечения кроссплатформенности.

## Преимущества Docker

Docker решает проблемы ОС-специфичности следующим образом:

1. **Унифицированная среда**: Все контейнеры работают на Linux, независимо от хост-ОС (Windows/Mac/Linux)
2. **Изоляция зависимостей**: Python, PostgreSQL и системные библиотеки изолированы в контейнерах
3. **Консистентность**: Тот же setup работает одинаково в разработке и продакшене
4. **Простота развертывания**: Нет необходимости устанавливать PostgreSQL или Python локально
5. **Версионирование**: Docker образы можно версионировать и повторно использовать

## Быстрый старт

### Предварительные требования

- Docker и Docker Compose установлены на системе
- OpenAI API ключ

### Шаги запуска

1. **Клонируйте репозиторий:**
   ```bash
   git clone <repository-url>
   cd MaymunAI
   ```

2. **Создайте .env файл:**
   ```bash
   cp .env.example .env
   ```
   Отредактируйте `.env` файл и добавьте ваш OpenAI API ключ.

3. **Запустите сервисы:**
   ```bash
   docker-compose up --build
   ```

4. **Инициализация базы данных (опционально):**
   Если у вас есть бэкап базы данных `maymunai_backup.dump`, он автоматически восстановится при первом запуске.

## Внешние ретриверы (опционально)

Запуск FastGPT:

```bash
docker compose -f docker/fastgpt-compose.yml up -d
```

Запуск RAGFlow:

```bash
docker compose -f docker/ragflow-compose.yml up -d
```

## Структура сервисов

### PostgreSQL (db)
- **Образ**: postgres:15
- **Порт**: 5432 (доступен на localhost:5432)
- **База данных**: maymunai
- **Пользователь**: maymun
- **Volume**: `postgres_data` для персистентности данных

### Приложение (app)
- **Образ**: Собственный (собирается из Dockerfile)
- **Зависимости**: Python 3.11, PostgreSQL client
- **Volume**: Текущая директория монтируется в /app для разработки
- **Пользователь**: maymunai (не-root)

## Команды управления

```bash
# Запуск в фоне
docker-compose up -d

# Просмотр логов
docker-compose logs -f app

# Остановка сервисов
docker-compose down

# Пересборка и запуск
docker-compose up --build --force-recreate

# Очистка volumes (осторожно - удалит данные!)
docker-compose down -v
```

## Переменные окружения

| Переменная | Описание | Значение по умолчанию |
|------------|----------|----------------------|
| OPENAI_API_KEY | API ключ OpenAI | (обязательно) |
| DB_HOST | Хост базы данных | db |
| DB_PORT | Порт базы данных | 5432 |
| DB_NAME | Имя базы данных | maymunai |
| DB_USER | Пользователь БД | maymun |
| DB_PASSWORD | Пароль БД | ydYy9^&.q4#P9 |

## Разработка

Для разработки код монтируется как volume, поэтому изменения применяются сразу. Для применения изменений зависимостей:

```bash
docker-compose build app
docker-compose up app
```

## Troubleshooting

### Проблемы с подключением к БД
Убедитесь, что сервис db здоров:
```bash
docker-compose ps
docker-compose logs db
```

### Ошибки сборки
Очистите кэш Docker:
```bash
docker system prune -a
```

### Проблемы с памятью на Windows
Увеличьте память Docker Desktop до 4GB+.

## Миграция с локальной установки

Если у вас была локальная установка PostgreSQL:

1. Создайте бэкап вашей базы данных
2. Скопируйте `maymunai_backup.dump` в корень проекта
3. Docker автоматически восстановит данные при первом запуске

## Производственное использование

Для продакшена:

1. Используйте production-ready образы
2. Настройте secrets management вместо .env
3. Добавьте healthchecks и мониторинг
4. Настройте backup стратегию для volumes
