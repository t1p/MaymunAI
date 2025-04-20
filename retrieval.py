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

def validate_item(item: Dict[str, Any]) -> bool:
    """
    Проверяет валидность элемента для поиска.
    
    Args:
        item: Элемент для проверки
        
    Returns:
        True если элемент валиден, иначе False
    """
    if not isinstance(item, dict):
        return False
    if 'id' not in item:
        return False
    if 'text' not in item or not isinstance(item['text'], str) or not item['text'].strip():
        return False
    return True

def extract_text(item: Dict[str, Any]) -> Optional[str]:
    """
    Извлекает текст из элемента, поддерживая несколько форматов.
    Возвращает None если текст не найден.
    
    Args:
        item: Элемент данных
        
    Returns:
        Текст элемента или None если не найден
    """
    if 'text' in item and item['text']:
        return item['text']
    if 'item' in item:
        if isinstance(item['item'], dict) and 'text' in item['item']:
            return item['item']['text']
        if isinstance(item['item'], list) and len(item['item']) > 2:
            return item['item'][2]
    return None

logger = logging.getLogger(__name__)

# Кэш для модели реранжировщика
_reranker_cache = None

@timeit
def rerank_with_cross_encoder(
    query: str,
    items: List[Dict[str, Any]],
    model_name: str = "bge-reranker-base",
    top_k: int = None,
    min_score: float = 0.0,
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    Реранжирует результаты поиска с использованием кросс-энкодера BGE.
    Поддерживает несколько форматов входных данных и включает расширенное логирование.
    
    Args:
        query: Поисковый запрос (непустая строка)
        items: Список элементов для реранжирования (поддерживаются форматы:
               - {'text': str, ...}
               - {'item': {'text': str, ...}, ...}
               - {'item': [id, _, text], ...})
        model_name: Название модели (по умолчанию 'bge-reranker-base')
        top_k: Количество возвращаемых результатов (None = из SEARCH_SETTINGS)
        min_score: Минимальный score для включения в результаты
        max_retries: Максимальное количество попыток при ошибках модели
    
    Returns:
        Список реранжированных элементов с полями:
        - rerank_score: оценка реранжирования
        - original_item: ссылка на исходный элемент
        - text: использованный текст
    
    Raises:
        ValueError: При невалидных входных параметрах
        RuntimeError: При ошибках модели после max_retries попыток
    """
    global _reranker_cache
    
    # Расширенная валидация входных параметров
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string")
    
    if not isinstance(items, list):
        raise ValueError("Items must be a list of dictionaries")
    
    if len(items) == 0:
        logger.warning("Received empty items list for reranking")
        return []
    
    # Валидация top_k
    if top_k is None:
        top_k = SEARCH_SETTINGS.get('top_k', 10)
    elif not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")
    
    # Валидация min_score
    if not isinstance(min_score, (int, float)) or min_score < 0:
        raise ValueError("min_score must be a non-negative number")
    
    # Валидация max_retries
    if not isinstance(max_retries, int) or max_retries < 1:
        raise ValueError("max_retries must be a positive integer")
    
    logger.info(f"Starting reranking for query: '{query[:50]}...' with {len(items)} items")
    logger.debug(f"Parameters: top_k={top_k}, min_score={min_score}, model={model_name}")
    
    # Инициализация модели с кэшированием и повторными попытками
    if _reranker_cache is None:
        logger.debug(f"Initializing reranker model: {model_name}")
        for attempt in range(max_retries):
            try:
                _reranker_cache = FlagReranker(model_name, use_fp16=True)
                logger.info(f"Reranker model {model_name} initialized successfully (attempt {attempt + 1})")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to initialize reranker after {max_retries} attempts: {str(e)}")
                    raise RuntimeError(f"Failed to initialize reranker after {max_retries} attempts") from e
                logger.warning(f"Retrying model initialization (attempt {attempt + 1}): {str(e)}")
    
    # Подготавливаем пары запрос-текст для реранжирования с детальным логированием
    pairs = []
    valid_items = []
    invalid_items = 0
    format_stats = {'dict': 0, 'list': 0, 'invalid': 0}
    
    for idx, item in enumerate(items):
        try:
            if not isinstance(item, dict):
                logger.warning(f"Item at index {idx} is not a dictionary (type: {type(item)}), skipping")
                invalid_items += 1
                format_stats['invalid'] += 1
                continue
                
            # Поддержка разных форматов элементов с логированием
            text = extract_text(item)
            if text is None:
                logger.warning(f"Could not extract text from item at index {idx}, id: {item.get('id', 'unknown')}")
                logger.debug(f"Item structure: {list(item.keys())}")
                invalid_items += 1
                format_stats['invalid'] += 1
                continue
                
            if not isinstance(text, str) or not text.strip():
                logger.warning(f"Invalid text in item at index {idx}, id: {item.get('id', 'unknown')}")
                invalid_items += 1
                format_stats['invalid'] += 1
                continue
                
            # Определяем формат элемента
            if isinstance(item.get('item', None), dict):
                format_stats['dict'] += 1
            elif isinstance(item.get('item', None), list):
                format_stats['list'] += 1
            else:
                format_stats['invalid'] += 1
                
            pairs.append((query, text))
            valid_items.append(item)
            
        except Exception as e:
            logger.error(f"Error processing item at index {idx}: {str(e)}", exc_info=True)
            invalid_items += 1
            format_stats['invalid'] += 1
    
    logger.info(f"Prepared {len(pairs)} valid pairs for reranking ({invalid_items} invalid items skipped)")
    logger.debug(f"Item formats: {format_stats}")
    
    if not pairs:
        logger.warning("No valid pairs for reranking, returning empty list")
        return []
    
    try:
        # Получаем оценки реранжирования
        logger.debug("Computing rerank scores...")
        rerank_scores = _reranker_cache.compute_score(pairs)
        logger.debug(f"Got {len(rerank_scores)} rerank scores")
        
        # Добавляем оценки только к валидных элементов
        for i, item in enumerate(valid_items):
            item['rerank_score'] = float(rerank_scores[i])
            logger.debug(f"Item {i}: score={item['rerank_score']:.4f}")
        
        # Сортируем по убываиююоценки реранжирования
        sorted_items = sorted(valid_items, key=lambda x: x['rerank_score'], reverse=True)
        logger.info(f"Reranking completed, top score: {sorted_items[0]['rerank_score'] if sorted_items else 'N/A'}")
        
        return sorted_items[:top_k]
        
    except Exception as e:
        logger.error(f"Reranking failed: {str(e)}")
        raise

@timeit
def bm25_search(query: str, items: List[Dict[str, Any]], top_k: int = None) -> List[Dict[str, Any]]:
    """
    Выполняет поиск по BM25 и возвращает отсортированные результаты
    """
    if top_k is None:
        top_k = SEARCH_SETTINGS['top_k']
        
    # Получаем тексты документов для индексирования (поддерживаем оба формата)
    texts = []
    for item in items:
        text = extract_text(item)
        if text is None:
            logger.warning(f"Не удалось извлечь текст для элемента: {item.get('id', 'unknown')}")
            text = ''  # fallback
        texts.append(text)
    
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
            '