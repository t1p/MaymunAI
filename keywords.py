import logging
from typing import List
from openai_api_models import client
from config import KEYWORDS_SETTINGS, MODELS, RAG_SETTINGS

logger = logging.getLogger(__name__)

def generate_keywords_for_query(query: str, max_keywords: int = 5) -> list:
    """
    Генерирует ключевые слова для запроса с помощью GPT модели
    
    Args:
        query: Запрос пользователя
        max_keywords: Максимальное количество ключевых слов
        
    Returns:
        Список ключевых слов/фраз
    """
    logger.debug(f"Генерация ключевых слов для запроса: {query}")
    
    prompt = RAG_SETTINGS.get('keywords_prompt', 
        "Выдели из запроса пользователя 3-5 ключевых слов или фраз для поиска информации. " + 
        "Ответ должен содержать только список ключевых слов через запятую без пояснений. " +
        "Запрос пользователя: {query}")
    
    # Подставляем запрос в шаблон промпта
    formatted_prompt = prompt.format(query=query)
    
    try:
        response = client.chat.completions.create(
            model=MODELS['generation']['name'],
            messages=[
                {"role": "system", "content": "Ты помогаешь выделять ключевые слова из запросов пользователей."},
                {"role": "user", "content": formatted_prompt}
            ],
            temperature=0.3,
            max_tokens=100
        )
        
        # Получаем ответ модели
        keywords_text = response.choices[0].message.content.strip()
        
        # Разбиваем строку на отдельные ключевые слова
        keywords = [kw.strip() for kw in keywords_text.split(',') if kw.strip()]
        
        # Ограничиваем количество
        keywords = keywords[:max_keywords]
        
        logger.debug(f"Сгенерированы ключевые слова: {keywords}")
        return keywords
    
    except Exception as e:
        logger.error(f"Ошибка при генерации ключевых слов: {str(e)}")
        # Возвращаем базовые ключевые слова из запроса в случае ошибки
        fallback_keywords = [word.strip() for word in query.split()[:3] if len(word) > 3]
        return fallback_keywords 