from typing import List, Dict, Any, Optional
from openai import OpenAI
from config import OPENAI_API_KEY, MODELS, RAG_SETTINGS
import numpy as np
import logging
from debug_utils import debug_step
from openai_api_models import client
import hashlib
from db import get_connection

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
    """
    Сохраняет эмбеддинг запроса в кэш
    
    Args:
        query_text: Текст запроса
        embedding: Эмбеддинг для сохранения
        model: Название модели эмбеддинга
    """
    try:
        text_hash = get_text_hash(query_text)
        dimensions = len(embedding)
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Используем UPSERT через ON CONFLICT
                cur.execute("""
                    INSERT INTO query_embeddings 
                    (text, text_hash, embedding, dimensions, model, created_at) 
                    VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (text_hash, model) 
                    DO UPDATE SET 
                        embedding = EXCLUDED.embedding,
                        dimensions = EXCLUDED.dimensions,
                        created_at = CURRENT_TIMESTAMP
                """, (query_text, text_hash, embedding, dimensions, model))
                
                conn.commit()
                logger.debug(f"Сохранен эмбеддинг запроса '{query_text[:30]}...'")
                return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении эмбеддинга запроса: {str(e)}")
        return False

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
            
        # Отладка: показываем текст перед генерацией эмбеддинга
        new_params = debug_step('embeddings', {
            'text': text,
            'model': model
        })
        
        if new_params and 'model' in new_params:
            model = new_params['model']
            
        response = client.embeddings.create(
            model=model,
            input=text
        )
        embedding = response.data[0].embedding
        
        # Отладка: показываем полученный эмбеддинг
        debug_step('embeddings', {
            'text': text,
            'model': model,
            'dimensions': len(embedding),
            'embedding': embedding
        })
        
        # Кэшируем короткие запросы
        if len(text) < 500:
            save_query_embedding_to_cache(text, embedding, model)
        
        return embedding
    except Exception as e:
        logger.error(f"Ошибка при получении эмбеддинга: {str(e)}")
        raise

def save_embedding_to_db(item_id: str, embedding: List[float], text: str, model: str) -> bool:
    """Сохраняет эмбеддинг в базе данных"""
    try:
        text_hash = get_text_hash(text)
        
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Проверяем, существует ли уже эмбеддинг для этого элемента с этой моделью
                cur.execute("""
                    SELECT id, text_hash FROM embeddings 
                    WHERE item_id = %s AND model = %s
                """, (item_id, model))
                
                existing = cur.fetchone()
                
                if existing:
                    # Если хеш текста изменился, обновляем эмбеддинг
                    if existing[1] != text_hash:
                        cur.execute("""
                            UPDATE embeddings 
                            SET embedding = %s, text_hash = %s, created_at = CURRENT_TIMESTAMP
                            WHERE id = %s
                        """, (embedding, text_hash, existing[0]))
                else:
                    # Создаем новую запись
                    cur.execute("""
                        INSERT INTO embeddings (item_id, embedding, model, text_hash)
                        VALUES (%s, %s, %s, %s)
                    """, (item_id, embedding, model, text_hash))
                    
                conn.commit()
                return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении эмбеддинга: {str(e)}")
        return False

def get_embedding_from_db(item_id: str, model: str = None) -> Optional[Dict]:
    """Получает эмбеддинг из базы данных"""
    if model is None:
        model = MODELS['embedding']['name']
        
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT embedding, text_hash, created_at
                    FROM embeddings 
                    WHERE item_id = %s AND model = %s
                """, (item_id, model))
                
                result = cur.fetchone()
                
                if result:
                    return {
                        'embedding': result[0],
                        'text_hash': result[1],
                        'created_at': result[2]
                    }
                return None
    except Exception as e:
        logger.error(f"Ошибка при получении эмбеддинга: {str(e)}")
        return None

def create_embedding_for_item(item: Dict) -> Dict:
    """
    Создает эмбеддинг для элемента с учетом контекста
    """
    try:
        # Собираем текст из:
        texts = []
        
        # 1. Родительских элементов
        if item.get('parents'):
            for parent in item['parents']:
                if parent and parent[2]:  # parent[2] - это текст
                    texts.append(parent[2])
        
        # 2. Самого элемента
        if item['item'] and item['item'][2]:
            texts.append(item['item'][2])
        
        # 3. Дочерних элементов
        if item.get('children'):
            for child in item['children']:
                if child and child[2]:
                    texts.append(child[2])
        
        # Объединяем все тексты в один
        combined_text = " ".join(texts)
        
        # Проверяем длину текста в токенах
        if len(combined_text.split()) > MODELS['embedding']['max_tokens']:
            logger.warning(f"Текст превышает максимальное количество токенов ({MODELS['embedding']['max_tokens']})")
            # Обрезаем текст до максимального количества токенов
            combined_text = " ".join(combined_text.split()[:MODELS['embedding']['max_tokens']])
        
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
        raise

def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Вычисляет косинусное сходство между двумя эмбеддингами
    """
    try:
        # Проверяем размерности
        if len(embedding1) != len(embedding2):
            logger.warning(f"Разные размерности эмбеддингов: {len(embedding1)} != {len(embedding2)}")
            return 0.0  # Возвращаем минимальное сходство вместо ошибки
            
        # Преобразуем в numpy массивы
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Вычисляем косинусное сходство
        similarity = np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2))
        
        # Отладка: показываем результат сравнения
        debug_step('similarity', {
            'dimensions': len(embedding1),
            'similarity': similarity
        })
        
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