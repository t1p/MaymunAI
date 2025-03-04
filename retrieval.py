from typing import List, Dict, Any, Optional
import numpy as np
from db import get_items_sample
from embeddings import get_embedding, calculate_similarity, create_embedding_for_item
from config import SEARCH_SETTINGS, RAG_SETTINGS, DEBUG
from debug_utils import debug_step
import logging
from utils import timeit
from config_db import get_threshold

logger = logging.getLogger(__name__)

@timeit
def search_similar_items(query: str, items: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
    """
    Ищет наиболее релевантные элементы для заданного запроса
    """
    if top_k is None:
        top_k = SEARCH_SETTINGS['top_k']
        
    logger.debug(f"Поиск похожих элементов для запроса: {query}")
    
    # 1. Создается эмбеддинг для запроса пользователя
    query_embedding = get_embedding(query)
    
    # Получаем параметры поиска (возможно, обновленные пользователем)
    search_params = debug_step('retrieval')
    logger.debug(f"Параметры из debug_step: {search_params}")
    
    # Получаем пороговое значение из базы данных
    db_threshold = get_threshold()
    logger.debug(f"Пороговое значение из БД: {db_threshold}")
    
    # Используем параметр из debug_step или из БД
    if search_params and 'similarity_threshold' in search_params:
        threshold = search_params['similarity_threshold']
        logger.debug(f"Используется пороговое значение из debug_step: {threshold}")
    else:
        threshold = db_threshold
        logger.debug(f"Используется пороговое значение из БД: {threshold}")
    
    logger.debug(f"Используемое пороговое значение: {threshold}")
    
    # Вычисляем эмбеддинги для всех элементов и их сходство с запросом
    similarities = []
    for item in items:
        try:
            # Создаем эмбеддинг для элемента
            embedding_data = create_embedding_for_item(item)
            
            # Вычисляем сходство с запросом
            similarity = calculate_similarity(query_embedding, embedding_data['embedding'])
            
            # Для диагностики выводим более подробную информацию
            if DEBUG['enabled']:
                logger.debug(f"Элемент: {item['item'][0]}, Сходство: {similarity:.4f}, Текст: {embedding_data['text'][:100]}...")
            
            # Добавляем информацию о сходстве
            similarities.append({
                'item': item,
                'embedding': embedding_data['embedding'],
                'text': embedding_data['text'],
                'similarity': similarity
            })
        except Exception as e:
            logger.warning(f"Ошибка при обработке элемента: {str(e)}")
    
    # Сортируем по убыванию сходства
    sorted_items = sorted(similarities, key=lambda x: x['similarity'], reverse=True)
    
    # Для диагностики
    if DEBUG['enabled']:
        print("\n==================== sorted_items ====================")
        for idx, item in enumerate(sorted_items[:5]):
            print(f"{idx+1}. Сходство: {item['similarity']:.4f}, Элемент: {item['item']['item'][0]}")
            print(f"   Текст: {item['text'][:150]}...\n")
        
        # Выводим пороговое значение
        print(f"Пороговое значение сходства: {threshold}")
    
    # Отбираем элементы с сходством выше порога
    result = [item for item in sorted_items if item['similarity'] >= threshold]
    
    # Если не найдено релевантных элементов, берем первый с наибольшим сходством
    if not result and sorted_items:
        logger.warning("Не найдено релевантных элементов, используем первый элемент из выборки")
        logger.debug(f"Максимальное сходство: {sorted_items[0]['similarity']}, порог: {threshold}")
        
        # Уменьшаем пороговое значение для этого запроса
        if DEBUG['enabled']:
            print(f"\nВНИМАНИЕ! Пороговое значение ({threshold}) слишком высокое.")
            print(f"Максимальное найденное сходство: {sorted_items[0]['similarity']:.4f}")
            print("Рекомендуется снизить пороговое значение в config.py (RAG_SETTINGS['similarity_threshold'])")
            
            # Используем лучший результат, даже если он ниже порога
            result = [sorted_items[0]]
    
    # Ограничиваем количество результатов
    result = result[:top_k]
    
    # Для отладки показываем найденные элементы
    if DEBUG['enabled']:
        print("\n==================== Поиск релевантных документов ====================\n")
        if result:
            for i, item in enumerate(result, 1):
                print(f"Документ {i}:")
                print(f"Сходство: {item['similarity']:.4f}")
                print(f"Текст: {item['text'][:300]}..." if len(item['text']) > 300 else item['text'])
                print()
        else:
            print("Документ 1:")
            print(f"Сходство: 0.5000")
            print(f"Текст: Информация отсутствует. Пользовательский запрос: {query}...")
            print()
    
    return result 