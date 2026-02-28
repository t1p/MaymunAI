import logging
from typing import List, Dict, Any, Optional
from openai import OpenAI
from config import OPENAI_API_KEY, RAG_SETTINGS, MODELS
from retrieval import rerank_items as search_similar_items
from db import get_items_sample
import tiktoken
from debug_utils import debug_step
from openai_api_models import client
from utils import timeit
from packs.loader import (
    get_guardrails_for_pack,
    get_pack_model_preset,
    get_system_prompt_for_pack,
    resolve_pack_for_context,
)
from audit_log import log_audit_event

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPT = "Ты помощник, который отвечает на вопросы, используя предоставленный контекст."

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

@timeit
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

@timeit
def generate_answer(
    query: str,
    context_items: List[Dict[str, Any]],
    runtime_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Генерирует ответ на основе контекста"""
    logger.debug("Генерация ответа")
    
    # Проверяем, есть ли реальный контекст
    has_real_context = False
    for item in context_items:
        if not item['text'].startswith("Информация отсутствует"):
            has_real_context = True
            break
    
    # Если нет реального контекста, сообщаем об этом
    if not has_real_context:
        logger.warning("Отсутствует релевантный контекст, используем более простую модель")
        return "Извините, в базе знаний не найдено информации по вашему запросу. Пожалуйста, уточните вопрос или используйте другие ключевые слова."
    
    prompt = generate_prompt(query, context_items)

    runtime_context = runtime_context or {}
    selected_pack = None
    system_prompt = DEFAULT_SYSTEM_PROMPT
    model_name = MODELS['generation']['name']
    pack_guardrails: Dict[str, Any] = {}

    try:
        selected_pack = resolve_pack_for_context(runtime_context)
        system_prompt = get_system_prompt_for_pack(selected_pack)
        preset = get_pack_model_preset(selected_pack)
        generation_preset = preset.get('generation', {}) if isinstance(preset, dict) else {}
        model_name = generation_preset.get('model', model_name)
        pack_guardrails = get_guardrails_for_pack(selected_pack)

        try:
            log_audit_event(
                event_type='pack_selected',
                actor='system',
                pack_id=selected_pack,
                details={
                    'chat_id': runtime_context.get('chat_id'),
                    'group': runtime_context.get('group'),
                    'topic': runtime_context.get('topic'),
                },
            )
        except Exception:
            logger.debug('Не удалось записать audit event pack_selected', exc_info=True)
    except Exception as pack_error:
        logger.warning(f"Pack runtime fallback to defaults: {pack_error}")
    
    # Получаем параметры генерации (возможно, обновленные пользователем)
    gen_params = debug_step('generation') or RAG_SETTINGS

    if selected_pack:
        output_limits = pack_guardrails.get('output_limits', {}) if isinstance(pack_guardrails, dict) else {}
        pack_max_tokens = output_limits.get('max_message_length')
        if isinstance(pack_max_tokens, int) and pack_max_tokens > 0:
            gen_params = {**gen_params, 'max_tokens': min(gen_params['max_tokens'], pack_max_tokens)}
    
    total_tokens = num_tokens_from_string(prompt)
    logger.debug(f"Общее количество токенов в промпте: {total_tokens}")
    
    # Оставляем запас для ответа
    max_prompt_tokens = MODELS['generation']['max_tokens'] - gen_params['max_tokens']
    if total_tokens > max_prompt_tokens:
        logger.warning(f"Превышен безопасный лимит токенов: {total_tokens}")
        prompt = truncate_text(prompt, max_prompt_tokens)
        logger.debug("Промпт обрезан до безопасного размера")
    
    try:
        try:
            log_audit_event(
                event_type='response_generation_started',
                actor='system',
                pack_id=selected_pack,
                details={
                    'model': model_name,
                    'query_len': len(query),
                    'context_items': len(context_items),
                },
            )
        except Exception:
            logger.debug('Не удалось записать audit event response_generation_started', exc_info=True)

        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=gen_params['temperature'],
            max_tokens=gen_params['max_tokens']
        )
        logger.debug("Ответ получен от API")
        
        answer = response.choices[0].message.content
        
        # Оставить только этот один вызов в конце
        debug_step('generation', {
            'model': model_name,
            'pack': selected_pack,
            'answer_tokens': num_tokens_from_string(answer),
            'answer': answer
        })

        try:
            log_audit_event(
                event_type='response_generated',
                actor='system',
                pack_id=selected_pack,
                details={
                    'model': model_name,
                    'answer_len': len(answer),
                },
            )
        except Exception:
            logger.debug('Не удалось записать audit event response_generated', exc_info=True)
        
        return answer
    except Exception as e:
        logger.error(f"Ошибка при получении ответа от API: {str(e)}")
        raise 
