from typing import List, Dict, Any, Optional
from openai import OpenAI
from config import OPENAI_API_KEY, MODELS, RAG_SETTINGS
import numpy as np
import logging
from debug_utils import debug_step
from openai_api_models import client
import hashlib
from db import get_connection
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
    """
    Ищет кэшированный эмбеддинг запроса в базе данных
    
    Args:
        query_text: Текст запроса
        model: Название модели эмбеддинга
    
    Returns:
        Найденный эмбеддинг или None, если не найден
    """
    try:
        text_hash = get_text_hash(query_text)
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT embedding, dimensions FROM query_embeddings 
                    WHERE text_hash = %s AND model = %s
                """, (text_hash, model))
                
                result = cur.fetchone()
                
                if result:
                    embedding = result[0]
                    dimensions = result[1]
                    
                    # Проверяем, соответствует ли размерность ожидаемой
                    if dimensions != MODELS['embedding']['dimensions']:
                        logger.warning(f"Кэшированный эмбеддинг запроса имеет неправильную размерность: {dimensions} вместо {MODELS['embedding']['dimensions']}")
                        return None
                    
                    logger.debug(f"Используем кэшированный эмбеддинг для запроса '{query_text[:30]}...'")
                    return embedding
                
                return None
    except Exception as e:
        logger.error(f"Ошибка при получении кэшированного эмбеддинга запроса: {str(e)}")
        return None

def save_query_embedding_to_cache(query_text: str, embedding: List[float], model: str) -> bool:
    """Сохраняет эмбеддинг запроса в кэш"""
    try:
        text_hash = get_text_hash(query_text)
        dimensions = len(embedding)
        model_version = MODELS['embedding']['version']  # Получаем версию модели
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Используем UPSERT через ON CONFLICT
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
                """, (query_text, text_hash, embedding, dimensions, model, model_version))
                
                conn.commit()
                logger.debug(f"Сохранен эмбеддинг запроса '{query_text[:30]}...'")
                return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении эмбеддинга запроса: {str(e)}")
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
        # Получаем модель из конфигурации или используем переданную
        if model is None:
            model = MODELS['embedding']['name']
            
        # Проверяем кэш для запросов (только для коротких текстов)
        if len(text) < 500:  # Кэшируем только короткие запросы
            cached_embedding = get_query_embedding_from_cache(text, model)
            if cached_embedding:
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
        if len(text) < 500:
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
def create_embedding_for_item(item: Dict) -> Dict:
    """
    Создает эмбеддинг для элемента
    """
    try:
        # Собираем текст из:
        texts = []
        
        # 1. Родительских элементов
        if item.get('parents'):
            for parent in item['parents']:
                if parent and parent[2]:  # parent[2] - это текст
                    # Удаляем "admin" из начала текста, если он там есть
                    parent_text = parent[2]
                    if parent_text.startswith("admin "):
                        parent_text = parent_text[6:]  # Удаляем первые 6 символов "admin "
                    texts.append(parent_text)
        
        # 2. Самого элемента
        if item['item'] and item['item'][2]:
            # Удаляем "admin" из начала текста
            item_text = item['item'][2]
            if item_text.startswith("admin "):
                item_text = item_text[6:]  # Удаляем первые 6 символов "admin "
            texts.append(item_text)
        
        # 3. Дочерних элементов
        if item.get('children'):
            for child in item['children']:
                if child and child[2]:
                    # Удаляем "admin" из начала текста
                    child_text = child[2]
                    if child_text.startswith("admin "):
                        child_text = child_text[6:]  # Удаляем первые 6 символов "admin "
                    texts.append(child_text)
        
        # Объединяем все тексты в один
        combined_text = " ".join(texts)
        
        # Ограничиваем по токенам вместо слов
        # Используем более безопасный лимит в 7000 токенов (меньше максимума в 8192)
        max_tokens = 7000
        token_count = count_tokens(combined_text)
        
        if token_count > max_tokens:
            logger.warning(f"Текст слишком длинный ({token_count} токенов), обрезаем до {max_tokens} токенов")
            
            # Обрезаем текст по токенам
            encoding = tiktoken.encoding_for_model(MODELS['embedding']['name'])
            tokens = encoding.encode(combined_text)
            truncated_tokens = tokens[:max_tokens]
            combined_text = encoding.decode(truncated_tokens)
            
            # Проверяем новое количество токенов после обрезки
            new_token_count = count_tokens(combined_text)
            logger.debug(f"После обрезки: {new_token_count} токенов")
        
        # Получаем ID элемента
        item_id = item['item'][0]
        model = MODELS['embedding']['name']
        
        # Проверяем, есть ли уже эмбеддинг в базе
        cached_embedding = get_embedding_from_db(item_id, model)
        
        # Если эмбеддинг найден и текст не изменился
        if cached_embedding and get_text_hash(combined_text) == cached_embedding['text_hash']:
            logger.debug(f"Используем кэшированный эмбеддинг для элемента {item_id}")
            embedding = cached_embedding['embedding']
        else:
            # Получаем новый эмбеддинг и сохраняем его
            embedding = get_embedding(combined_text)
            save_embedding_to_db(item_id, embedding, combined_text, model)
        
        return {
            'text': combined_text,
            'embedding': embedding,
            'dimensions': len(embedding)
        }
    except Exception as e:
        logger.error(f"Ошибка при создании эмбеддинга для элемента: {str(e)}")
        
        # Более безопасное возвращение значения в случае ошибки
        # Создаем эмбеддинг только для самого элемента, без контекста
        try:
            simplified_text = ""
            if item['item'] and item['item'][2]:
                simplified_text = item['item'][2]
                if simplified_text.startswith("admin "):
                    simplified_text = simplified_text[6:]
                    
                # Ограничиваем длину
                if count_tokens(simplified_text) > 7000:
                    encoding = tiktoken.encoding_for_model(MODELS['embedding']['name'])
                    tokens = encoding.encode(simplified_text)
                    simplified_text = encoding.decode(tokens[:7000])
                    
                # Создаем эмбеддинг только для этого текста
                embedding = get_embedding(simplified_text)
                return {
                    'text': simplified_text,
                    'embedding': embedding,
                    'dimensions': len(embedding)
                }
        except Exception as inner_e:
            logger.error(f"Ошибка при создании запасного эмбеддинга: {str(inner_e)}")
            # В крайнем случае, возвращаем пустой эмбеддинг нужной размерности
            dimensions = MODELS['embedding']['dimensions']
            return {
                'text': 'Ошибка при обработке текста',
                'embedding': [0.0] * dimensions,
                'dimensions': dimensions
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