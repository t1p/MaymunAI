#!/usr/bin/env python3
"""
Скрипт для хранения и загрузки конфигурации из базы данных
"""
import logging
import json
from db import get_connection

logger = logging.getLogger(__name__)

def save_config_to_db(config_name, config_value):
    """Сохраняет параметр конфигурации в базе данных"""
    try:
        # Если значение не строка, сериализуем его в JSON
        if not isinstance(config_value, str):
            config_value = json.dumps(config_value)
            
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Проверяем, существует ли таблица
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS config (
                        name VARCHAR(255) PRIMARY KEY,
                        value TEXT,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                # Вставляем или обновляем значение
                cur.execute("""
                    INSERT INTO config (name, value, updated_at)
                    VALUES (%s, %s, NOW())
                    ON CONFLICT (name) 
                    DO UPDATE SET value = %s, updated_at = NOW()
                """, (config_name, config_value, config_value))
                
                conn.commit()
                logger.info(f"Сохранен параметр '{config_name}' в базе данных")
                return True
    except Exception as e:
        logger.error(f"Ошибка при сохранении конфигурации в БД: {str(e)}")
        return False

def get_config_from_db(config_name, default_value=None):
    """Загружает параметр конфигурации из базы данных"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Проверяем, существует ли таблица
                cur.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = 'config'
                    )
                """)
                
                if not cur.fetchone()[0]:
                    return default_value
                
                # Получаем значение
                cur.execute("SELECT value FROM config WHERE name = %s", (config_name,))
                result = cur.fetchone()
                
                if result:
                    value = result[0]
                    
                    # Пробуем десериализовать JSON
                    try:
                        return json.loads(value)
                    except (json.JSONDecodeError, TypeError):
                        return value
                        
                return default_value
    except Exception as e:
        logger.error(f"Ошибка при загрузке конфигурации из БД: {str(e)}")
        return default_value

def set_threshold(value):
    """Устанавливает пороговое значение сходства в базе данных"""
    return save_config_to_db('similarity_threshold', value)

def get_threshold(default=0.5):
    """Получает пороговое значение сходства из базы данных"""
    return get_config_from_db('similarity_threshold', default)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, 
                        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    # Установка порогового значения
    set_threshold(0.5)
    print(f"Текущее пороговое значение: {get_threshold()}") 