import psycopg2
from config import DB_CONFIG, ROOT_MARKERS, SEARCH_SETTINGS
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

def get_tables():
    """Получает список таблиц в базе данных"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)
                return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"Ошибка при получении списка таблиц: {str(e)}")
        raise

def get_table_info(table_name: str):
    """Получает информацию о структуре таблицы"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Получаем информацию о колонках
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = %s
                    ORDER BY ordinal_position
                """, (table_name,))
                columns = cur.fetchall()
                
                # Получаем количество строк
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = cur.fetchone()[0]
                
                return {
                    'columns': columns,
                    'row_count': row_count
                }
    except Exception as e:
        logger.error(f"Ошибка при получении информации о таблице {table_name}: {str(e)}")
        raise

def get_table_properties(table_name: str):
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    cur.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name='{table_name}'
        ORDER BY ordinal_position;
    """)
    properties = cur.fetchall()
    cur.close()
    conn.close()
    return properties

def get_root_items(root_markers: List[str] = None) -> List[Dict[str, Any]]:
    """
    Получает корневые элементы (верхний уровень иерархии)
    
    Args:
        root_markers: Список маркеров для поиска корневых элементов.
                     Если None, используется ROOT_MARKERS из config
    """
    if root_markers is None:
        root_markers = ROOT_MARKERS
        
    logger.debug(f"Поиск корневых элементов по маркерам: {root_markers}")
    
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Формируем условия для LIKE
    like_conditions = " OR ".join([f"txt LIKE '%{marker}%'" for marker in root_markers])
    
    # Получаем элементы верхнего уровня
    query = f"""
        SELECT id, id_parent, txt, area
        FROM items 
        WHERE id_parent IS NULL
        OR id_parent IN (
            SELECT id FROM items WHERE {like_conditions}
        )
        ORDER BY area;
    """
    
    logger.debug(f"SQL запрос: {query}")
    cur.execute(query)
    
    items = cur.fetchall()
    result = []
    
    for item in items:
        item_with_context = get_item_with_context(item[0])
        if item_with_context:
            result.append(item_with_context)
    
    cur.close()
    conn.close()
    
    logger.debug(f"Найдено {len(result)} корневых элементов")
    return result

def get_item_with_context(item_id: str) -> Dict[str, Any]:
    """
    Получает запись из таблицы items вместе с контекстом (родительские и дочерние элементы)
    """
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    # Получаем основную запись
    cur.execute("""
        SELECT id, id_parent, txt, area
        FROM items 
        WHERE id = %s
    """, (item_id,))
    item = cur.fetchone()
    
    if not item:
        return None
    
    # Получаем родительские записи
    cur.execute("""
        WITH RECURSIVE parents AS (
            SELECT id, id_parent, txt, area, 1 as level
            FROM items
            WHERE id = %s
            UNION ALL
            SELECT i.id, i.id_parent, i.txt, i.area, p.level + 1
            FROM items i
            INNER JOIN parents p ON p.id_parent = i.id
        )
        SELECT * FROM parents
        ORDER BY level DESC;
    """, (item_id,))
    parents = cur.fetchall()
    
    # Получаем дочерние записи (теперь с большей глубиной)
    cur.execute("""
        WITH RECURSIVE children AS (
            SELECT id, id_parent, txt, area, 1 as level
            FROM items
            WHERE id_parent = %s
            UNION ALL
            SELECT i.id, i.id_parent, i.txt, i.area, c.level + 1
            FROM items i
            INNER JOIN children c ON i.id_parent = c.id
            WHERE c.level < 3  -- Ограничиваем глубину поиска
        )
        SELECT * FROM children
        ORDER BY level, area;
    """, (item_id,))
    children = cur.fetchall()
    
    cur.close()
    conn.close()
    
    return {
        'item': item,
        'parents': parents,
        'children': children
    }

def get_connection():
    """Создает подключение к базе данных"""
    return psycopg2.connect(**DB_CONFIG)

def get_items_sample(min_id: int = 1, sample_size: int = 20, root_id: str = None) -> List[Dict[str, Any]]:
    """
    Получает выборку элементов из базы данных
    
    Args:
        min_id: Минимальный ID для выборки (игнорируется, т.к. id это UUID)
        sample_size: Размер выборки
        root_id: ID корневого элемента для ограничения выборки (UUID)
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Базовый запрос
                query = """
                WITH RECURSIVE tree AS (
                    -- Корневой элемент
                    SELECT id, id_parent, txt, 1 as level
                    FROM items 
                    WHERE 1=1  -- Всегда истинное условие
                    """
                
                params = []
                
                # Добавляем условие для корневого элемента
                if root_id:
                    query += " AND id = %s"
                    params.append(root_id)
                else:
                    query += " AND id_parent IS NULL"
                    
                # Добавляем рекурсивную часть
                query += """
                    UNION ALL
                    -- Дочерние элементы
                    SELECT i.id, i.id_parent, i.txt, t.level + 1
                    FROM items i
                    JOIN tree t ON i.id_parent = t.id
                    WHERE t.level < 3  -- Ограничиваем глубину
                )
                SELECT id, id_parent, txt
                FROM tree
                ORDER BY RANDOM()
                LIMIT %s;
                """
                
                params.append(sample_size)
                
                cur.execute(query, params)
                rows = cur.fetchall()
                
                # Получаем родительские и дочерние элементы для каждого элемента
                items = []
                for row in rows:
                    item_data = {
                        'item': row,
                        'parents': get_parent_items(row[0], cur),
                        'children': get_child_items(row[0], cur)
                    }
                    items.append(item_data)
                
                return items
                
    except Exception as e:
        logger.error(f"Ошибка при получении выборки: {str(e)}")
        raise

def get_parent_items(item_id: int, cur) -> List[tuple]:
    """Получает родительские элементы"""
    query = """
    WITH RECURSIVE parents AS (
        -- Прямой родитель
        SELECT i.id, i.id_parent, i.txt, 1 as level
        FROM items i
        JOIN items child ON child.id_parent = i.id
        WHERE child.id = %s
        
        UNION ALL
        
        -- Рекурсивно поднимаемся вверх
        SELECT i.id, i.id_parent, i.txt, p.level + 1
        FROM items i
        JOIN parents p ON p.id_parent = i.id
        WHERE p.level < 3  -- Ограничиваем глубину
    )
    SELECT id, id_parent, txt
    FROM parents
    ORDER BY level DESC;
    """
    cur.execute(query, (item_id,))
    return cur.fetchall()

def get_child_items(item_id: int, cur) -> List[tuple]:
    """Получает дочерние элементы"""
    query = """
    WITH RECURSIVE children AS (
        -- Прямые потомки
        SELECT id, id_parent, txt, 1 as level
        FROM items
        WHERE id_parent = %s
        
        UNION ALL
        
        -- Рекурсивно спускаемся вниз
        SELECT i.id, i.id_parent, i.txt, c.level + 1
        FROM items i
        JOIN children c ON i.id_parent = c.id
        WHERE c.level < 3  -- Ограничиваем глубину
    )
    SELECT id, id_parent, txt
    FROM children
    ORDER BY level;
    """
    cur.execute(query, (item_id,))
    return cur.fetchall()

def view_item_tree(root_id: str):
    """Показывает дерево элементов для заданного корня"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Сначала проверяем существование элемента
                cur.execute("""
                    SELECT id, id_parent, txt, area
                    FROM items
                    WHERE id = %s
                """, (root_id,))
                root = cur.fetchone()
                
                if not root:
                    print(f"Элемент с ID {root_id} не найден")
                    return
                
                # Получаем дерево
                query = """
                WITH RECURSIVE tree AS (
                    -- Корневой элемент
                    SELECT id, id_parent, txt, area, 0 as level
                    FROM items
                    WHERE id = %s
                    
                    UNION ALL
                    
                    -- Рекурсивно получаем потомков
                    SELECT i.id, i.id_parent, i.txt, i.area, t.level + 1
                    FROM items i
                    JOIN tree t ON i.id_parent = t.id
                    WHERE t.level < 3  -- Ограничиваем глубину
                )
                SELECT id, id_parent, txt, area, level
                FROM tree
                ORDER BY level, id;
                """
                cur.execute(query, (root_id,))
                rows = cur.fetchall()
                
                print("\nСтруктура дерева:")
                for row in rows:
                    if row:
                        indent = "  " * row[4]  # level теперь в позиции 4
                        id = row[0] or 'None'
                        txt = row[2] or 'Нет текста'
                        area = f" [{row[3]}]" if row[3] else ""
                        
                        # Обрезаем текст до 100 символов
                        truncated_text = (txt[:97] + "...") if len(txt) > 100 else txt
                        print(f"{indent}[{id}]{area} {truncated_text}")
                    
    except Exception as e:
        logger.error(f"Ошибка при просмотре дерева: {str(e)}")
        raise

def view_root_items(markers: List[str] = None):
    """Показывает корневые элементы"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Базовый запрос для получения корневых элементов
                query = """
                SELECT i.id, i.txt, i.area
                FROM items i
                WHERE i.id_parent IS NULL
                """
                
                if markers:
                    # Если есть маркеры, добавляем условие LIKE
                    placeholders = ','.join(['%s'] * len(markers))
                    query += f" AND (txt ILIKE ANY (ARRAY[{placeholders}]))"
                    cur.execute(query, [f"%{m}%" for m in markers])
                else:
                    cur.execute(query)
                    
                rows = cur.fetchall()
                
                if not rows:
                    print("Корневые элементы не найдены")
                    return
                
                print("\nНайденные корневые элементы:")
                for row in rows:
                    if row and len(row) >= 2:  # Проверяем, что строка не пустая и содержит нужные поля
                        item_id, txt, area = row
                        # Обрезаем текст до 100 символов и добавляем многоточие если нужно
                        truncated_text = (txt[:97] + "...") if txt and len(txt) > 100 else txt
                        area_info = f" [{area}]" if area else ""
                        print(f"ID: {item_id}{area_info}\nТекст: {truncated_text}\n")
                    else:
                        logger.warning(f"Пропущена некорректная строка: {row}")
                
    except Exception as e:
        logger.error(f"Ошибка при просмотре корневых элементов: {str(e)}")
        raise

def search_text(text: str, context: int = 2) -> List[Dict]:
    """
    Поиск текста в базе данных
    
    Args:
        text: Текст для поиска
        context: Количество родительских/дочерних элементов для контекста
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Поиск элементов, содержащих текст
                query = """
                SELECT id, id_parent, txt
                FROM items
                WHERE txt ILIKE %s
                """
                cur.execute(query, (f"%{text}%",))
                rows = cur.fetchall()
                
                results = []
                for row in rows:
                    # Получаем контекст для каждого найденного элемента
                    item_data = {
                        'item': row,
                        'parents': get_parent_items(row[0], cur)[:context],
                        'children': get_child_items(row[0], cur)[:context]
                    }
                    results.append(item_data)
                
                return results
                
    except Exception as e:
        logger.error(f"Ошибка при поиске текста: {str(e)}")
        raise

def print_search_results(results: List[Dict]):
    """Выводит результаты поиска"""
    for i, result in enumerate(results, 1):
        print(f"\nРезультат {i}:")
        
        # Выводим родительские элементы
        if result['parents']:
            print("\nКонтекст выше:")
            for parent in result['parents']:
                print(f"[{parent[0]}] {parent[2][:100]}...")
        
        # Выводим найденный элемент
        print("\nНайденный элемент:")
        print(f"[{result['item'][0]}] {result['item'][2][:100]}...")
        
        # Выводим дочерние элементы
        if result['children']:
            print("\nКонтекст ниже:")
            for child in result['children']:
                print(f"[{child[0]}] {child[2][:100]}...")

def debug_database():
    """Выводит отладочную информацию о базе данных"""
    try:
        print("\nОтладочная информация о базе данных:")
        
        # Получаем список таблиц
        tables = get_tables()
        print(f"\nНайденные таблицы: {', '.join(tables)}")
        
        # Для каждой таблицы выводим информацию
        for table in tables:
            info = get_table_info(table)
            print(f"\nТаблица: {table}")
            print(f"Количество строк: {info['row_count']}")
            print("Структура:")
            for col in info['columns']:
                print(f"  {col[0]}: {col[1]} (nullable: {col[2]})")
                
    except Exception as e:
        logger.error(f"Ошибка при отладке базы данных: {str(e)}")
        raise

def get_block_info_by_name(name: str) -> List[Dict]:
    """
    Получает информацию о блоке по его названию
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Поиск блоков по названию
                query = """
                SELECT id, id_parent, txt, area, style
                FROM items
                WHERE txt ILIKE %s
                """
                cur.execute(query, (f"%{name}%",))
                blocks = cur.fetchall()
                
                if not blocks:
                    return []
                
                result = []
                for block in blocks:
                    # Получаем дочерние элементы первого уровня
                    cur.execute("""
                        SELECT id, txt, area, style
                        FROM items
                        WHERE id_parent = %s
                        ORDER BY area
                    """, (block[0],))
                    children = cur.fetchall()
                    
                    result.append({
                        'block': {
                            'id': block[0],
                            'parent_id': block[1],
                            'text': block[2],
                            'area': block[3],
                            'type': block[4]  # style используем как type
                        },
                        'children': [
                            {
                                'id': child[0],
                                'text': child[1],
                                'area': child[2],
                                'type': child[3]  # style используем как type
                            } for child in children
                        ]
                    })
                return result
    except Exception as e:
        logger.error(f"Ошибка при получении информации о блоке: {str(e)}")
        raise

def get_block_info_by_id(block_id: str) -> Optional[Dict]:
    """
    Получает информацию о блоке по его ID
    """
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                # Получаем информацию о блоке
                cur.execute("""
                    SELECT id, id_parent, txt, area, style
                    FROM items
                    WHERE id = %s
                """, (block_id,))
                block = cur.fetchone()
                
                if not block:
                    return None
                
                # Получаем родительский блок
                parent = None
                if block[1]:  # если есть id_parent
                    cur.execute("""
                        SELECT id, txt, area, style
                        FROM items
                        WHERE id = %s
                    """, (block[1],))
                    parent_data = cur.fetchone()
                    if parent_data:
                        parent = {
                            'id': parent_data[0],
                            'text': parent_data[1],
                            'area': parent_data[2],
                            'type': parent_data[3]  # style используем как type
                        }
                
                # Получаем дочерние элементы
                cur.execute("""
                    SELECT id, txt, area, style
                    FROM items
                    WHERE id_parent = %s
                    ORDER BY area
                """, (block[0],))
                children = cur.fetchall()
                
                return {
                    'block': {
                        'id': block[0],
                        'parent_id': block[1],
                        'text': block[2],
                        'area': block[3],
                        'type': block[4]  # style используем как type
                    },
                    'parent': parent,
                    'children': [
                        {
                            'id': child[0],
                            'text': child[1],
                            'area': child[2],
                            'type': child[3]  # style используем как type
                        } for child in children
                    ]
                }
    except Exception as e:
        logger.error(f"Ошибка при получении информации о блоке: {str(e)}")
        raise

def print_block_info(info: Dict):
    """
    Выводит информацию о блоке в читаемом формате
    """
    block = info['block']
    print("\nИнформация о блоке:")
    print(f"ID: {block['id']}")
    print(f"Текст: {block['text']}")
    print(f"Область: {block['area'] or 'не указана'}")
    print(f"Тип: {block['type'] or 'не указан'}")
    
    if info.get('parent'):
        parent = info['parent']
        print("\nРодительский блок:")
        print(f"ID: {parent['id']}")
        print(f"Текст: {parent['text']}")
        print(f"Область: {parent['area'] or 'не указана'}")
        print(f"Тип: {parent['type'] or 'не указан'}")
    
    if info['children']:
        print("\nДочерние блоки:")
        for child in info['children']:
            print(f"\n  ID: {child['id']}")
            print(f"  Текст: {child['text']}")
            print(f"  Область: {child['area'] or 'не указана'}")
            print(f"  Тип: {child['type'] or 'не указан'}")

def get_table_structure():
    """Показывает структуру таблицы items"""
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns 
                    WHERE table_name = 'items'
                    ORDER BY ordinal_position;
                """)
                columns = cur.fetchall()
                
                print("\nСтруктура таблицы items:")
                for col in columns:
                    print(f"  {col[0]}: {col[1]} (nullable: {col[2]})")
                
                # Показываем пример значений
                cur.execute("""
                    SELECT id, id_parent, txt, area, style 
                    FROM items 
                    LIMIT 1
                """)
                row = cur.fetchone()
                if row:
                    print("\nПример значений:")
                    print(f"  id: {row[0]}")
                    print(f"  id_parent: {row[1]}")
                    print(f"  txt: {row[2][:50]}...")
                    print(f"  area: {row[3]}")
                    print(f"  style: {row[4]}")
    except Exception as e:
        logger.error(f"Ошибка при получении структуры таблицы: {str(e)}")
        raise

if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)
    
    print("\nТестирование корневых элементов:")
    root_items = get_root_items()
    for item in root_items:
        print(f"\nКорневой элемент: {item['item']}")
        print(f"Количество родителей: {len(item['parents'])}")
        print(f"Количество детей: {len(item['children'])}")
    
    start_row = 3
    end_row = 10
    
    print("\nTable: items")
    properties = get_table_properties('items')
    print("Columns:", properties)
    
    try:
        items = get_items_sample(start_row, end_row)
        print(f"\nRows {start_row}-{end_row} with context:")
        for item in items:
            print("\nMain item:", item['item'])
            print("Parents:", item['parents'])
            print("Children:", item['children'])
    except Exception as e:
        print(f"Error getting data: {str(e)}")

    debug_database() 