from typing import List, Dict, Any, Optional
import numpy as np
from db import get_items_sample
from embeddings import get_embedding, calculate_similarity, create_embedding_for_item
from config import SEARCH_SETTINGS, RAG_SETTINGS
from debug_utils import debug_step
import logging

logger = logging.getLogger(__name__)

def search_similar_items(query: str, items: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
    """
    Ищет наиболее релевантные элементы для заданного запроса
    """
    if top_k is None:
        top_k = SEARCH_SETTINGS['top_k']
        
    logger.debug(f"Поиск похожих элементов для запроса: {query}")
    
    # 1. Создается эмбеддинг для запроса пользователя
    query_embedding = get_embedding(query)
    
    # Отладка: показываем эмбеддинг запроса
    debug_step('embeddings', {'query': query, 'embedding': query_embedding})
    
    # Получаем параметры поиска (возможно, обновленные пользователем)
    search_params = debug_step('retrieval') or SEARCH_SETTINGS
    threshold = RAG_SETTINGS['similarity_threshold']  # Берем порог из RAG_SETTINGS
    
    # Вычисляем эмбеддинги для всех элементов и их сходство с запросом
    similarities = []
    for item in items:
        try:
            # 2. Создаются эмбеддинги для каждого элемента из выборки
            item_embedding_data = create_embedding_for_item(item)
            similarity = calculate_similarity(query_embedding, item_embedding_data['embedding'])
            
            # Добавляем только если текст не пустой и сходство выше порога
            if (item_embedding_data['text'].strip() and similarity >= threshold):
                similarities.append({
                    'item': item,
                    'similarity': similarity,
                    'text': item_embedding_data['text']
                })
                logger.debug(f"Добавлен элемент, сходство: {similarity:.4f}")
            
        except Exception as e:
            logger.warning(f"Ошибка при обработке элемента: {str(e)}")
            continue
    
    # Сортируем по убыванию сходства и берем top_k элементов
    similarities.sort(key=lambda x: x['similarity'], reverse=True)
    result = similarities[:top_k]
    
    # Отладка: показываем найденные документы
    debug_step('retrieval', result)
    
    logger.debug(f"Найдено {len(result)} релевантных элементов")
    return result 