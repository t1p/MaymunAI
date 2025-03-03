import logging
from typing import List, Dict, Any
from openai import OpenAI
from config import OPENAI_API_KEY, RAG_SETTINGS, MODELS
from retrieval import search_similar_items
from db import get_items_sample
import tiktoken
from debug_utils import debug_step
from openai_api_models import client

logger = logging.getLogger(__name__)

def num_tokens_from_string(string: str, model: str = None) -> int:
    """Возвращает количество токенов в строке"""
    if model is None:
        model = MODELS['generation']['name']
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(string))
    except KeyError:
        logger.warning(f"Модель {model} не найдена, используем gpt-3.5-turbo")
        encoding = tiktoken.encoding_for_model("gpt-3.5-turbo")
        return len(encoding.encode(string))

def truncate_text(text: str, max_tokens: int = None) -> str:
    """Обрезает текст до указанного количества токенов"""
    if max_tokens is None:
        max_tokens = MODELS['generation']['max_tokens']
        
    logger.debug(f"Обрезаем текст. Исходная длина: {len(text)} символов")
    encoding = tiktoken.encoding_for_model(MODELS['generation']['name'])
    tokens = encoding.encode(text)
    logger.debug(f"Количество токенов: {len(tokens)}")
    
    if len(tokens) <= max_tokens:
        return text
    
    truncated = encoding.decode(tokens[:max_tokens])
    logger.debug(f"Текст обрезан. Новая длина: {len(truncated)} символов")
    return truncated

def generate_prompt(query: str, context_items: List[Dict[str, Any]]) -> str:
    """Генерирует промпт для модели"""
    logger.debug(f"Генерация промпта для запроса: {query}")
    
    # Получаем параметры контекста (возможно, обновленные пользователем)
    context_params = debug_step('context') or RAG_SETTINGS
    
    # Ограничиваем количество токенов для каждого контекста
    max_tokens_per_context = context_params['chunk_size']
    context_texts = []
    
    for i, item in enumerate(context_items):
        logger.debug(f"Обработка контекста {i+1}")
        context = item['text']
        truncated_context = truncate_text(context, max_tokens_per_context)
        context_texts.append(f"Context {i+1}:\n{truncated_context}")
    
    context_str = "\n\n".join(context_texts)
    total_tokens = num_tokens_from_string(context_str)
    logger.debug(f"Общее количество токенов в контексте: {total_tokens}")
    
    prompt = f"""Используй следующий контекст для ответа на вопрос. 
Если информации недостаточно, скажи об этом.

{context_str}

Вопрос: {query}

Ответ:"""

    # Отладка: показываем собранный контекст и промпт
    debug_step('context', {
        'context_count': len(context_texts),
        'total_tokens': total_tokens,
        'context': context_str
    })
    
    debug_step('generation', {
        'model': MODELS['generation']['name'],
        'prompt': prompt,
        'tokens': num_tokens_from_string(prompt)
    })
    
    return prompt

def generate_answer(query: str, context_items: List[Dict[str, Any]]) -> str:
    """Генерирует ответ на основе контекста"""
    logger.debug("Генерация ответа")
    prompt = generate_prompt(query, context_items)
    
    # Получаем параметры генерации (возможно, обновленные пользователем)
    gen_params = debug_step('generation') or RAG_SETTINGS
    
    total_tokens = num_tokens_from_string(prompt)
    logger.debug(f"Общее количество токенов в промпте: {total_tokens}")
    
    # Оставляем запас для ответа
    max_prompt_tokens = MODELS['generation']['max_tokens'] - gen_params['max_tokens']
    if total_tokens > max_prompt_tokens:
        logger.warning(f"Превышен безопасный лимит токенов: {total_tokens}")
        prompt = truncate_text(prompt, max_prompt_tokens)
        logger.debug("Промпт обрезан до безопасного размера")
    
    try:
        response = client.chat.completions.create(
            model=MODELS['generation']['name'],
            messages=[
                {"role": "system", "content": "Ты помощник, который отвечает на вопросы, используя предоставленный контекст."},
                {"role": "user", "content": prompt}
            ],
            temperature=gen_params['temperature'],
            max_tokens=gen_params['max_tokens']
        )
        logger.debug("Ответ получен от API")
        
        answer = response.choices[0].message.content
        
        # Отладка: показываем результат
        debug_step('generation', {
            'model': MODELS['generation']['name'],
            'answer_tokens': num_tokens_from_string(answer),
            'answer': answer
        })
        
        return answer
    except Exception as e:
        logger.error(f"Ошибка при получении ответа от API: {str(e)}")
        raise 