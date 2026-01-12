# config.py
from settings import DB_CONFIG, OPENAI_API_KEY
from typing import Optional, Dict, Any

# Модели OpenAI
MODELS = {
    'embedding': {
        'name': "text-embedding-3-large",  # или "text-embedding-ada-002"
        'dimensions': 3072,  # 1536 для ada-002
        'max_tokens': 8191,  # Максимальное количество токенов для эмбеддинга
        'version': '1.0'  # Добавлено поле версии
    },
    'generation': {
        'name': "gpt-4o-latest",  # или "gpt-4"
        'max_tokens': 4096,  # Максимальное количество токенов для ответа
        'version': '1.0'  # Добавлено поле версии
    }
}

# Режим отладки
DEBUG = {
    'enabled': False,  # Глобальное включение/отключение режима отладки
    'interactive': True,  # Включить интерактивный режим с запросами пользователю
    'show_embeddings': True,  # Показывать эмбеддинги
    'show_similarity': True,  # Показывать значения сходства
    'show_context': True,  # Показывать собранный контекст
    'show_prompt': True,  # Показывать финальный промпт
    'truncate_output': 1000,  # Ограничение длины выводимого текста
}

# Корневые узлы для поиска
ROOT_MARKERS = [
    'Knowledge Universe TIP',
    'База знаний',
]

# Настройки RAG
RAG_SETTINGS = {
    'temperature': 0.3,  # Креативность ответов (0.0 - строго, 1.0 - креативно)
    'max_tokens': 2048,  # Максимальная длина ответа
    'similarity_threshold': 0.4,  # Минимальный порог сходства для релевантных документов
    'context_window': 0,  # Количество родительских/дочерних элементов для контекста
    'chunk_size': 1000,  # Размер чанка для разбиения длинных текстов
    'chunk_overlap': 100,  # Перекрытие между чанками
    'keywords_prompt': """Выдели из запроса пользователя 3-5 ключевых слов или фраз для поиска информации.
Ответ должен содержать только список ключевых слов через запятую без пояснений.
Запрос пользователя: {query}"""
}

# Настройки поиска
SEARCH_SETTINGS = {
    'sample_size': 10,  # Размер выборки документов для поиска 
    'top_k': 5,  # Количество возвращаемых документов
    'max_depth': 0,  # Максимальная глубина поиска в иерархии
    'similarity_threshold': 0.3,  # Порог сходства (документы с меньшим сходством игнорируются)
}

# Настройки для интерактивного режима
INTERACTIVE_SETTINGS = {
    'stages': {
        'embeddings': {
            'params': ['model'],
            'description': 'Генерация эмбеддингов',
            'model_key': 'embedding',  # Ссылка на конфигурацию модели
        },
        'retrieval': {
            'params': ['similarity_threshold', 'max_depth', 'top_k'],
            'description': 'Поиск релевантных документов',
        },
        'context': {
            'params': ['context_window', 'chunk_size', 'chunk_overlap'],
            'description': 'Агрегация контекста',
        },
        'generation': {
            'params': ['temperature', 'max_tokens', 'model'],
            'description': 'Генерация ответа',
            'model_key': 'generation',  # Ссылка на конфигурацию модели
        }
    },
    'param_descriptions': {
        'model': 'Модель для генерации',
        'similarity_threshold': 'Порог сходства (0.0 - 1.0)',
        'max_depth': 'Максимальная глубина поиска',
        'top_k': 'Количество возвращаемых документов',
        'context_window': 'Размер окна контекста',
        'chunk_size': 'Размер чанка текста',
        'chunk_overlap': 'Перекрытие между чанками',
        'temperature': 'Температура генерации (0.0 - 1.0)',
        'max_tokens': 'Максимальное количество токенов'
    }
}

# Настройки для автоматического подбора ключевых слов
KEYWORDS_SETTINGS = {
    'prompt': "Подбери пять ключевых слов, по которым лучше всего можно найти ответ в тексте, на этот запрос. В ответе перечисли их через запятую. Текст запроса: {query}",
    'model': 'gpt-4o-mini',
    'temperature': 0.3,
    'max_tokens': 100
}

def get_embedding_from_db(item_id: str, model: str) -> Optional[Dict[str, Any]]:
    # После получения эмбеддинга из БД, добавить проверку размерности
    if embedding and len(embedding) != MODELS['embedding']['dimensions']:
        logger.warning(f"Кэшированный эмбеддинг имеет неправильную размерность: {len(embedding)} вместо {MODELS['embedding']['dimensions']}")
        return None  # Возвращаем None, чтобы создать новый эмбеддинг