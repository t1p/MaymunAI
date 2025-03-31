# Product Context

This file provides a high-level overview of the project and the expected product that will be created. Initially it is based upon projectBrief.md (if provided) and all other available project-related information in the working directory. This file is intended to be updated as the project evolves, and should be used to inform all other modes of the project's goals and context.
2025-03-30 00:01:44 - Log of updates made will be appended as footnotes to the end of this file.

*

## Project Goal

* MaymunAI - это персональный ассистент, который использует технологию RAG (Retrieval-Augmented Generation) для ответов на вопросы пользователя на основе базы знаний, хранящейся в PostgreSQL.

## Key Features

* Семантический поиск с использованием эмбеддингов OpenAI (text-embedding-3-large)
* Генерация ответов с использованием GPT-4 Turbo
* Поиск по ключевым словам и автоматическая генерация ключевых слов для запросов
* Иерархическая структура данных с родительскими и дочерними элементами
* Кэширование эмбеддингов для оптимизации производительности
* Интерактивный режим отладки с возможностью настройки параметров
* Анализ базы данных и миграция схемы

## Overall Architecture

* **База данных**: PostgreSQL для хранения элементов (items) и их эмбеддингов
* **Эмбеддинги**: Использование OpenAI API для создания векторных представлений текста
* **Поиск**: Семантический поиск с использованием косинусного сходства между эмбеддингами
* **Генерация**: Использование GPT-4 Turbo для генерации ответов на основе найденного контекста

## Launch Parameters

* `-d`, `--debug` - Включить режим отладки
* `-dd`, `--debug_extended` - Расширенный режим отладки
* `-i`, `--info` - Просмотр информации о блоках
* `-n NAME`, `--name NAME` - Поиск блока по названию
* `-b ID`, `--block-id ID` - Просмотр информации по ID блока
* `-r MARKERS`, `--roots MARKERS` - Корневые маркеры для поиска
* `-v`, `--view-tree` - Показать дерево элементов
* `-s TEXT`, `--search TEXT` - Поиск по тексту в базе данных
* `-c N`, `--context N` - Размер контекста при поиске (по умолчанию: 2)
* `--clear-cache` - Очистить кэш эмбеддингов
* `--preload` - Предзагрузить эмбеддинги частых запросов
* `--migrate` - Обновить структуру базы данных
* `--rebuild-tables` - Перестроить таблицы эмбеддингов
* `--clear-invalid` - Очистить эмбеддинги с неправильной размерностью
* `--parent-context N` - Уровни родительского контекста (0 - отключено)
* `--child-context N` - Уровни дочернего контекста (0 - отключено)
* **Интерфейс**: Консольное приложение с интерактивным режимом взаимодействия
* **Отладка**: Расширенные возможности отладки и анализа работы системы