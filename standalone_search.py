#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone Search Mode

Этот модуль предоставляет автономный режим для поиска текстовых блоков,
формирования запросов к ИИ и сохранения результатов в базе данных.

Основные функции:
1. Поиск текстовых блоков в базе данных
2. Выбор блоков для формирования контекста
3. Отправка запросов к OpenAI API
4. Сохранение диалогов в базе данных

Использование:
    python standalone_search.py
"""

import psycopg2
import uuid
import sys
from config import DB_CONFIG, OPENAI_API_KEY, MODELS
from openai import OpenAI
import logging
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("standalone_search.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Создаем клиент OpenAI
client = OpenAI(api_key=OPENAI_API_KEY, timeout=60.0)

def search_items(query, use_embeddings=False, limit=20):
    """
    Поиск элементов в базе данных по запросу.
    
    Args:
        query: Текст для поиска
        use_embeddings: Использовать ли векторный поиск
        limit: Максимальное количество результатов
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                if use_embeddings and 'embeddings' in get_tables(cur):
                    # Проверяем наличие модуля для работы с эмбеддингами
                    try:
                        from embeddings import get_embedding
                        
                        # Получаем эмбеддинг для запроса
                        query_embedding = get_embedding(query)
                        
                        # Выполняем векторный поиск
                        cur.execute("""
                            SELECT i.id, i.txt,
                                   1 - (e.embedding <=> %s) as similarity
                            FROM items i
                            JOIN embeddings e ON i.id = e.item_id
                            ORDER BY similarity DESC
                            LIMIT %s
                        """, (query_embedding, limit))
                        
                        return [(row[0], row[1]) for row in cur.fetchall()]
                    except ImportError:
                        logger.warning("Модуль embeddings не найден, используем текстовый поиск")
                        use_embeddings = False
                
                # Если векторный поиск не используется или недоступен, используем текстовый
                cur.execute("""
                    SELECT id, txt
                    FROM items
                    WHERE txt ILIKE %s
                    LIMIT %s
                """, (f"%{query}%", limit))
                
                return cur.fetchall()
    except Exception as e:
        logger.error(f"Ошибка при поиске элементов: {str(e)}")
        return []

def get_tables(cur=None):
    """Получает список таблиц в базе данных."""
    close_conn = False
    conn = None
    
    try:
        if cur is None:
            conn = get_connection()
            cur = conn.cursor()
            close_conn = True
            
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)
        
        tables = [row[0] for row in cur.fetchall()]
        
        if close_conn and conn:
            cur.close()
            conn.close()
            
        return tables
    except Exception as e:
        logger.error(f"Ошибка при получении списка таблиц: {str(e)}")
        
        if close_conn and conn:
            try:
                cur.close()
                conn.close()
            except:
                pass
                
        return []

def get_connection():
    """Создает подключение к базе данных."""
    return psycopg2.connect(**DB_CONFIG)

def select_blocks(results):
    """Выбор блоков из результатов поиска."""
    selected_blocks = []
    for index, (block_id, text) in enumerate(results):
        print(f"{index + 1}: ID: {block_id}, Текст: {text[:50]}...")
    while True:
        choice = input("Выберите номер блока для добавления в контекст (или 'done' для завершения): ")
        if choice.lower() == 'done':
            break
        try:
            index = int(choice) - 1
            if 0 <= index < len(results):
                selected_blocks.append(results[index])
            else:
                print("Неверный номер. Попробуйте снова.")
        except ValueError:
            print("Пожалуйста, введите номер или 'done'.")
    return selected_blocks

def query_ai(selected_blocks, user_query):
    """Отправка запроса к OpenAI с выбранными блоками в качестве контекста."""
    try:
        # Формируем контекст из выбранных блоков
        context = "\n\n".join([f"ID: {block_id}\nТекст: {text}" for block_id, text in selected_blocks])
        
        # Формируем промпт
        prompt = f"""Контекст:
{context}

Вопрос пользователя:
{user_query}

Пожалуйста, ответьте на вопрос пользователя, используя предоставленный контекст."""
        
        # Отправляем запрос к OpenAI
        response = client.chat.completions.create(
            model=MODELS['generation']['name'],
            messages=[
                {"role": "system", "content": "Вы помощник, который отвечает на вопросы, используя предоставленный контекст."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=1000
        )
        
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка при запросе к OpenAI: {str(e)}")
        return f"Произошла ошибка при запросе к ИИ: {str(e)}"

def save_dialogue(selected_blocks, user_query, ai_response, parent_id=None):
    """Сохранение диалога в базу данных."""
    try:
        # Если parent_id не указан, используем ID первого выбранного блока
        if parent_id is None and selected_blocks:
            parent_id = selected_blocks[0][0]
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Создаем новую запись для диалога
                dialogue_id = str(uuid.uuid4())
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                dialogue_text = f"Запрос: {user_query}\n\nОтвет: {ai_response}\n\nВремя: {timestamp}"
                
                # Вставляем запись диалога
                cur.execute("""
                    INSERT INTO items (id, id_parent, txt)
                    VALUES (%s, %s, %s)
                """, (dialogue_id, parent_id, dialogue_text))
                
                # Для каждого выбранного блока создаем дочерний элемент
                for block_id, text in selected_blocks:
                    child_id = str(uuid.uuid4())
                    cur.execute("""
                        INSERT INTO items (id, id_parent, txt)
                        VALUES (%s, %s, %s)
                    """, (child_id, dialogue_id, f"Контекст из блока {block_id}: {text[:100]}..."))
                
                conn.commit()
                return dialogue_id
    except Exception as e:
        logger.error(f"Ошибка при сохранении диалога: {str(e)}")
        return None

def main():
    """Основная функция для запуска консольного интерфейса."""
    search_history = []  # История поисковых запросов
    selected_blocks = []  # Выбранные блоки
    current_results = []  # Текущие результаты поиска
    
    print("=== Режим поиска и запросов к ИИ ===")
    print("Вы можете искать текстовые блоки, выбирать их и формировать запросы к ИИ.")
    
    while True:
        print("\nДоступные действия:")
        print("1. Новый поиск")
        print("2. Выбрать блоки из текущих результатов")
        if search_history:
            print("3. Выбрать блоки из предыдущих результатов")
        if selected_blocks:
            print("4. Сформировать запрос к ИИ")
            print("5. Сохранить диалог")
        print("0. Выход")
        
        choice = input("Выберите действие: ")
        
        if choice == "0":
            print("Выход из программы.")
            break
            
        elif choice == "1":
            # Новый поиск
            query = input("Введите поисковый запрос: ")
            
            # Выбор типа поиска
            search_type = input("Выберите тип поиска (1 - обычный, 2 - векторный): ")
            use_embeddings = (search_type == "2")
            
            if use_embeddings:
                print("Используем векторный поиск...")
            else:
                print("Используем обычный текстовый поиск...")
                
            current_results = search_items(query, use_embeddings=use_embeddings)
            
            if current_results:
                print(f"Найдено {len(current_results)} результатов:")
                for i, (block_id, text) in enumerate(current_results):
                    print(f"{i+1}. ID: {block_id}")
                    print(f"   Текст: {text[:100]}...")
                
                # Добавляем результаты в историю
                search_history.append((query, current_results))
            else:
                print("По вашему запросу ничего не найдено.")
                
        elif choice == "2" and current_results:
            # Выбор блоков из текущих результатов
            selected_blocks = select_blocks(current_results)
            print(f"Выбрано {len(selected_blocks)} блоков.")
            
        elif choice == "3" and search_history:
            # Выбор из предыдущих результатов
            print("История поиска:")
            for i, (query, _) in enumerate(search_history):
                print(f"{i+1}. Запрос: {query}")
            
            try:
                history_index = int(input("Выберите номер запроса: ")) - 1
                if 0 <= history_index < len(search_history):
                    _, history_results = search_history[history_index]
                    blocks_from_history = select_blocks(history_results)
                    selected_blocks.extend(blocks_from_history)
                    print(f"Всего выбрано {len(selected_blocks)} блоков.")
                else:
                    print("Неверный номер запроса.")
            except ValueError:
                print("Пожалуйста, введите номер.")
                
        elif choice == "4" and selected_blocks:
            # Формирование запроса к ИИ
            user_query = input("Введите ваш запрос к ИИ: ")
            print("\nОтправка запроса к ИИ...")
            ai_response = query_ai(selected_blocks, user_query)
            
            print("\n=== Ответ ИИ ===")
            print(ai_response)
            print("=== Конец ответа ===")
            
            # Сохраняем последний диалог
            last_dialogue = (selected_blocks, user_query, ai_response)
            
        elif choice == "5" and 'last_dialogue' in locals():
            # Сохранение диалога
            blocks, query, response = last_dialogue
            
            # Выбор родительского блока
            parent_id = None
            print("\nВыберите родительский блок для сохранения диалога:")
            print("0. Использовать первый выбранный блок (по умолчанию)")
            for i, (block_id, text) in enumerate(blocks):
                print(f"{i+1}. ID: {block_id}, Текст: {text[:50]}...")
            
            parent_choice = input("Выберите номер (или нажмите Enter для значения по умолчанию): ")
            if parent_choice and parent_choice != "0":
                try:
                    parent_index = int(parent_choice) - 1
                    if 0 <= parent_index < len(blocks):
                        parent_id = blocks[parent_index][0]
                except ValueError:
                    pass
            
            # Сохраняем диалог
            dialogue_id = save_dialogue(blocks, query, response, parent_id)
            if dialogue_id:
                print(f"Диалог успешно сохранен с ID: {dialogue_id}")
            else:
                print("Ошибка при сохранении диалога.")
        
        else:
            print("Неверный выбор или недоступное действие.")

def run_standalone_mode():
    """Запуск программы в автономном режиме."""
    try:
        # Проверка подключения к базе данных
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
        
        # Проверка доступа к OpenAI API
        if not OPENAI_API_KEY:
            logger.error("API ключ OpenAI не настроен. Проверьте файл config.py")
            print("Ошибка: API ключ OpenAI не настроен. Проверьте файл config.py")
            return False
        
        # Запуск основного интерфейса
        main()
        return True
    except psycopg2.Error as e:
        logger.error(f"Ошибка подключения к базе данных: {str(e)}")
        print(f"Ошибка подключения к базе данных: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Непредвиденная ошибка: {str(e)}")
        print(f"Произошла ошибка: {str(e)}")
        return False

if __name__ == "__main__":
    print("Запуск режима поиска и запросов к ИИ...")
    success = run_standalone_mode()
    if not success:
        print("Программа завершена с ошибкой.")
        sys.exit(1)