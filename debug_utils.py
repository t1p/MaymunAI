import logging
from typing import Any, Dict, Optional
from config import DEBUG, INTERACTIVE_SETTINGS, RAG_SETTINGS, SEARCH_SETTINGS, MODELS
import numpy as np
import sys  # Добавляем импорт sys для выхода из программы

logger = logging.getLogger(__name__)

def truncate_text(text: str, max_length: int = DEBUG['truncate_output']) -> str:
    """Обрезает текст до указанной длины"""
    if not text:
        return "(пустой текст)"
    return f"{text[:max_length]}..." if len(text) > max_length else text

def format_vector(vector: Any, max_items: int = 5) -> str:
    """Форматирует вектор или другие данные для вывода"""
    if not vector:
        return "[]"
    
    if isinstance(vector, dict):
        # Для словарей показываем ключи и значения
        items = list(vector.items())[:max_items]
        preview = ", ".join(f"{k}: {format_value(v)}" for k, v in items)
        return f"{{{preview}}} ... {len(vector)} items"
    elif isinstance(vector, (list, tuple, np.ndarray)):
        # Для списков и массивов
        items = vector[:max_items]
        preview = ", ".join(format_value(x) for x in items)
        return f"[{preview}, ... {len(vector)} items]"
    else:
        # Для других типов данных
        return str(vector)

def format_value(value: Any) -> str:
    """Форматирует отдельное значение"""
    if isinstance(value, (float, np.float32, np.float64)):
        return f"{value:.4f}"
    elif isinstance(value, (int, np.int32, np.int64)):
        return str(value)
    elif isinstance(value, str):
        # Обрезаем длинные строки
        return f'"{value[:50]}..."' if len(value) > 50 else f'"{value}"'
    elif isinstance(value, (list, tuple, np.ndarray)):
        return format_vector(value)
    else:
        return str(value)

def print_stage_header(stage: str) -> None:
    """Выводит заголовок этапа"""
    stage_info = INTERACTIVE_SETTINGS['stages'].get(stage, {})
    description = stage_info.get('description', stage)
    print(f"\n{'='*20} {description} {'='*20}")

def get_stage_params(stage: str) -> dict:
    """Получает текущие параметры для этапа"""
    stage_info = INTERACTIVE_SETTINGS['stages'].get(stage, {})
    params = stage_info.get('params', [])
    result = {}
    
    for param in params:
        if param == 'model':
            # Получаем модель из MODELS, а не из RAG_SETTINGS
            model_key = stage_info.get('model_key')
            if model_key and model_key in MODELS:
                result[param] = MODELS[model_key]['name']
            else:
                result[param] = None
        elif stage in ['embeddings', 'generation']:
            result[param] = RAG_SETTINGS.get(param)
        elif stage == 'retrieval':
            result[param] = SEARCH_SETTINGS.get(param, None)
        elif stage == 'context':
            result[param] = RAG_SETTINGS.get(param)
            
    return result

def print_params(params: Dict[str, Any]) -> None:
    """Выводит текущие параметры"""
    print("\nТекущие параметры:")
    for param, value in params.items():
        description = INTERACTIVE_SETTINGS['param_descriptions'].get(param, '')
        print(f"  {param} = {value}  # {description}")

def get_user_params(stage: str, current_params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Запрашивает у пользователя новые параметры"""
    print("\nВведите новые значения (или Enter для пропуска):")
    new_params = {}
    
    for param in current_params:
        while True:
            try:
                value = input(f"{param} [{current_params[param]}]: ").strip()
                if not value:  # Пропускаем, если ввод пустой
                    new_params[param] = current_params[param]
                    break
                    
                # Преобразуем значение в правильный тип
                if isinstance(current_params[param], float):
                    new_params[param] = float(value)
                elif isinstance(current_params[param], int):
                    new_params[param] = int(value)
                else:
                    new_params[param] = value
                break
            except ValueError:
                print(f"Ошибка! Введите значение типа {type(current_params[param]).__name__}")
    
    return new_params if new_params != current_params else None

def confirm_action(prompt: str = "Продолжить? (да/нет): ") -> bool:
    """Запрашивает подтверждение действия"""
    while True:
        response = input(prompt).strip().lower()
        # Если ввод пустой, возвращаем False (нет)
        if not response:
            return False
        if response in ['y', 'yes', 'д', 'да']:
            return True
        if response in ['n', 'no', 'н', 'нет']:
            return False
        # Обработка команды выхода
        if response in ['exit', 'quit', 'выход']:
            print("Выход из программы...")
            sys.exit(0)
        print("Пожалуйста, ответьте 'да' или 'нет' (или 'выход' для завершения программы)")

def debug_step(stage: str, data: Any = None) -> Optional[Dict[str, Any]]:
    """
    Показывает отладочную информацию для этапа и предлагает изменить параметры
    
    Args:
        stage: Название этапа
        data: Данные для отображения
    """
    if not DEBUG['enabled'] or not DEBUG['interactive']:
        return None
        
    print_stage_header(stage)
    
    # Показываем данные в зависимости от этапа
    if data is not None:
        if stage == 'embeddings':
            if isinstance(data, dict):
                print(f"\nТекст: {data.get('text', '')}")
                print(f"Модель: {data.get('model', '')}")
                if 'embedding' in data:
                    print(f"Эмбеддинг: {format_vector(data['embedding'])}")
            else:
                print(f"Данные: {format_vector(data)}")
                
        elif stage == 'retrieval':
            if isinstance(data, list):
                for i, item in enumerate(data, 1):
                    print(f"\nДокумент {i}:")
                    print(f"Сходство: {item.get('similarity', 0):.4f}")
                    print(f"Текст: {item.get('text', '')[:200]}...")
            else:
                print(f"Данные: {format_vector(data)}")
                
        elif stage == 'context':
            if isinstance(data, dict):
                print(f"\nКоличество контекстов: {data.get('context_count', 0)}")
                print(f"Общее количество токенов: {data.get('total_tokens', 0)}")
                if 'context' in data:
                    print(f"\nКонтекст:\n{data['context'][:500]}...")
            else:
                print(f"Контекст:\n{str(data)[:500]}...")
            
        elif stage == 'generation':
            if isinstance(data, dict):
                print(f"\nМодель: {data.get('model', '')}")
                if 'prompt' in data:
                    print(f"Промпт:\n{data['prompt'][:500]}...")
                if 'answer' in data:
                    print(f"\nОтвет:\n{data['answer']}")
                if 'tokens' in data:
                    print(f"Токены: {data['tokens']}")
            else:
                print(f"Данные:\n{str(data)[:500]}...")
    
    # Получаем и показываем текущие параметры
    current_params = get_stage_params(stage)
    if current_params:
        print_params(current_params)
        
        # Спрашиваем, хочет ли пользователь изменить параметры
        if confirm_action("\nИзменить параметры этого этапа? (да/нет): "):
            return get_user_params(stage, current_params)
    
    return None 