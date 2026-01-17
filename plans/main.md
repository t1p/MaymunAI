Принял. Обновляю ТЗ для прототипа MaymunAI с учётом новых требований-переключателей.

# ТЗ: MaymunAI (MVP) — RAG, Postgres/Neurokod, MCP, внешние ретриверы

## 0) Контекст и цели

* Ассистент: **MaymunAI**.
* Хранилище знаний (MVP): **Postgres** (картотека Нейрокод на X200).
* RAG обязателен: старт с локального (pg/pgvector), затем опции внешних движков (**FastGPT**, **RAGFlow**) через Docker/NPX.
* Поддержка **MCP**: как клиент к **Enhanced Postgres MCP Server** и режим работы **самого** MaymunAI как MCP-сервера. Основа MCP: открытый стандарт, хост/клиент/сервер, stdio/HTTP/SSE. ([modelcontextprotocol.io][1])
* Enhanced Postgres MCP Server даёт чтение/запись, схему, DDL/CRUD. ([GitHub][2])
* FastGPT / RAGFlow — внешние RAG-провайдеры с готовыми пайплайнами. ([GitHub][3])

---

## 1) Архитектура и режимы

### 1.1 Режимы подключения к Нейрокоду (переключаемые)

* **A. native_pg**: прямое подключение к Postgres (psycopg2), локальный RAG (pgvector).
* **B. mcp_pg**: доступ к тем же данным через **enhanced-postgres-mcp-server** (клиент MCP). ([GitHub][2])

### 1.2 Режимы ретривера (переключаемые)

* **RAG_NATIVE**: локальная индексация/поиск (pgvector/FAISS в fallback).
* **RAG_FASTGPT**: делегирование в FastGPT (REST API/SDK, деплой via Docker). ([GitHub][3])
* **RAG_RAGFLOW**: делегирование в RAGFlow (REST API, деплой via Docker). ([ragflow.io][4])

### 1.3 Режимы запуска MaymunAI

* **client_app**: обычный CLI/сервис ассистента.
* **mcp_server**: MaymunAI поднимает **MCP-сервер** со своими tools (retrieval, notes, tasks, prompts). ([modelcontextprotocol.io][1])

---

## 2) Конфиги и переключатели

### 2.1 Файл `config.yaml`

```yaml
mode:
  db_access: native_pg   # [native_pg|mcp_pg]
  retriever: RAG_NATIVE  # [RAG_NATIVE|RAG_FASTGPT|RAG_RAGFLOW]
  run_as: client_app     # [client_app|mcp_server]

postgres:
  host: localhost
  port: 5432
  dbname: neurokod
  user: postgres
  password: ${PG_PASSWORD}
  schema: public
  use_pgvector: true

mcp:
  pg_server:
    command: "enhanced-postgres-mcp-server"
    transport: "stdio"   # or http
    args:
      - "--dsn=${PG_DSN}"

fastgpt:
  base_url: "http://localhost:3000"
  api_key: "${FASTGPT_API_KEY}"
  dataset_id: "${FASTGPT_DATASET_ID}"

ragflow:
  base_url: "http://localhost:9380"
  api_key: "${RAGFLOW_API_KEY}"
  index:   "default"

prompts:
  pack: "default"        # имя набора системных промптов
  preload_paths:
    - "./prompts/system"
    - "./prompts/modes"

logging:
  level: INFO            # [CRITICAL|ERROR|WARN|INFO|DEBUG|TRACE]
  fmt: json              # [json|text]
  file: "./logs/maymunai.log"
  module_levels:
    "db": INFO
    "rag": DEBUG
    "mcp": DEBUG
    "retrievers.fastgpt": DEBUG
    "retrievers.ragflow": DEBUG
  trace_id: true
```

### 2.2 `.env` пример

```
OPENAI_API_KEY=...
PG_PASSWORD=...
PG_DSN=postgresql://postgres:...@localhost:5432/neurokod
FASTGPT_API_KEY=...
FASTGPT_DATASET_ID=...
RAGFLOW_API_KEY=...
```

---

## 3) Структура проекта (обновлённая)

```
maymunai/
  main.py
  config.yaml
  .env
  core/
    settings.py
    logging_setup.py
    prompts_loader.py
    mcp_server.py
  db/
    pg_native.py
    pg_mcp_client.py
    schema_introspect.py
  rag/
    embed_openai.py
    index_pgvector.py
    retriever_native.py
    retriever_fastgpt.py
    retriever_ragflow.py
    compose_context.py
  modes/
    runner_client.py
    runner_mcp_server.py
  prompts/
    system/*.md      # системные промпты режимов
    modes/*.md       # профильные промпты (управление задачами, мозг.штурм и т.п.)
  cli/
    build_index.py
    ingest_docs.py
    test_query.py
  logs/
  docker/
    fastgpt-compose.yml
    ragflow-compose.yml
```

---

## 4) Модули и обязанности

### 4.1 Доступ к БД (Нейрокод)

* `db/pg_native.py`

  * `get_conn()`, `list_tables()`, `fetch_documents()`, `upsert_chunk_embeddings(...)`.
* `db/pg_mcp_client.py`

  * Клиент MCP к enhanced-postgres-mcp-server (exec tool: `query`, `ddl`, `schema`).
  * Интерфейсы совпадают по сигнатурам с `pg_native.py`, чтобы легко переключать backend. ([GitHub][2])
* `db/schema_introspect.py`

  * Унификация описания схемы (таблицы/поля/типы), экспоз в JSON для промптов.

### 4.2 RAG

* `rag/embed_openai.py`: эмбеддинги (OpenAI).
* `rag/index_pgvector.py`: создание/миграция таблиц (`documents`, `chunks`, `embeddings`), поиск KNN.
* `rag/retriever_native.py`: конвейер `query->embed->KNN->chunks`.
* `rag/retriever_fastgpt.py`: REST-клиент к FastGPT: `upload docs`, `query`, `top_k`. ([GitHub][3])
* `rag/retriever_ragflow.py`: REST-клиент к RAGFlow: `datasets`, `ingest`, `query`, `citations`. ([ragflow.io][4])
* `rag/compose_context.py`: сборка контекста (с метаданными, цитатами) + анти-инъекционные guardrails.

### 4.3 MCP

* **Клиент**: `db/pg_mcp_client.py` (см. выше).
* **Сервер (режим mcp_server)**: `core/mcp_server.py`

  * Экспортирует tools:

    * `tool.retrieval(query, top_k, retriever_mode)`
    * `tool.note.create(text, tags)`
    * `tool.task.create(title, payload)`
    * `tool.info.schema()` — описание БД/индекса.
  * Транспорт stdio по умолчанию; совместим со спецификацией MCP. ([modelcontextprotocol.io][1])

### 4.4 Промпты

* `core/prompts_loader.py`

  * Предзагрузка «пакетов» системных промптов из `prompts/system` и профильных из `prompts/modes`.
  * Экспорт в рантайм для разных режимов (`assistant=tasks`, `assistant=brainstorm`, `assistant=knowledge`).
  * Включает JSON-описание БД (из `schema_introspect`) и **правила извлечения/манипуляции данными** (RAG-policy).

### 4.5 Логи/диагностика

* `core/logging_setup.py`

  * Уровни: `CRITICAL/ERROR/WARN/INFO/DEBUG/TRACE`.
  * Форматы: `json|text`, ротация файлов.
  * `trace_id` в каждый лог-ивент.
  * **Эшелонирование**: глобальный уровень + `module_levels` из конфигура.
  * CLI-переключатели для временного повышения уровней отдельных модулей.

---

## 5) CLI-утилиты

1. `python -m cli.ingest_docs --source <path|sql> --chunk 1200 --overlap 200`

   * Ингест локальных файлов или выборки из БД в индекс (native_pg | mcp_pg).
2. `python -m cli.build_index --rebuild`

   * Создание/миграция таблиц (pgvector), пересчёт эмбеддингов.
3. `python -m cli.test_query --q "..." --top_k 5`

   * Проверка контура RAG (любой retriever по конфигу).

Флаги общие:

```
--config config.yaml
--set mode.db_access=mcp_pg
--set mode.retriever=RAG_FASTGPT
--set logging.level=DEBUG
--set logging.module_levels.rag=TRACE
```

---

## 6) Режимы запуска

### 6.1 Клиент

```
python -m modes.runner_client --config config.yaml
```

### 6.2 MCP-сервер

```
python -m modes.runner_mcp_server --config config.yaml
# stdio по умолчанию (интеграция с клиентами MCP)
```

---

## 7) Интеграция внешних ретриверов

### 7.1 FastGPT (Docker)

* Ссылки/описание проекта, поддержка RAG и визуальных пайплайнов. ([GitHub][3])
* `docker/fastgpt-compose.yml` (поднимает API/UI).
* `retriever_fastgpt.py`:

  * `upload(doc|chunk)`, `query(q, top_k)`; парсит ответы, возвращает цитаты/score.

### 7.2 RAGFlow (Docker)

* Открытый движок RAG с агентными возможностями; API для ingestion/query. ([ragflow.io][4])
* `docker/ragflow-compose.yml`.
* `retriever_ragflow.py`: аналогично FastGPT.

---

## 8) Безопасность/риски MCP (минимум в MVP)

* MCP даёт мощные интеграции; учитывать инъекции/идентичность/секреты (кратко зафиксировать в README: токены, JIT-доступ, минимизация привилегий). ([IT Pro][5])

---

## 9) Мини-план работ для кодера (по шагам)

1. **Конфигурация/логи**

   * Реализовать `settings.py` (pydantic/yaml), `logging_setup.py` (структурные логи, module_levels).

2. **DB-слой**

   * `pg_native.py` (psycopg2).
   * `pg_mcp_client.py` (вызовы tools enhanced-postgres MCP: schema, query, ddl). ([GitHub][2])
   * `schema_introspect.py` → JSON-сводка схемы.

3. **RAG-слой (native)**

   * `embed_openai.py` (OpenAI embeddings).
   * `index_pgvector.py` (создание таблиц, KNN).
   * `retriever_native.py` (end-to-end поиск).

4. **Внешние ретриверы**

   * `retriever_fastgpt.py` + docker-compose (поднять локально). ([GitHub][3])
   * `retriever_ragflow.py` + docker-compose. ([ragflow.io][4])

5. **Промпты**

   * `prompts_loader.py`: preload pack + включение описания БД и RAG-policy в system-prompt.

6. **MCP**

   * Клиент к pg-MCP (см. п.2).
   * `mcp_server.py` (tools: retrieval/note/task/info.schema).

7. **CLI**

   * `ingest_docs.py`, `build_index.py`, `test_query.py`.
   * `main.py` (интерактивный запрос→ответ).

8. **README**

   * Краткая инструкция по переключателям, env, запуску режимов, логированию.

---

## 10) Критерии приёмки (MVP)

* Переключение `db_access` = `native_pg` ↔ `mcp_pg` без изменения прикладного кода.
* Переключение `retriever` = `RAG_NATIVE` ↔ `RAG_FASTGPT` ↔ `RAG_RAGFLOW` одной строкой конфига.
* Запуск **mcp_server** и доступность tools (`retrieval`, `info.schema`).
* Предзагрузка промптов; в ответе модель использует RAG-контекст.
* Логи: JSON, trace_id, избирательно повышаем уровень для модуля (например, `retrievers.ragflow:TRACE`) без перезапуска.
* Утилиты `ingest_docs`, `build_index`, `test_query` работают на реальных данных Нейрокода.

---

## 11) Ссылки (для ориентира разработчику)

* Enhanced Postgres MCP Server (чтение/запись, схема): ([GitHub][2])
* MCP: обзор/сервер-концепции/спека: ([modelcontextprotocol.io][1])
* FastGPT (open-source RAG/воркфлоу): ([GitHub][3])
* RAGFlow (open-source RAG/агенты): ([ragflow.io][4])
* Безопасность MCP/адопшен: ([IT Pro][5])
