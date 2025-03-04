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
        
    logger.debug(f"Поиск похожих элементов для запроса: {query}, top_k: {top_k}")
    
    # 1. Создается эмбеддинг для запроса пользователя
    query_embedding = get_embedding(query)
    
    # Получаем параметры поиска (возможно, обновленные пользователем)
    search_params = debug_step('retrieval')
    logger.debug(f"Параметры из debug_step: {search_params}")
    
    # Получаем пороговое значение из базы данных или конфигурации
    db_threshold = get_threshold()
    logger.debug(f"Пороговое значение из БД: {db_threshold}")
    
    # Используем параметр из debug_step, из БД или из конфигурации
    if search_params and 'similarity_threshold' in search_params:
        threshold = search_params['similarity_threshold']
        logger.debug(f"Используется пороговое значение из debug_step: {threshold}")
    else:
        # Здесь использовать значение из конфигурации, а не жестко заданное
        threshold = SEARCH_SETTINGS['similarity_threshold']
        logger.debug(f"Используется пороговое значение из конфигурации: {threshold}")
    
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
    
    # Для диагностики - показываем не только первые 5, а все top_k элементов
    if DEBUG['enabled']:
        print("\n==================== sorted_items ====================")
        for idx, item in enumerate(sorted_items[:top_k]):
            print(f"{idx+1}. Сходство: {item['similarity']:.4f}, Элемент: {item['item']['item'][0]}")
            print(f"   Текст: {item['text'][:150]}...\n")
        
        # Выводим пороговое значение
        print(f"Пороговое значение сходства: {threshold}")
    
    # ИЗМЕНЯЕМ ЛОГИКУ: Сначала берем top_k лучших документов
    top_results = sorted_items[:top_k]
    
    # Затем фильтруем по порогу только если у нас больше документов чем top_k
    if len(sorted_items) > top_k:
        # Отбираем элементы с сходством выше порога (старая логика)
        filtered_results = [item for item in sorted_items if item['similarity'] >= threshold]
        
        # Если после фильтрации осталось больше документов чем top_k, берем только top_k
        if len(filtered_results) > top_k:
            result = filtered_results[:top_k]
        # Если после фильтрации осталось меньше документов чем top_k или они все отфильтровались
        elif filtered_results:
            result = filtered_results
        # Если все документы отфильтровались, берем первые top_k
        else:
            result = top_results
    else:
        # Если документов меньше чем top_k, берем все, но фильтруем по порогу
        result = [item for item in sorted_items if item['similarity'] >= threshold]
        
        # Если все отфильтровались, берем все доступные
        if not result and sorted_items:
            result = sorted_items
    
    # Если всё ещё нет результатов и есть отсортированные элементы, берем первый
    if not result and sorted_items:
        logger.warning("Не найдено релевантных элементов, используем первый элемент из выборки")
        logger.debug(f"Максимальное сходство: {sorted_items[0]['similarity']}, порог: {threshold}")
        
        # Уменьшаем пороговое значение для этого запроса
        if DEBUG['enabled']:
            print(f"\nВНИМАНИЕ! Пороговое значение ({threshold}) слишком высокое.")
            print(f"Максимальное найденное сходство: {sorted_items[0]['similarity']:.4f}")
            print("Рекомендуется снизить пороговое значение в config.py (RAG_SETTINGS['similarity_threshold'])")
            
            # Используем все найденные элементы в пределах top_k
            result = sorted_items[:top_k]
    
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
    
    # В конце функции проверяем, что возвращаем правильное количество элементов
    logger.debug(f"Возвращаем {len(result)} релевантных элементов из {len(sorted_items)} доступных")
    
    return result 