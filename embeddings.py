from typing import List, Dict, Any, Optional
from openai import OpenAI
from config import OPENAI_API_KEY, MODELS, RAG_SETTINGS
import numpy as np
import logging
from debug_utils import debug_step
from openai_api_models import client

logger = logging.getLogger(__name__)

def get_embedding(text: str, model: str = None) -> List[float]:
    """
    Получает эмбеддинг для текста используя указанную модель
    """
    try:
        # Получаем модель из конфигурации или используем переданную
        if model is None:
            model = MODELS['embedding']['name']
            
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
            'model': model,
            'dimensions': len(embedding),
            'embedding': embedding
        })
        
        return embedding
    except Exception as e:
        logger.error(f"Ошибка при получении эмбеддинга: {str(e)}")
        raise

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
        
        # Получаем эмбеддинг для объединенного текста
        embedding = get_embedding(combined_text)
        
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
            raise ValueError(f"Разные размерности эмбеддингов: {len(embedding1)} != {len(embedding2)}")
            
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
        logger.error(f"Ошибка при вычислении сходства: {str(e)}")
        raise

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