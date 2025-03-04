#!/usr/bin/env python3
"""
Скрипт для анализа структуры базы данных и сохранения информации в файл
"""
import os
import json
import datetime
from typing import List, Dict, Any, Optional
import logging
from db import get_connection, DB_CONFIG

# Настройка логирования
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('db_analyzer')

def get_database_info() -> Dict[str, Any]:
    """Получает общую информацию о базе данных"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Получаем версию PostgreSQL
            cur.execute("SELECT version();")
            version = cur.fetchone()[0]
            
            # Получаем размер базы данных
            cur.execute("""
                SELECT pg_size_pretty(pg_database_size(current_database())) as db_size;
            """)
            db_size = cur.fetchone()[0]
            
            # Получаем имя текущей базы данных
            cur.execute("SELECT current_database();")
            db_name = cur.fetchone()[0]
            
            # Получаем настройки базы данных
            cur.execute("""
                SELECT name, setting, short_desc 
                FROM pg_settings 
                WHERE category = 'Connections' OR category = 'Resource Usage'
                ORDER BY category, name;
            """)
            settings = [{"name": row[0], "value": row[1], "description": row[2]} 
                        for row in cur.fetchall()]
            
            return {
                "database_name": db_name,
                "version": version,
                "size": db_size,
                "settings": settings,
                "connection_info": {
                    "host": DB_CONFIG["host"],
                    "port": DB_CONFIG["port"],
                    "dbname": DB_CONFIG["dbname"],
                    "user": DB_CONFIG["user"]
                }
            }

def get_tables_info() -> List[Dict[str, Any]]:
    """Получает информацию о всех таблицах в базе данных"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Получаем список таблиц
            cur.execute("""
                SELECT 
                    tablename,
                    tableowner,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as total_size,
                    pg_total_relation_size(schemaname||'.'||tablename) as size_bytes,
                    obj_description((schemaname||'.'||tablename)::regclass, 'pg_class') as description
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY size_bytes DESC;
            """)
            
            tables = []
            for row in cur.fetchall():
                table_name = row[0]
                owner = row[1]
                size = row[2]
                size_bytes = row[3]
                description = row[4]
                
                # Получаем количество строк
                cur.execute(f"SELECT COUNT(*) FROM {table_name};")
                row_count = cur.fetchone()[0]
                
                # Получаем структуру таблицы
                cur.execute(f"""
                    SELECT 
                        column_name, 
                        data_type, 
                        character_maximum_length,
                        column_default,
                        is_nullable
                    FROM information_schema.columns
                    WHERE table_name = %s
                    ORDER BY ordinal_position;
                """, (table_name,))
                
                columns = []
                for col in cur.fetchall():
                    columns.append({
                        "name": col[0],
                        "type": col[1],
                        "max_length": col[2],
                        "default": col[3],
                        "nullable": col[4]
                    })
                
                # Получаем индексы таблицы
                cur.execute(f"""
                    SELECT
                        indexname,
                        indexdef
                    FROM pg_indexes
                    WHERE tablename = %s;
                """, (table_name,))
                
                indexes = []
                for idx in cur.fetchall():
                    indexes.append({
                        "name": idx[0],
                        "definition": idx[1]
                    })
                
                # Получаем ограничения таблицы
                cur.execute(f"""
                    SELECT
                        conname,
                        pg_get_constraintdef(c.oid)
                    FROM pg_constraint c
                    JOIN pg_namespace n ON n.oid = c.connamespace
                    WHERE conrelid = (SELECT oid FROM pg_class WHERE relname = %s 
                                     AND relnamespace = n.oid)
                    AND n.nspname = 'public';
                """, (table_name,))
                
                constraints = []
                for con in cur.fetchall():
                    constraints.append({
                        "name": con[0],
                        "definition": con[1]
                    })
                
                # Получаем примеры данных
                try:
                    cur.execute(f"SELECT * FROM {table_name} LIMIT 5;")
                    column_names = [desc[0] for desc in cur.description]
                    sample_data = []
                    for sample_row in cur.fetchall():
                        sample_data.append(dict(zip(column_names, sample_row)))
                except Exception as e:
                    sample_data = [{"error": str(e)}]
                
                tables.append({
                    "name": table_name,
                    "owner": owner,
                    "size": size,
                    "size_bytes": size_bytes,
                    "row_count": row_count,
                    "description": description,
                    "columns": columns,
                    "indexes": indexes,
                    "constraints": constraints,
                    "sample_data": sample_data
                })
            
            return tables

def get_relationships() -> List[Dict[str, Any]]:
    """Получает информацию о внешних ключах и связях между таблицами"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT
                    tc.table_name as source_table,
                    kcu.column_name as source_column,
                    ccu.table_name AS target_table,
                    ccu.column_name AS target_column,
                    tc.constraint_name
                FROM 
                    information_schema.table_constraints AS tc 
                    JOIN information_schema.key_column_usage AS kcu
                      ON tc.constraint_name = kcu.constraint_name
                      AND tc.table_schema = kcu.table_schema
                    JOIN information_schema.constraint_column_usage AS ccu
                      ON ccu.constraint_name = tc.constraint_name
                      AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY'
                ORDER BY tc.table_name;
            """)
            
            relationships = []
            for row in cur.fetchall():
                relationships.append({
                    "source_table": row[0],
                    "source_column": row[1],
                    "target_table": row[2],
                    "target_column": row[3],
                    "constraint_name": row[4]
                })
            
            return relationships

def get_query_statistics() -> List[Dict[str, Any]]:
    """Получает статистику запросов и производительности"""
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Проверим доступность pg_stat_statements
            cur.execute("""
                SELECT EXISTS(
                    SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements'
                );
            """)
            has_pg_stat = cur.fetchone()[0]
            
            if has_pg_stat:
                cur.execute("""
                    SELECT 
                        round(total_exec_time::numeric, 2) as total_time,
                        calls,
                        round(mean_exec_time::numeric, 2) as mean_time,
                        substring(query, 1, 200) as query
                    FROM pg_stat_statements
                    ORDER BY total_exec_time DESC
                    LIMIT 10;
                """)
                
                return [{
                    "total_time_ms": row[0],
                    "calls": row[1],
                    "mean_time_ms": row[2],
                    "query": row[3]
                } for row in cur.fetchall()]
            else:
                return [{"note": "pg_stat_statements extension is not installed"}]

def analyze_database():
    """Анализирует базу данных и сохраняет информацию в файл"""
    logger.info("Начинаем анализ базы данных...")
    
    # Получаем текущую дату и время для имени файла
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = f"db_structure_{timestamp}.json"
    
    try:
        # Собираем все данные
        db_info = get_database_info()
        tables_info = get_tables_info()
        relationships = get_relationships()
        query_stats = get_query_statistics()
        
        # Формируем полную структуру данных
        database_structure = {
            "timestamp": datetime.datetime.now().isoformat(),
            "database_info": db_info,
            "tables": tables_info,
            "relationships": relationships,
            "query_statistics": query_stats
        }
        
        # Сохраняем в файл
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(database_structure, f, indent=2, default=str)
        
        # Создаем также более удобную для чтения версию
        readable_file = f"db_structure_{timestamp}.txt"
        with open(readable_file, 'w', encoding='utf-8') as f:
            f.write(f"База данных: {db_info['database_name']}\n")
            f.write(f"Версия PostgreSQL: {db_info['version']}\n")
            f.write(f"Размер базы данных: {db_info['size']}\n\n")
            
            f.write("=== ТАБЛИЦЫ ===\n")
            for table in tables_info:
                f.write(f"\n{table['name']} ({table['row_count']} строк, размер: {table['size']})\n")
                f.write("-" * 80 + "\n")
                
                f.write("Колонки:\n")
                for col in table['columns']:
                    nullable = "NULL" if col['nullable'] == "YES" else "NOT NULL"
                    f.write(f"  {col['name']}: {col['type']}" + 
                           (f"({col['max_length']})" if col['max_length'] else "") + 
                           f" {nullable}" +
                           (f" DEFAULT {col['default']}" if col['default'] else "") + 
                           "\n")
                
                if table['indexes']:
                    f.write("\nИндексы:\n")
                    for idx in table['indexes']:
                        f.write(f"  {idx['name']}: {idx['definition']}\n")
                
                if table['constraints']:
                    f.write("\nОграничения:\n")
                    for con in table['constraints']:
                        f.write(f"  {con['name']}: {con['definition']}\n")
                
                f.write("\nПримеры данных:\n")
                for i, sample in enumerate(table['sample_data'][:3], 1):
                    f.write(f"  Запись {i}: {str(sample)[:100]}{'...' if len(str(sample)) > 100 else ''}\n")
            
            if relationships:
                f.write("\n\n=== СВЯЗИ МЕЖДУ ТАБЛИЦАМИ ===\n")
                for rel in relationships:
                    f.write(f"{rel['source_table']}.{rel['source_column']} -> " +
                           f"{rel['target_table']}.{rel['target_column']} " +
                           f"({rel['constraint_name']})\n")
        
        logger.info(f"Анализ завершен. Результаты сохранены в файлах:")
        logger.info(f"  - {output_file} (JSON формат)")
        logger.info(f"  - {readable_file} (текстовый формат)")
        
        return {
            "json_file": output_file,
            "text_file": readable_file
        }
        
    except Exception as e:
        logger.error(f"Ошибка при анализе базы данных: {str(e)}", exc_info=True)
        return {"error": str(e)}

if __name__ == "__main__":
    files = analyze_database()
    if "error" not in files:
        print(f"\nАнализ базы данных завершен успешно!")
        print(f"Результаты сохранены в:")
        print(f"  - {files['json_file']} (JSON формат для программной обработки)")
        print(f"  - {files['text_file']} (текстовый формат для чтения)")
        
        # Выводим основную информацию
        with open(files['text_file'], 'r', encoding='utf-8') as f:
            head = ''.join(f.readlines()[:20])
            print("\nФрагмент результатов:")
            print("=" * 80)
            print(head)
            print("..." if os.path.getsize(files['text_file']) > len(head) else "")
            print("=" * 80)
    else:
        print(f"\nПроизошла ошибка при анализе базы данных: {files['error']}") 