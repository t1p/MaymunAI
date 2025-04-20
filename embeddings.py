from typing import List, Dict, Any, Optional, Tuple
from openai import OpenAI
from config import OPENAI_API_KEY, MODELS, RAG_SETTINGS
import numpy as np
import logging
from debug_utils import debug_step
from openai_api_models import client
import hashlib
from db import get_connection
from utils import timeit, ProgressIndicator
from base64 import b64decode
import struct
import tiktoken
import json
import re

logger = logging.getLogger(__name__)

def get_text_hash(text: str) -> str:
    """Возвращает SHA-256 хеш текста"""
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def semantic_chunking(text: str, 
                     max_tokens: int = 500, 
                     overlap: float = 0.15,
                     model: str = None) -> List[Tuple[str, Dict]]:
    """
    Разбивает текст на семантические чанки с перекрытием
    
    Args:
        text: Исходный текст для разбиения
        max_tokens: Максимальное количество токенов в чанке
        overlap: Процент перекрытия между чанками (0.0-1.0)
        model: Модель для подсчета токенов
    
    Returns:
        Список кортежей (чанк, метаданные)
    """
    if model is None:
        model = MODELS['embedding']['name']
    
    # Определяем границы абзацев/разделов
    paragraphs = re.split(r'\n\s*\n', text.strip())
    chunks = []
    current_chunk = []
    current_tokens = 0
    overlap_tokens = int(max_tokens * overlap)
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        para_tokens = count_tokens(para, model)
        
        # Если абзац слишком большой, разбиваем его дальше
        if para_tokens > max_tokens:
            sentences = re.split(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s', para)
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                    
                sent_tokens = count_tokens(sent, model)
                
                if current_tokens + sent_tokens > max_tokens:
                    if current_chunk:
                        chunk_text = '\n\n'.join(current_chunk)
                        chunks.append((chunk_text, {
                            'type': 'paragraph',
                            'tokens': current_tokens,
                            'is_complete': True
                        }))
                        # Сохраняем конец текущего чанка для перекрытия
                        overlap_part = '\n\n'.join(current_chunk[-overlap_tokens:]) if overlap_tokens else ''
                        current_chunk = [overlap_part] if overlap_part else []
                        current_tokens = count_tokens(overlap_part, model)
                        
                current_chunk.append(sent)
                current_tokens += sent_tokens
        else:
            if current_tokens + para_tokens > max_tokens:
                if current_chunk:
                    chunk_text = '\n\n'.join(current_chunk)
                    chunks.append((chunk_text, {
                        'type': 'paragraph',
                        'tokens': current_tokens,
                        'is_complete': True
                    }))
                    # Сохраняем конец текущего чанка для перекрытия
                    overlap_part = '\n\n'.join(current_chunk[-overlap_tokens:]) if overlap_tokens else ''
                    current_chunk = [overlap_part] if overlap_part else []
                    current_tokens = count_tokens(overlap_part, model)
                    
            current_chunk.append(para)
            current_tokens += para_tokens
    
    # Добавляем последний чанк
    if current_chunk:
        chunk_text = '\n\n'.join(current_chunk)
        chunks.append((chunk_text, {
            'type': 'paragraph',
            'tokens': current_tokens,
            'is_complete': True
        }))
    
    return chunks

@timeit
def create_embedding_for_item(item, chunked: bool = True):
    """
    Создает эмбеддинг для элемента с учетом его структуры
    
    Args:
        item: Элемент для обработки
        chunked: Если True, разбивает текст на чанки
    
    Returns:
        Словарь с эмбеддингами и метаданными
    """
    try:
        if 'item' in item:
            item_id, parent_id, item_text = item['item']
            text = item_text.strip() if item_text else ""
            
            if not chunked:
                # Старый вариант без разбиения (для обратной совместимости)
                embedding = get_embedding(text)
                return {
                    'embedding': embedding,
                    'text': text,
                    'item_id': item_id,
                    'chunked': False
                }
            else:
                # Новый вариант с семантическим разбиением
                chunks = semantic_chunking(
                    text,
                    max_tokens=RAG_SETTINGS.get('max_chunk_tokens', 500),
                    overlap=RAG_SETTINGS.get('chunk_overlap', 0.15)
                )
                
                embeddings = []
                for chunk_text, metadata in chunks:
                    embedding = get_embedding(chunk_text)
                    embeddings.append({
                        'embedding': embedding,
                        'text': chunk_text,
                        'metadata': metadata,
                        'item_id': f"{item_id}_{len(embeddings)}"
                    })
                
                return {
                    'embeddings': embeddings,
                    'original_text': text,
                    'item_id': item_id,
                    'chunked': True
                }
        else:
            raise ValueError("Неверный формат элемента")
    except Exception as e:
        logger.error(f"Ошибка при создании эмбеддинга для элемента: {str(e)}")
        return {
            'embedding': [],
            'text': '',
            'item_id': 'error',
            'chunked': False
        }

def get_embedding(text: str, model: str = None) -> List[float]:
    """
    Получает эмбеддинг для текста с помощью OpenAI API
    
    Args:
        text: Текст для векторизации
        model: Модель для эмбеддинга (если None, берется из конфига)
    
    Returns:
        Список чисел с эмбеддингом
    """
    if model is None:
        model = MODELS['embedding']['name']
    
    try:
        response = client.embeddings.create(
            input=text,
            model=model
        )
        return response.data[0].embedding
    except Exception as e:
        logger.error(f"Ошибка при получении эмбеддинга: {str(e)}")
        return []

def calculate_similarity(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Вычисляет косинусное сходство между двумя эмбеддингами
    
    Args:
        embedding1: Первый вектор эмбеддинга
        embedding2: Второй вектор эмбеддинга
    
    Returns:
        Значение косинусного сходства от -1 до 1
    """
    if not embedding1 or not embedding2:
        return 0.0
        
    dot_product = np.dot(embedding1, embedding2)
    norm1 = np.linalg.norm(embedding1)
    norm2 = np.linalg.norm(embedding2)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
        
    return dot_product / (norm1 * norm2)

# Остальные существующие функции (get_query_embedding_from_cache, save_query_embedding_to_cache,
# decode_base64_embedding, save_embedding_to_db, get_embedding_from_db) остаются без изменений

def count_tokens(text: str, model: str) -> int:
    """Подсчитывает количество токенов в тексте для указанной модели
    
    Args:
        text: Текст для анализа
        model: Идентификатор модели (например, "text-embedding-ada-002")
        
    Returns:
        Количество токенов в тексте
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        logger.error(f"Ошибка при подсчёте токенов: {str(e)}")
        return 0