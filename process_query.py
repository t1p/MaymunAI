from typing import List, Dict, Any
import logging
from config import SEARCH_SETTINGS, RAG_SETTINGS, DEBUG
from db import get_items_sample
from embeddings import get_embedding, calculate_similarity, create_embedding_for_item
from debug_utils import debug_step

def process_query_with_keywords(query: str, keywords: List[str], top_k: int = None, root_id: str = None, parent_context: int = 0, child_context: int = 0) -> str:
    """
    Обрабатывает пользовательский запрос с использованием ключевых слов для поиска контекста
    """
    logger = logging.getLogger('process_query')
    
    # Используем значения из настроек, если не указаны явно
    if top_k is None:
        top_k = SEARCH_SETTINGS['top_k']
    
    try:
        # Получаем выборку элементов на основе ключевых слов
        logger.debug(f"Поиск элементов по ключевым словам: {keywords}")
        ensure_text_search_index()  # Создаем индекс, если его нет
        items = search_by_keywords(keywords, SEARCH_SETTINGS['sample_size'], root_id)
        logger.debug(f"Найдено {len(items)} элементов по ключевым словам")
        
        # Если по ключевым словам ничего не найдено, используем стандартную выборку
        if not items:
            logger.debug(f"По ключевым словам ничего не найдено, используем стандартную выборку")
            items = get_items_sample(1, SEARCH_SETTINGS['sample_size'], root_id=root_id)
            
        # Обогащаем каждый элемент контекстом в соответствии с параметрами
        items_with_context = []
        for item in items:
            item_with_context = get_item_with_context(
                item[0], 
                parent_depth=parent_context,
                child_depth=child_context
            )
            if item_with_context:
                items_with_context.append(item_with_context)
        
        # Ищем релевантные элементы
        logger.debug(f"Ищем {top_k} релевантных элементов")
        relevant_items = search_similar_items(query, items_with_context, top_k)
        logger.debug(f"Найдено {len(relevant_items)} релевантных элементов")
        
        # В режиме отладки показываем найденные элементы
        if DEBUG['enabled']:
            print("\nНайденные релевантные элементы:")
            for i, item in enumerate(relevant_items, 1):
                print(f"\n--- Элемент {i} (сходство: {item['similarity']:.4f}) ---")
                print(item['text'][:200] + "..." if len(item['text']) > 200 else item['text'])
        
        # Генерируем ответ
        logger.debug("Генерируем ответ")
        answer = generate_answer(query, relevant_items)
        logger.debug("Ответ получен")
        
        return answer
    except Exception as e:
        logger.error(f"Ошибка в process_query_with_keywords: {str(e)}", exc_info=True)
        return f"Произошла ошибка при обработке запроса: {str(e)}"

def process_query(query: str, keywords: List[str] = None, context: List[Dict[str, Any]] = None, 
                 strategy: str = None) -> Dict[str, Any]:
    """
    Обрабатывает запрос пользователя
    
    Args:
        query: Запрос пользователя
        keywords: Ключевые слова для поиска контекста
        context: Дополнительный контекст
        strategy: Стратегия обработки
        
    Returns:
        Dict: Результат обработки запроса
    """
    try:
        # Если не указаны ключевые слова, используем запрос как основу для поиска
        if not keywords:
            logger.debug("Ключевые слова не указаны, используем запрос")
            keywords = query.lower().split()
        
        # Поиск элементов по ключевым словам
        logger.debug(f"Поиск элементов по ключевым словам: {keywords}")
        items = search_by_keywords(keywords)
        logger.debug(f"Найдено {len(items)} элементов по ключевым словам")

        # ДОБАВИТЬ КОД ЗДЕСЬ - выводим список найденных элементов
        if items:
            print("\n==================== Найденные элементы по ключевым словам ====================\n")
            for idx, item in enumerate(items, 1):
                # Извлекаем текст элемента - структура может отличаться в зависимости от вашей реализации
                item_text = item.get('text', '')
                if not item_text and 'item' in item:
                    if isinstance(item['item'], list) and len(item['item']) > 1:
                        item_text = item['item'][1]  # Обычно текст во втором элементе списка
                    elif isinstance(item['item'], dict) and 'text' in item['item']:
                        item_text = item['item']['text']
                
                # Получаем ID элемента
                item_id = None
                if 'item_id' in item:
                    item_id = item['item_id']
                elif 'item' in item and isinstance(item['item'], list) and len(item['item']) > 0:
                    item_id = item['item'][0]
                
                # Выводим информацию о элементе
                print(f"Элемент {idx} (ID: {item_id}):")
                print(f"Текст: {item_text[:150]}..." if len(str(item_text)) > 150 else f"Текст: {item_text}")
                print()
        
        # Если по ключевым словам ничего не найдено, используем стандартную выборку
        if not items:
            logger.debug(f"По ключевым словам ничего не найдено, используем стандартную выборку")
            items = get_items_sample(1, SEARCH_SETTINGS['sample_size'], root_id=root_id)
            
        # Обогащаем каждый элемент контекстом в соответствии с параметрами
        items_with_context = []
        for item in items:
            item_with_context = get_item_with_context(
                item[0], 
                parent_depth=parent_context,
                child_depth=child_context
            )
            if item_with_context:
                items_with_context.append(item_with_context)
        
        # Ищем релевантные элементы
        logger.debug(f"Ищем {top_k} релевантных элементов")
        relevant_items = search_similar_items(query, items_with_context, top_k)
        logger.debug(f"Найдено {len(relevant_items)} релевантных элементов")
        
        # В режиме отладки показываем найденные элементы
        if DEBUG['enabled']:
            print("\nНайденные релевантные элементы:")
            for i, item in enumerate(relevant_items, 1):
                print(f"\n--- Элемент {i} (сходство: {item['similarity']:.4f}) ---")
                print(item['text'][:200] + "..." if len(item['text']) > 200 else item['text'])
        
        # Генерируем ответ
        logger.debug("Генерируем ответ")
        answer = generate_answer(query, relevant_items)
        logger.debug("Ответ получен")
        
        return answer
    except Exception as e:
        logger.error(f"Ошибка в process_query: {str(e)}", exc_info=True)
        return f"Произошла ошибка при обработке запроса: {str(e)}" 