from openai_api_models import client as openai_client

from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from rank_bm25 import BM25Okapi
# from db import get_items_sample # Закомментировано, т.к. функция get_items_sample не используется в текущей реализации
from embeddings import get_embedding, calculate_similarity # create_embedding_for_item - не используется здесь
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
    # Расширенная логика для вложенных структур, если 'item' содержит основной контент
    if 'item' in item:
        inner_item = item['item']
        if isinstance(inner_item, dict) and 'text' in inner_item and inner_item['text']:
            return inner_item['text']
        # Пример для формата списка: [id, embedding_vector, text, ...]
        if isinstance(inner_item, list) and len(inner_item) > 2 and isinstance(inner_item[2], str) and inner_item[2]:
             return inner_item[2]
    # Дополнительная проверка, если сам item содержит нужные поля (для случая без вложенности 'item')
    if 'id' in item and 'embedding' in item and 'text' in item and item['text']:
         return item['text']

    logger.debug(f"Could not extract text from item structure: {item.keys()}")
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
    min_score: float = 0.0, # min_score пока не используется в логике ниже, но оставлен для совместимости
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    Реранжирует результаты поиска с использованием кросс-энкодера BGE.
    Поддерживает несколько форматов входных данных и включает расширенное логирование.

    Args:
        query: Поисковый запрос (непустая строка)
        items: Список элементов для реранжирования. Ожидается, что каждый элемент - словарь,
               из которого можно извлечь текст с помощью extract_text.
        model_name: Название модели (по умолчанию 'bge-reranker-base')
        top_k: Количество возвращаемых результатов (None = из SEARCH_SETTINGS)
        min_score: Минимальный score для включения в результаты (пока не используется)
        max_retries: Максимальное количество попыток при ошибках модели

    Returns:
        Список реранжированных элементов (исходные словари item),
        отсортированных по убыванию оценки реранжирования.
        Каждый возвращаемый элемент - это *оригинальный* словарь item из входного списка,
        дополненный полем 'rerank_score'.

    Raises:
        ValueError: При невалидных входных параметрах
        RuntimeError: При ошибках модели после max_retries попыток
    """
    global _reranker_cache

    # Расширенная валидация входных параметров
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string")

    if not isinstance(items, list):
        # Попытка исправить, если передан один словарь
        if isinstance(items, dict):
             items = [items]
        else:
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
                # use_fp16=True может ускорить, но требует совместимого GPU
                _reranker_cache = FlagReranker(model_name, use_fp16=False) # Изменено на False для большей совместимости
                logger.info(f"Reranker model {model_name} initialized successfully (attempt {attempt + 1})")
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Failed to initialize reranker after {max_retries} attempts: {str(e)}")
                    raise RuntimeError(f"Failed to initialize reranker after {max_retries} attempts") from e
                logger.warning(f"Retrying model initialization (attempt {attempt + 1}): {str(e)}")

    # Подготавливаем пары запрос-текст для реранжирования с детальным логированием
    pairs = []
    valid_items_map = {} # Используем map для связи индекса пары с исходным item
    invalid_items_count = 0

    for idx, item in enumerate(items):
        try:
            if not isinstance(item, dict):
                logger.warning(f"Item at index {idx} is not a dictionary (type: {type(item)}), skipping")
                invalid_items_count += 1
                continue

            text = extract_text(item)
            if text is None:
                logger.warning(f"Could not extract text from item at index {idx}, id: {item.get('id', 'unknown')}")
                invalid_items_count += 1
                continue

            if not isinstance(text, str) or not text.strip():
                logger.warning(f"Invalid or empty text in item at index {idx}, id: {item.get('id', 'unknown')}")
                invalid_items_count += 1
                continue

            pairs.append([query, text]) # Модель ожидает список списков
            valid_items_map[len(pairs) - 1] = item # Сохраняем исходный item по индексу пары

        except Exception as e:
            logger.error(f"Error processing item at index {idx}: {str(e)}", exc_info=DEBUG)
            invalid_items_count += 1

    logger.info(f"Prepared {len(pairs)} valid pairs for reranking ({invalid_items_count} invalid items skipped)")

    if not pairs:
        logger.warning("No valid pairs for reranking, returning empty list")
        return []

    try:
        # Получаем оценки реранжирования
        logger.debug(f"Computing rerank scores for {len(pairs)} pairs...")
        # Модель FlagReranker.compute_score ожидает list of pairs: [[query, doc1], [query, doc2]...]
        rerank_scores = _reranker_cache.compute_score(pairs, batch_size=SEARCH_SETTINGS.get('reranker_batch_size', 64))
        logger.debug(f"Got {len(rerank_scores)} rerank scores")

        # Добавляем оценки к исходным элементам
        reranked_items_with_scores = []
        for i, score in enumerate(rerank_scores):
             if i in valid_items_map:
                 original_item = valid_items_map[i]
                 # Добавляем score к *копии* словаря, чтобы не изменять исходные объекты напрямую
                 item_copy = original_item.copy()
                 item_copy['rerank_score'] = float(score)
                 reranked_items_with_scores.append(item_copy)
                 logger.debug(f"Item index {i} (id: {original_item.get('id', 'N/A')}): score={item_copy['rerank_score']:.4f}")
             else:
                 logger.warning(f"Mismatch: score index {i} not found in valid_items_map")


        # Сортируем по убыванию оценки реранжирования
        sorted_items = sorted(reranked_items_with_scores, key=lambda x: x['rerank_score'], reverse=True)
        logger.info(f"Reranking completed, top score: {sorted_items[0]['rerank_score'] if sorted_items else 'N/A'}")

        # Возвращаем только top_k результатов
        return sorted_items[:top_k]

    except Exception as e:
        logger.error(f"Reranking failed: {str(e)}", exc_info=DEBUG)
        # В случае ошибки реранкера, можно вернуть пустой список или исходные items

@timeit
def rerank_items(
    query: str,
    items: List[Dict[str, Any]],
    provider: str = 'openai', # Добавляем выбор провайдера
    model_name: str = "rerank-english-3", # Модель по умолчанию для OpenAI
    top_k: int = None,
    min_score: float = 0.0,
    max_retries: int = 3 # Оставляем для совместимости, но может не использоваться всеми провайдерами
) -> List[Dict[str, Any]]:
    """
    Реранжирует результаты поиска с использованием выбранного провайдера (OpenAI, заглушки).

    Args:
        query: Поисковый запрос (непустая строка)
        items: Список элементов для реранжирования. Ожидается, что каждый элемент - словарь,
               из которого можно извлечь текст с помощью extract_text.
        provider: Провайдер реранжирования ('openai', 'google', 'deepseek', 'openrouter').
        model_name: Название модели для выбранного провайдера.
        top_k: Количество возвращаемых результатов (None = из SEARCH_SETTINGS).
        min_score: Минимальный score для включения в результаты (может не поддерживаться всеми провайдерами).
        max_retries: Максимальное количество попыток при ошибках.

    Returns:
        Список реранжированных элементов (исходные словари item),
        отсортированных по убыванию оценки реранжирования.
        Каждый возвращаемый элемент - это *оригинальный* словарь item из входного списка,
        дополненный полем 'rerank_score'.

    Raises:
        ValueError: При невалидных входных параметрах или неподдерживаемом провайдере.
        RuntimeError: При ошибках реранжирования после max_retries попыток.
        NotImplementedError: Для провайдеров с заглушками.
    """
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Query must be a non-empty string")

    if not isinstance(items, list):
        if isinstance(items, dict):
             items = [items]
        else:
             raise ValueError("Items must be a list of dictionaries")

    if len(items) == 0:
        logger.warning("Received empty items list for reranking")
        return []

    if top_k is None:
        top_k = SEARCH_SETTINGS.get('top_k', 10)
    elif not isinstance(top_k, int) or top_k <= 0:
        raise ValueError("top_k must be a positive integer")

