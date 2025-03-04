import logging
import json
import os
from embeddings import get_embedding, save_query_embedding_to_cache
from config import MODELS

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Путь к файлу с частыми запросами
FREQUENT_QUERIES_FILE = 'data/frequent_queries.json'

def load_frequent_queries():
    """Загружает список частых запросов из файла"""
    if not os.path.exists(FREQUENT_QUERIES_FILE):
        logger.warning(f"Файл с частыми запросами не найден: {FREQUENT_QUERIES_FILE}")
        # Создаем заглушку с базовыми запросами
        return [
            "Как работает система?",
            "Что такое RAG?",
            "Как использовать эмбеддинги?",
            "Что такое векторное представление текста?",
            "Как улучшить релевантность поиска?"
        ]
    
    try:
        with open(FREQUENT_QUERIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Ошибка при загрузке частых запросов: {str(e)}")
        return []

def preload_query_embeddings():
    """Предзагружает эмбеддинги для частых запросов"""
    queries = load_frequent_queries()
    logger.info(f"Загружено {len(queries)} частых запросов")
    
    model = MODELS['embedding']['name']
    count = 0
    
    for query in queries:
        try:
            # Получаем эмбеддинг
            embedding = get_embedding(query, model)
            
            # Сохраняем в кэш
            if save_query_embedding_to_cache(query, embedding, model):
                count += 1
                logger.info(f"Кэширован запрос: '{query[:50]}...' если длинный")
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса '{query}': {str(e)}")
    
    logger.info(f"Успешно кэшировано {count} из {len(queries)} запросов")

if __name__ == '__main__':
    logger.info("Запуск предзагрузки эмбеддингов частых запросов")
    preload_query_embeddings() 