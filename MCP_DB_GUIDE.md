# Руководство по работе с БД через MCP

## Подключение к БД через MCP

Для подключения к базе данных через MCP необходимо:

1. Убедиться, что MCP сервер с поддержкой БД запущен
2. Использовать следующий формат подключения:

```python
from mcp import DatabaseConnector

# Подключение к PostgreSQL
conn = DatabaseConnector(
    server_name="db_server",
    db_type="postgresql",
    db_name="my_database",
    username="user",
    password="pass"
)
```

## Формат SQL-запросов

Рекомендуемый формат SQL-запросов:

- Используйте параметризованные запросы для безопасности
- Разделяйте сложные запросы на несколько строк
- Комментируйте неочевидные части запроса

```sql
-- Пример параметризованного запроса
SELECT * FROM users 
WHERE created_at > %(date_param)s
  AND status = %(status_param)s
```

## Примеры запросов

### SELECT

```python
# Получение данных
query = """
SELECT id, name, email 
FROM users
WHERE active = TRUE
LIMIT 100
"""

results = conn.execute_query(query)
```

### INSERT

```python
# Вставка данных
insert_query = """
INSERT INTO users (name, email, created_at)
VALUES (%(name)s, %(email)s, NOW())
"""

data = {'name': 'Иван', 'email': 'ivan@example.com'}
conn.execute_query(insert_query, data)
```

### UPDATE

```python
# Обновление данных
update_query = """
UPDATE users
SET last_login = NOW()
WHERE id = %(user_id)s
"""

conn.execute_query(update_query, {'user_id': 42})
```

## Обработка результатов

Результаты запросов возвращаются в виде списка словарей:

```python
for row in results:
    print(f"ID: {row['id']}, Name: {row['name']}")
    
# Или преобразование в DataFrame
import pandas as pd
df = pd.DataFrame(results)
```

## Частые ошибки и решения

1. **Ошибка подключения**
   - Проверьте параметры подключения
   - Убедитесь, что сервер БД доступен

2. **Ошибка выполнения запроса**
   - Проверьте синтаксис SQL
   - Убедитесь, что все параметры переданы

3. **Проблемы с кодировкой**
   - Укажите кодировку при подключении: `client_encoding='UTF8'`

4. **Медленные запросы**
   - Добавьте индексы на часто используемые поля
   - Оптимизируйте сложные запросы