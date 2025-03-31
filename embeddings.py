from typing import List, Dict, Any, Optional
from openai import OpenAI
from config import OPENAI_API_KEY, MODELS, RAG_SETTINGS
import numpy as np
import logging
from debug_utils import debug_step
from openai_api_models import client
import hashlib
from db import get_connection, create_embeddings_table, create_query_embeddings_table
from utils import timeit, ProgressIndicator
from base64 import b64decode
import struct
import tiktoken  # Добавляем библиотеку tiktoken для точного подсчета токенов
import json  # Добавляем для корректной сериализации/десериализации

logger = logging.getLogger(__name__)

def get_text_hash(text: str) -> str:
    """Возвращает SHA-256 хеш текста"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def get_query_embedding_from_cache(query_text: str, model: str) -> Optional[List[float]]:
    """Ищет кэшированный эмбеддинг запроса в базе данных"""
    try:
        text_hash = get_text_hash(query_text)
        model_version = MODELS['embedding']['version']
        
        print(f"DEBUG: Ищем кэш для запроса: '{query_text[:50]}...'")
        print(f"DEBUG: Хеш запроса: {text_hash}")
        print(f"DEBUG: Модель: {model}, версия: {model_version}")
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Сначала проверим существование таблицы
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'query_embeddings'
                    )
                """)
                table_exists = cur.fetchone()[0]
                print(f"DEBUG: Таблица query_embeddings существует: {table_exists}")
                
                if not table_exists:
                    print("DEBUG: Таблица query_embeddings не существует!")
                    return None
                
                # Проверяем наличие записи
                cur.execute("""
                    SELECT COUNT(*) FROM query_embeddings 
                    WHERE text_hash = %s AND model = %s AND model_version = %s
                """, (text_hash, model, model_version))
                count = cur.fetchone()[0]
                print(f"DEBUG: Найдено записей с таким хешем и моделью: {count}")
                
                # Теперь пытаемся получить эмбеддинг
                cur.execute("""
                    SELECT embedding, dimensions FROM query_embeddings 
                    WHERE text_hash = %s AND model = %s AND model_version = %s
                """, (text_hash, model, model_version))
                
                result = cur.fetchone()
                
                if result:
                    print("DEBUG: Найден кэшированный эмбеддинг!")
                    
                    # Проверим тип и структуру данных эмбеддинга
                    embedding_data = result[0]
                    print(f"DEBUG: Тип эмбеддинга: {type(embedding_data)}")
                    print(f"DEBUG: Первые 10 значений: {str(embedding_data)[:100]}")
                    
                    # Преобразуем в список, если нужно
                    embedding = embedding_data
                    if isinstance(embedding_data, str):
                        print("DEBUG: Преобразуем строковое представление в список")
                        try:
                            # Обработка строки [1.2, 3.4, ...] -> список
                            embedding = json.loads(embedding_data)
                        except json.JSONDecodeError:
                            # Для старого формата строки без пробелов
                            embedding = [float(x) for x in embedding_data.strip('[]').split(',')]
                    
                    dimensions = result[1]
                    
                    # Проверяем, соответствует ли размерность ожидаемой
                    expected_dim = MODELS['embedding']['dimensions']
                    print(f"DEBUG: Размерность эмбеддинга: {dimensions}, ожидаемая: {expected_dim}")
                    
                    if dimensions != expected_dim:
                        print(f"DEBUG: Неправильная размерность, кэш не используется")
                        return None
                    
                    print(f"DEBUG: Успешно получен кэшированный эмбеддинг!")
                    return embedding
                else:
                    print("DEBUG: Кэшированный эмбеддинг не найден")
                return None
    except Exception as e:
        print(f"ERROR при получении кэшированного эмбеддинга: {str(e)}")
        import traceback
        traceback.print_exc()
        return None

def save_query_embedding_to_cache(query_text: str, embedding: List[float], model: str) -> bool:
    """Сохраняет эмбеддинг запроса в кэш"""
    try:
        text_hash = get_text_hash(query_text)
        dimensions = len(embedding)
        model_version = MODELS['embedding']['version']
        
        print(f"DEBUG: Сохраняем эмбеддинг для запроса: '{query_text[:50]}...'")
        print(f"DEBUG: Хеш запроса: {text_hash}")
        print(f"DEBUG: Размерность эмбеддинга: {dimensions}")
        print(f"DEBUG: Модель: {model}, версия: {model_version}")
        
        # Преобразуем эмбеддинг в JSON строку для PostgreSQL
        embedding_json = json.dumps(embedding)
        print(f"DEBUG: Эмбеддинг преобразован в JSON: {embedding_json[:50]}...")
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Проверяем существование таблицы
                cur.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'query_embeddings'
                    )
                """)
                table_exists = cur.fetchone()[0]
                print(f"DEBUG: Таблица query_embeddings существует: {table_exists}")
                
                if not table_exists:
                    print("DEBUG: Таблица query_embeddings не существует! Создаём...")
                    create_query_embeddings_table()
                
                # Сохраняем или обновляем запись
                try:
                    cur.execute("""
                        INSERT INTO query_embeddings 
                        (text, text_hash, embedding, dimensions, model, model_version, frequency, last_used, created_at) 
                        VALUES (%s, %s, %s, %s, %s, %s, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (text_hash, model, model_version) 
                        DO UPDATE SET 
                            embedding = EXCLUDED.embedding,
                            dimensions = EXCLUDED.dimensions,
                            frequency = query_embeddings.frequency + 1,
                            last_used = CURRENT_TIMESTAMP
                    """, (query_text, text_hash, embedding_json, dimensions, model, model_version))
                    
                    conn.commit()
                    print(f"DEBUG: Успешно сохранен эмбеддинг запроса")
                    return True
                except Exception as e:
                    print(f"ERROR при выполнении SQL запроса: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    return False
    except Exception as e:
        print(f"ERROR при сохранении эмбеддинга запроса: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def decode_base64_embedding(base64_string):
    """Декодирует эмбеддинг из base64 в список чисел с плавающей точкой"""
    try:
        # Декодируем base64 в бинарные данные
        binary_data = b64decode(base64_string)
        
        # Каждое число float занимает 4 байта
        num_floats = len(binary_data) // 4
        
        # Распаковываем бинарные данные в список чисел float
        floats = struct.unpack(f'{num_floats}f', binary_data)
        
        return list(floats)
    except Exception as e:
        logger.error(f"Ошибка при декодировании base64 эмбеддинга: {str(e)}")
        return []

@timeit
def get_embedding(text: str, model: str = None) -> List[float]:
    """
    Получает эмбеддинг для текста используя указанную модель
    """
    try:
        # Явно создаем таблицы, если они не существуют
        create_embeddings_table()
        create_query_embeddings_table()
        
        # Получаем модель из конфигурации или используем переданную
        if model is None:
            model = MODELS['embedding']['name']
            
        # Проверяем кэш для запросов (синхронизируем с условием сохранения)
        if len(text) < 1500:  # Изменено с 500 на 1500
            cached_embedding = get_query_embedding_from_cache(text, model)
            if cached_embedding:
                logger.info(f"Используем кэшированный эмбеддинг для текста длиной {len(text)}")
                return cached_embedding
        
        # Первый вызов debug_step - ОСТАВИТЬ
        new_params = debug_step('embeddings', {
            'text': text,
            'model': model
        })
        
        if new_params and 'model' in new_params:
            model = new_params['model']
            
        # Показываем индикатор прогресса при вызове API
        progress = ProgressIndicator("Генерация эмбеддинга")
        progress.start()
        try:
            response = client.embeddings.create(
                input=text,
                model=model,
                encoding_format="float"
            )
        finally:
            progress.stop()
        
        embedding = response.data[0].embedding
        
        # Кэшируем короткие запросы
        if len(text) < 1500:
            save_query_embedding_to_cache(text, embedding, model)
        
        return embedding
    except Exception as e:
        logger.error(f"Ошибка при получении эмбеддинга: {str(e)}")
        raise

def save_embedding_to_db(item_id: str, embedding: List[float], text: str, model: str = None) -> bool:
    """Сохраняет эмбеддинг в базу данных"""
    if model is None:
        model = MODELS['embedding']['name']
        
    model_version = MODELS['embedding']['version']  # Получаем версию модели
    text_hash = get_text_hash(text)
    dimensions = len(embedding)
    
    try:
        # Преобразуем эмбеддинг в строку, без дополнительных кавычек
        # Используем простое строковое представление для типа vector в PostgreSQL
        embedding_str = str(embedding).replace(' ', '')
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Проверяем, есть ли уже запись для данного элемента и модели
                cur.execute("""
                    SELECT id FROM embeddings 
                    WHERE item_id = %s AND model = %s AND model_version = %s
                """, (item_id, model, model_version))
                
                result = cur.fetchone()
                
                if result:
                    # Обновляем существующую запись
                    cur.execute("""
                        UPDATE embeddings 
                        SET embedding = %s, text = %s, text_hash = %s, dimensions = %s, updated_at = NOW()
                        WHERE item_id = %s AND model = %s AND model_version = %s
                    """, (embedding_str, text, text_hash, dimensions, item_id, model, model_version))
                else:
                    # Создаем новую запись
                    cur.execute("""
                        INSERT INTO embeddings 
                        (item_id, embedding, text, text_hash, model, model_version, dimensions, created_at, updated_at)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                    """, (item_id, embedding_str, text, text_hash, model, model_version, dimensions))
                
                conn.commit()
                logger.debug(f"Сохранен эмбеддинг для элемента {item_id}, модель {model}, версия {model_version}")
                return True
                
    except Exception as e:
        logger.error(f"Ошибка при сохранении эмбеддинга: {str(e)}")
        return False

def get_embedding_from_db(item_id: str, model: str = None) -> Optional[Dict]:
    """Получает эмбеддинг из базы данных"""
    if model is None:
        model = MODELS['embedding']['name']
    
    model_version = MODELS['embedding']['version']  # Получаем версию модели
        
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT embedding, text_hash, created_at
                    FROM embeddings 
                    WHERE item_id = %s AND model = %s AND model_version = %s
                """, (item_id, model, model_version))
                
                result = cur.fetchone()
                
                if result:
                    # Исправляем проблему с форматом эмбеддинга
                    embedding = result[0]
                    
                    # Преобразуем строку в список, если необходимо
                    if isinstance(embedding, str):
                        try:
                            # Пробуем декодировать как JSON
                            embedding = json.loads(embedding)
                        except json.JSONDecodeError:
                            # Если не получается, разделяем по запятым (для старых записей)
                            embedding = [float(x) for x in embedding.strip('[]').split(',')]
                    
                    # Проверяем размерность эмбеддинга
                    if len(embedding) != MODELS['embedding']['dimensions']:
                        logger.warning(f"Эмбеддинг с неправильной размерностью: {len(embedding)} вместо {MODELS['embedding']['dimensions']}")
                        # Удаляем эмбеддинг с неправильной размерностью
                        cur.execute("""
                            DELETE FROM embeddings 
                            WHERE item_id = %s AND model = %s
                        """, (item_id, model))
                        conn.commit()
                        return None
                    
                    return {
                        'embedding': embedding,
                        'text_hash': result[1],
                        'created_at': result[2]
                    }
                return None
    except Exception as e:
        logger.error(f"Ошибка при получении эмбеддинга: {str(e)}")
        return None

def count_tokens(text: str, model: str = None) -> int:
    """Подсчитывает точное количество токенов в тексте"""
    if model is None:
        model = MODELS['embedding']['name']
    
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        # Если модель не поддерживается tiktoken, используем стандартную кодировку
        encoding = tiktoken.get_encoding("cl100k_base")  # Кодировка для моделей embedding
        return len(encoding.encode(text))

@timeit
def create_embedding_for_item(item):
    """
    Создает эмбеддинг для элемента с учетом его структуры и родительских/дочерних элементов
    """
    try:
        if 'item' in item:
            item_id, parent_id, item_text = item['item']
            
            # Создаем основной текст
            text = item_text.strip() if item_text else ""
            
            # ВРЕМЕННО ЗАКОММЕНТИРОВАНО: Объединение с родительскими элементами
            # if 'parents' in item and item['parents']:
            #     for parent in item['parents']:
            #         parent_text = parent[2].strip() if parent[2] else ""
            #         if parent_text:
            #             text = f"{parent_text}\n\n{text}"
            
            # ВРЕМЕННО ЗАКОММЕНТИРОВАНО: Объединение с дочерними элементами
            # if 'children' in item and item['children']:
            #     for child in item['children']:
            #         child_text = child[2].strip() if child[2] else ""
            #         if child_text:
            #             text = f"{text}\n\n{child_text}"
            
            # Возвращаем эмбеддинг и исходный текст
            embedding = get_embedding(text)
            return {
                'embedding': embedding,
                'text': text,
                'item_id': item_id
            }
        else:
            raise ValueError("Неверный формат элемента")
    except Exception as e:
        logging.getLogger('embeddings').error(f"Ошибка при создании эмбеддинга для элемента: {str(e)}")
        
        # Пытаемся создать запасной эмбеддинг
        try:
            text = str(item)
            embedding = get_embedding(text)
            return {
                'embedding': embedding,
                'text': text,
                'item_id': 'unknown'
            }
        except Exception as e2:
            logging.getLogger('embeddings').error(f"Ошибка при создании запасного эмбеддинга: {str(e2)}")
            return {
                'embedding': [],
                'text': '',
                'item_id': 'error'
            }

@timeit
def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Вычисляет косинусное сходство между двумя эмбеддингами
    """
    try:
        # Проверка и преобразование типов
        if isinstance(embedding1, str):
            try:
                embedding1 = json.loads(embedding1)
            except json.JSONDecodeError:
                embedding1 = [float(x) for x in embedding1.strip('[]').split(',')]
        
        if isinstance(embedding2, str):
            try:
                embedding2 = json.loads(embedding2)
            except json.JSONDecodeError:
                embedding2 = [float(x) for x in embedding2.strip('[]').split(',')]
        
        # Проверяем размерности
        if len(embedding1) != len(embedding2):
            logger.warning(f"Разные размерности эмбеддингов: {len(embedding1)} != {len(embedding2)}")
            # Более детальная информация для отладки
            logger.debug(f"Первый эмбеддинг: тип={type(embedding1)}, размер={len(embedding1)}")
            logger.debug(f"Второй эмбеддинг: тип={type(embedding2)}, размер={len(embedding2)}")
            
            # Приводим эмбеддинги к одинаковой размерности, используя меньшую из двух
            min_size = min(len(embedding1), len(embedding2))
            embedding1 = embedding1[:min_size]
            embedding2 = embedding2[:min_size]
            logger.info(f"Эмбеддинги обрезаны до размера {min_size}")
            
        # Преобразуем в numpy массивы, явно указывая тип float
        vec1 = np.array(embedding1, dtype=np.float64)
        vec2 = np.array(embedding2, dtype=np.float64)
        
        # Вычисляем косинусное сходство
        similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        
        return float(similarity)
    except Exception as e:
        logger.warning(f"Ошибка при вычислении сходства: {str(e)}")
        return 0.0  # Возвращаем минимальное сходство вместо ошибки

if __name__ == '__main__':
    # Пример использования
    from db import get_items_sample
    
    # Получаем несколько элементов для тестирования
    items = get_items_sample(1, 2)
    
    for item in items:
        # Создаем эмбеддинг для каждого элемента
        embedding_data = create_embedding_for_item(item)
        print(f"\nItem ID: {item['item'][0]}")
        print(f"Text length: {len(embedding_data['text'])}")
        print(f"Embedding dimensions: {embedding_data['dimensions']}") 