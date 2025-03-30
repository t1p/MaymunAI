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
* **Интерфейс**: Консольное приложение с интерактивным режимом взаимодействия
* **Отладка**: Расширенные возможности отладки и анализа работы системы