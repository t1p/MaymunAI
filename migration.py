import logging
from db import get_connection

logger = logging.getLogger(__name__)

def migrate_database():
    """Обновляет структуру таблиц в соответствии с новой схемой"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Проверяем существующую структуру таблицы embeddings
                cur.execute("SELECT column_name FROM information_schema.columns WHERE table_name = 'embeddings'")
                columns = [col[0] for col in cur.fetchall()]
                
                # Добавляем недостающие колонки
                if 'text' not in columns:
                    logger.info("Добавление колонки 'text' в таблицу embeddings")
                    cur.execute("ALTER TABLE embeddings ADD COLUMN text TEXT")
                
                if 'model_version' not in columns:
                    logger.info("Добавление колонки 'model_version' в таблицу embeddings")
                    cur.execute("ALTER TABLE embeddings ADD COLUMN model_version VARCHAR(20) DEFAULT '1.0'")
                
                # Обновляем ограничения уникальности
                logger.info("Обновление ограничений уникальности")
                cur.execute("""
                    BEGIN;
                    -- Удаляем старое ограничение, если оно существует
                    DO $$
                    BEGIN
                        IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'embeddings_item_id_model_key') THEN
                            ALTER TABLE embeddings DROP CONSTRAINT embeddings_item_id_model_key;
                        END IF;
                    END $$;
                    
                    -- Добавляем новое ограничение
                    ALTER TABLE embeddings ADD CONSTRAINT embeddings_item_id_model_version_key 
                    UNIQUE(item_id, model, model_version);
                    COMMIT;
                """)
                
                conn.commit()
                logger.info("Миграция базы данных успешно завершена")
                
                return True
    except Exception as e:
        logger.error(f"Ошибка при миграции базы данных: {str(e)}")
        return False

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    migrate_database() 