from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from rank_bm25 import BM25Okapi
from db import get_items_sample
from embeddings import get_embedding, calculate_similarity, create_embedding_for_item
from config import SEARCH_SETTINGS, RAG_SETTINGS, DEBUG
from debug_utils import debug_step
import logging
from utils import timeit
from config_db import get_threshold
from FlagEmbedding import FlagReranker

logger = logging.getLogger(__name__)

# Кэш для модели реранжировщика
_reranker_cache = None

@timeit
def rerank_with_cross_encoder(
    query: str,
    items: List[Dict[str, Any]],
    model_name: str = "bge-reranker-base",
    top_k: int = None
) -> List[Dict[str, Any]]:
    """
    Реранжирует результаты поиска с использованием кросс-энкодера BGE.
    
    Args:
        query: Поисковый запрос
        items: Список элементов для реранжирования (должны содержать 'text')
        model_name: Название модели (по умолчанию 'bge-reranker-base')
        top_k: Количество возвращаемых результатов
    
    Returns:
        Список реранжированных элементов с дополнительным полем 'rerank_score'
    """
    global _reranker_cache
    
    if top_k is None:
        top_k = SEARCH_SETTINGS['top_k']
    
    # Инициализация модели с кэшированием
    if _reranker_cache is None:
        _reranker_cache = FlagReranker(model_name, use_fp16=True)
    
    # Подготавливаем пары запрос-текст для реранжирования
    pairs = [(query, item['text']) for item in items]
    
    # Получаем оценки реранжирования
    rerank_scores = _reranker_cache.compute_score(pairs)
    
    # Добавляем оценки к элементам
    for i, item in enumerate(items):
        item['rerank_score'] = float(rerank_scores[i])
    
    # Сортируем по убыванию оценки реранжирования
    sorted_items = sorted(items, key=lambda x: x['rerank_score'], reverse=True)
    
    return sorted_items[:top_k]

@timeit
def bm25_search(query: str, items: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
    """
    Выполняет поиск по BM25 и возвращает отсортированные результаты
    """
    if top_k is None:
        top_k = SEARCH_SETTINGS['top_k']
        
    # Получаем тексты документов для индексирования
    texts = [item['text'] for item in items]
    
    # Токенизация (простая реализация - можно улучшить)
    tokenized_texts = [text.lower().split() for text in texts]
    tokenized_query = query.lower().split()
    
    # Создаем индекс BM25
    bm25 = BM25Okapi(tokenized_texts)
    
    # Получаем оценки для запроса
    scores = bm25.get_scores(tokenized_query)
    
    # Собираем результаты с оценками
    results = []
    for i, item in enumerate(items):
        results.append({
            'item': item,
            'score': scores[i],
            'text': texts[i]
        })
    
    # Сортируем по убыванию оценки
    sorted_results = sorted(results, key=lambda x: x['score'], reverse=True)
    
    return sorted_results[:top_k]

@timeit
def search_similar_items(
    query: str,
    items: List[Dict[str, Any]],
    top_k: int = None,
    vector_weight: float = 0.6,
    bm25_weight: float = 0.2,
    rerank_weight: float = 0.2,
    use_hybrid: bool = True,
    use_reranker: bool = False
) -> List[Dict[str, Any]]:
    """
    Ищет наиболее релевантные элементы для заданного запроса.
    Поддерживает гибридный поиск (векторный + BM25) или только векторный.
    
    Args:
        query: Поисковый запрос
        items: Список элементов для поиска
        top_k: Количество возвращаемых результатов
        vector_weight: Вес векторного поиска (по умолчанию 0.7)
        bm25_weight: Вес BM25 поиска (по умолчанию 0.3)
        use_hybrid: Использовать гибридный поиск (True) или только векторный (False)
    
    Returns:
        Список релевантных элементов с дополнительными полями:
        - similarity: оценка сходства (векторный поиск)
        - score: оценка BM25
        - combined_score: взвешенная сумма оценок (если use_hybrid=True)
    """
    if top_k is None:
        top_k = SEARCH_SETTINGS['top_k']
        
    logger.debug(f"Поиск похожих элементов для запроса: {query}, top_k: {top_k}")
    
    # Получаем параметры из конфигурации, если не переданы явно
    if use_hybrid:
        if 'hybrid_search_weights' in SEARCH_SETTINGS:
            vector_weight = SEARCH_SETTINGS['hybrid_search_weights'].get('vector', vector_weight)
            bm25_weight = SEARCH_SETTINGS['hybrid_search_weights'].get('bm25', bm25_weight)
        
        # Нормализуем веса
        total_weight = vector_weight + bm25_weight
        vector_weight /= total_weight
        bm25_weight /= total_weight
    
    # 1. Выполняем векторный поиск
    query_embedding = get_embedding(query)
    
    # 2. Выполняем BM25 поиск, если используется гибридный режим
    bm25_results = []
    if use_hybrid:
        bm25_results = bm25_search(query, items, top_k)
        # Создаем словарь для быстрого доступа к оценкам BM25
        bm25_scores = {res['item']['id']: res['score'] for res in bm25_results if 'id' in res['item']}
    
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
            result_item = {
                'item': item,
                'embedding': embedding_data['embedding'],
                'text': embedding_data['text'],
                'similarity': similarity
            }
            
            # Добавляем оценку BM25 если используется гибридный поиск
            if use_hybrid and 'id' in item and item['id'] in bm25_scores:
                result_item['bm25_score'] = bm25_scores[item['id']]
                # Вычисляем комбинированную оценку
                result_item['combined_score'] = (
                    vector_weight * similarity +
                    bm25_weight * result_item['bm25_score']
                )
            else:
                result_item['combined_score'] = similarity
                
            similarities.append(result_item)
        except Exception as e:
            logger.warning(f"Ошибка при обработке элемента: {str(e)}")
    
    # Сортируем по убыванию релевантности
    sort_key = 'combined_score' if use_hybrid else 'similarity'
    sorted_items = sorted(similarities, key=lambda x: x[sort_key], reverse=True)
    
    logger.debug(f"Используемый метод поиска: {'гибридный (векторный + BM25)' if use_hybrid else 'векторный'}")
    
    # Применяем реранжирование, если включено
    if use_reranker:
        # Получаем веса из конфигурации, если не переданы явно
        if 'hybrid_search_weights' in SEARCH_SETTINGS:
            rerank_weight = SEARCH_SETTINGS['hybrid_search_weights'].get('rerank', rerank_weight)
        
        # Нормализуем веса
        total_weight = vector_weight + bm25_weight + rerank_weight
        vector_weight /= total_weight
        bm25_weight /= total_weight
        rerank_weight /= total_weight
        
        # Реранжируем top_k*2 элементов, чтобы было больше контекста для реранжирования
        items_to_rerank = sorted_items[:top_k*2] if len(sorted_items) > top_k*2 else sorted_items
        reranked_items = rerank_with_cross_encoder(query, items_to_rerank, top_k=top_k*2)
        
        # Создаем словарь для быстрого доступа к оценкам реранжирования
        rerank_scores = {item['item']['id']: item['rerank_score']
                        for item in reranked_items if 'id' in item['item']}
        
        # Обновляем combined_score с учетом реранжирования
        for item in sorted_items:
            if 'id' in item['item'] and item['item']['id'] in rerank_scores:
                item['combined_score'] = (
                    vector_weight * item['similarity'] +
                    bm25_weight * item.get('bm25_score', 0) +
                    rerank_weight * rerank_scores[item['item']['id']]
                )
        
        # Пересортируем с учетом новых оценок
        sorted_items = sorted(sorted_items, key=lambda x: x['combined_score'], reverse=True)
        
        logger.debug(f"Добавлено реранжирование с весом {rerank_weight:.2f}")
    
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