#4566b621-926d-4405-82a1-f76728e8d93f
from openai import OpenAI
from config import OPENAI_API_KEY, MODELS
import logging

logger = logging.getLogger(__name__)

# Создаем клиент с увеличенным таймаутом
client = OpenAI(
    api_key=OPENAI_API_KEY,
    timeout=60.0  # Увеличиваем таймаут до 60 секунд
)

def list_models():
    """Получает список доступных моделей"""
    try:
        models = client.models.list()
        print("\nДоступные модели:")
        for model in models:
            print(f"- {model.id}")
        return [model.id for model in models]
    except Exception as e:
        logger.error(f"Ошибка при получении списка моделей: {str(e)}")
        return []

def get_model_info(model_id: str):
    """Получает информацию о конкретной модели"""
    try:
        model = client.models.retrieve(model_id)
        print(f"\nИнформация о модели {model_id}:")
        print(f"ID: {model.id}")
        print(f"Created: {model.created}")
        print(f"Owned by: {model.owned_by}")
        return model
    except Exception as e:
        logger.error(f"Ошибка при получении информации о модели: {str(e)}")
        return None

def validate_models():
    """Проверяет доступность настроенных моделей"""
    available_models = list_models()
    
    # Проверяем модель для эмбеддингов
    embedding_model = MODELS['embedding']['name']
    if embedding_model not in available_models:
        logger.warning(f"Модель для эмбеддингов {embedding_model} недоступна!")
        print(f"ВНИМАНИЕ: Модель {embedding_model} не найдена в списке доступных моделей")
    else:
        print(f"Модель для эмбеддингов {embedding_model} доступна")
        get_model_info(embedding_model)
    
    # Проверяем модель для генерации
    generation_model = MODELS['generation']['name']
    if generation_model not in available_models:
        logger.warning(f"Модель для генерации {generation_model} недоступна!")
        print(f"ВНИМАНИЕ: Модель {generation_model} не найдена в списке доступных моделей")
    else:
        print(f"Модель для генерации {generation_model} доступна")
        get_model_info(generation_model)

if __name__ == '__main__':
    # Проверяем настроенные модели
    validate_models()