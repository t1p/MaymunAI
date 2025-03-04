import logging
from typing import List
from openai_api_models import client
from config import KEYWORDS_SETTINGS

logger = logging.getLogger(__name__)

def generate_keywords_for_query(query: str) -> List[str]:
    """
    Использует модель GPT для генерации ключевых слов для запроса
    
    Args:
        query: Текст запроса пользователя
        
    Returns:
        Список ключевых слов
    """
    logger.debug(f"Генерация ключевых слов для запроса: {query}")
    
    try:
        # Формируем промпт
        prompt = KEYWORDS_SETTINGS['prompt'].format(query=query)
        
        # Отправляем запрос к API
        response = client.chat.completions.create(
            model=KEYWORDS_SETTINGS['model'],
            messages=[
                {"role": "system", "content": "Ты - помощник по подбору ключевых слов для поиска."},
                {"role": "user", "content": prompt}
            ],
            temperature=KEYWORDS_SETTINGS['temperature'],
            max_tokens=KEYWORDS_SETTINGS['max_tokens']
        )
        
        # Извлекаем ответ
        keywords_text = response.choices[0].message.content.strip()
        logger.debug(f"Получены ключевые слова: {keywords_text}")
        
        # Преобразуем в список
        keywords = [k.strip() for k in keywords_text.split(',') if k.strip()]
        
        return keywords
    except Exception as e:
        logger.error(f"Ошибка при генерации ключевых слов: {str(e)}")
        # Возвращаем базовые ключевые слова в случае ошибки
        return [query.split()[0]] if query.split() else ["информация"] 