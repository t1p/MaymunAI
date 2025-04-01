[2025-04-02 01:11:30] - Обновлена документация схемы PostgreSQL. Добавлены новые таблицы (embeddings, query_embeddings, user_groups), уточнены связи и ограничения.
# Active Context

This file tracks the project's current status, including recent changes, current goals, and open questions.
2025-03-30 00:02:06 - Log of updates made.

*

## Current Focus

* Ознакомление с проектом MaymunAI и его архитектурой
* Понимание основных компонентов системы и их взаимодействия
* Выявление возможных улучшений и оптимизаций

## Recent Changes

* Создание Memory Bank для отслеживания проекта
* Анализ исходного кода и структуры проекта

## Open Questions/Issues

* Как настроена аутентификация для доступа к базе данных PostgreSQL?
* Существует ли файл settings.py с реальными настройками (есть только settings.example.py)?
* Как обрабатываются длинные тексты, превышающие лимиты токенов для моделей OpenAI?
* Как организовано тестирование системы?
* Какие метрики используются для оценки качества ответов?
* Как обрабатываются ошибки API OpenAI и сбои в работе базы данных?