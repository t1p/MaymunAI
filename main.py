from typing import List, Dict, Any
import argparse
import logging
from db import get_items_sample, view_item_tree, view_root_items, search_text, print_search_results, get_block_info_by_name, get_block_info_by_id, print_block_info, ensure_text_search_index, search_by_keywords
from retrieval import rerank_items as search_similar_items
from rag import generate_answer
from config import DEBUG, SEARCH_SETTINGS, RAG_SETTINGS
from debug_utils import confirm_action, debug_step
from keywords import generate_keywords_for_query
import db_analyzer

def convert_item_format(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Преобразует формат элементов из БД в формат, ожидаемый retrieval.py"""
    converted = []
    for item in items:
        if 'item' in item and len(item['item']) > 2:
            converted_item = {
                'id': item['item'][0],
                'text': item['item'][2],
                'item': item['item'],  # сохраняем оригинальную структуру
                'parents': item.get('parents', []),
                'children': item.get('children', [])
            }
            converted.append(converted_item)
        else:
            logger.warning(f"Пропущен элемент с некорректным форматом: {item}")
    return converted

def setup_logging(debug: bool):
    """Настройка логгирования"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

def process_query(query: str, sample_size: int = None, top_k: int = None, root_id: str = None) -> str:
    """
    Обрабатывает пользовательский запрос
    """
    logger = logging.getLogger('process_query')
    
    # Используем значения из настроек, если не указаны явно
    if sample_size is None:
        sample_size = SEARCH_SETTINGS['sample_size']
    if top_k is None:
        top_k = SEARCH_SETTINGS['top_k']
    
    # Получаем выборку элементов
    logger.debug(f"Получаем выборку из {sample_size} элементов")
    items = get_items_sample(1, sample_size, root_id=root_id)
    logger.debug(f"Получено {len(items)} элементов")
    
    # Преобразуем формат элементов
    converted_items = convert_item_format(items)
    
    # Ищем релевантные элементы
    logger.debug(f"Ищем {top_k} релевантных элементов")
    relevant_items = search_similar_items(query, converted_items, top_k)
    logger.debug(f"Найдено {len(relevant_items)} релевантных элементов")
    
    # В режиме отладки показываем найденные элементы
    if DEBUG['enabled']:
        print("\nНайденные релевантные элементы:")
        for i, item in enumerate(relevant_items, 1):
            print(f"\n--- Элемент {i} (сходство: {item['similarity']:.4f}) ---")
            print(item['text'][:200] + "..." if len(item['text']) > 200 else item['text'])
            
            # Добавляем расширенную информацию в расширенном режиме отладки
            if DEBUG.get('extended', False):
                print(f"ID элемента: {item.get('id', 'Нет ID')}")
                print(f"Путь: {item.get('path', 'Нет информации о пути')}")
                if 'metadata' in item:
                    print("Метаданные:", item['metadata'])
    
    # Генерируем ответ
    logger.debug("Генерируем ответ")
    answer = generate_answer(query, relevant_items)
    logger.debug("Ответ получен")
    
    return answer

def process_query_with_keywords(query: str, keywords: List[str], top_k: int = None, root_id: str = None, parent_context: int = 0, child_context: int = 0) -> str:
    """
    Обрабатывает пользовательский запрос с использованием ключевых слов для поиска контекста
    """
    logger = logging.getLogger('process_query')
    
    # Используем значения из настроек, если не указаны явно
    if top_k is None:
        top_k = SEARCH_SETTINGS['top_k']
    
    # Получаем выборку элементов на основе ключевых слов
    logger.debug(f"Поиск элементов по ключевым словам: {keywords}")
    ensure_text_search_index()  # Создаем индекс, если его нет
    items = search_by_keywords(keywords, SEARCH_SETTINGS['sample_size'], root_id, max_depth=0)  # Явно передаем max_depth=0
    logger.debug(f"Найдено {len(items)} элементов по ключевым словам")
    
    # Создаем словарь для быстрого поиска ID по тексту
    text_to_id_map = {}
    for item in items:
        item_id = item['item'][0] if 'item' in item and len(item['item']) > 0 else 'Нет ID'
        text = item['item'][2] if 'item' in item and len(item['item']) > 2 else ''
        # Сохраняем соответствие между текстом и ID
        text_to_id_map[text] = item_id
    
    # Вывод информации о найденных документах до генерации эмбеддингов
    if DEBUG['enabled']:
        print("\nНайденные документы по ключевым словам:")
        for i, item in enumerate(items, 1):
            print(f"\n--- Документ {i} ---")
            item_id = item['item'][0] if 'item' in item and len(item['item']) > 0 else 'Нет ID'
            text = item['item'][2] if 'item' in item and len(item['item']) > 2 else ''
            if len(text) > DEBUG['truncate_output']:
                text = text[:DEBUG['truncate_output']] + "..."
            print(f"ID: {item_id}")
            print(f"Текст: {text}")
    
    # Если по ключевым словам ничего не найдено, используем стандартную выборку
    if not items:
        logger.debug(f"По ключевым словам ничего не найдено, используем стандартную выборку")
        items = get_items_sample(1, SEARCH_SETTINGS['sample_size'], root_id=root_id)
    
    # Преобразуем формат элементов
    converted_items = convert_item_format(items)
    
    # Обновляем словарь для быстрого поиска ID по тексту
    text_to_id_map = {item['text']: item['id'] for item in converted_items}
    
    # Ищем релевантные элементы
    logger.debug(f"Ищем {top_k} релевантных элементов")
    relevant_items = search_similar_items(query, converted_items, top_k)
    logger.debug(f"Найдено {len(relevant_items)} релевантных элементов")
    
    # В режиме отладки показываем найденные элементы
    if DEBUG['enabled']:
        print("\nНайденные релевантные элементы:")
        for i, item in enumerate(relevant_items, 1):
            print(f"\n--- Элемент {i} (сходство: {item['similarity']:.4f}) ---")
            
            # Получаем ID из словаря текстов
            text = item.get('text', '')
            
            # Ищем ID по тексту
            item_id = text_to_id_map.get(text, 'Нет ID')
            
            print(f"ID: {item_id}")
            
            if len(text) > DEBUG['truncate_output']:
                text = text[:DEBUG['truncate_output']] + "..."
            print(text)
            
            # Добавляем расширенную информацию в расширенном режиме отладки
            if DEBUG.get('extended', False):
                print(f"Путь: {item.get('path', 'Нет информации о пути')}")
                if 'metadata' in item:
                    print("Метаданные:", item['metadata'])
    
    # Генерируем ответ
    logger.debug("Генерируем ответ")
    answer = generate_answer(query, relevant_items)
    logger.debug("Ответ получен")
    
    return answer

def main():
    parser = argparse.ArgumentParser(description='MaymunAI - Ваш персональный ассистент')
    parser.add_argument('-d', '--debug', action='store_true', help='Включить режим отладки')
    parser.add_argument('-dd', '--debug_extended', action='store_true', help='Расширенный режим отладки')
    parser.add_argument('-i', '--info', action='store_true', help='Режим просмотра информации о блоках')
    parser.add_argument('-n', '--name', help='Поиск блока по названию')
    parser.add_argument('-b', '--block-id', help='ID блока для просмотра информации')
    parser.add_argument('-r', '--roots', nargs='+', help='Корневые маркеры для поиска')
    parser.add_argument('-v', '--view-tree', action='store_true', help='Показать дерево элементов')
    parser.add_argument('-s', '--search', help='Поиск по тексту в базе данных')
    parser.add_argument('-c', '--context', type=int, default=2, help='Размер контекста при поиске')
    parser.add_argument('--clear-cache', action='store_true', help='Очистить кэш эмбеддингов')
    parser.add_argument('--preload', action='store_true', help='Предзагрузить эмбеддинги частых запросов')
    parser.add_argument('--migrate', action='store_true', help='Обновить структуру базы данных')
    parser.add_argument('--rebuild-tables', action='store_true', help='Полностью перестроить таблицы эмбеддингов')
    parser.add_argument('--parent-context', type=int, default=0, 
                        help='Количество уровней родительского контекста (0 - отключено)')
    parser.add_argument('--child-context', type=int, default=0, 
                        help='Количество уровней дочернего контекста (0 - отключено)')
    parser.add_argument('--clear-invalid', action='store_true', 
                       help='Очистить эмбеддинги с неправильной размерностью')
    args = parser.parse_args()
    
    # Настройка логгирования и режима отладки
    setup_logging(args.debug or args.debug_extended)
    DEBUG['enabled'] = args.debug or args.debug_extended
    DEBUG['extended'] = args.debug_extended  # Добавляем флаг расширенной отладки
    logger = logging.getLogger('main')
    
    # Создаем таблицы, если их нет
    try:
        from db import create_embeddings_table, create_query_embeddings_table
        create_embeddings_table()
        create_query_embeddings_table()
    except Exception as e:
        logger.error(f"Ошибка при инициализации базы данных: {str(e)}")
    
    if args.debug or args.debug_extended:
        logger.info("Запуск в режиме отладки")
        
        # Базовый режим отладки для обоих флагов
        try:
            # Минимальная отладочная информация для обоих режимов
            pass
        except Exception as e:
            logger.error(f"Ошибка при отладке базы данных: {str(e)}")
            
        # Расширенный режим отладки только для -dd
        if args.debug_extended:
            try:
                from db import debug_database, get_table_structure
                debug_database()
                get_table_structure()
            except Exception as e:
                logger.error(f"Ошибка при расширенной отладке базы данных: {str(e)}")
    
    if args.info:
        if args.name:
            # Поиск блока по названию
            blocks = get_block_info_by_name(args.name)
            if not blocks:
                print(f"\nБлоки с названием '{args.name}' не найдены")
            else:
                print(f"\nНайдено {len(blocks)} блоков:")
                for block in blocks:
                    print_block_info(block)
                    
                # Предлагаем выбрать блок для детального просмотра
                if len(blocks) > 1:
                    block_id = input("\nВведите ID блока для детального просмотра (или Enter для пропуска): ").strip()
                    if block_id:
                        block_info = get_block_info_by_id(block_id)
                        if block_info:
                            print_block_info(block_info)
                        else:
                            print(f"Блок с ID {block_id} не найден")
        
        elif args.block_id:
            # Просмотр информации по ID
            block_info = get_block_info_by_id(args.block_id)
            if block_info:
                print_block_info(block_info)
            else:
                print(f"Блок с ID {args.block_id} не найден")
        
        else:
            print("Укажите название блока (-n) или его ID (-b)")
            return
            
        return  # Завершаем работу после просмотра информации
    
    # Используем пользовательские корневые маркеры
    root_markers = args.roots if args.roots else None
    
    if args.view_tree:
        if args.block_id:
            print("\nПросмотр дерева для корневого элемента:")
            view_item_tree(args.block_id)
        else:
            print("\nДоступные корневые элементы:")
            view_root_items(root_markers)
            
            if confirm_action("\nХотите выбрать корневой элемент? (да/нет): "):
                args.block_id = input("Введите ID корневого элемента: ").strip()
    
    if args.search:
        print(f"\nПоиск: '{args.search}'")
        results = search_text(args.search, args.context)
        if results:
            print_search_results(results)
            if confirm_action("\nИспользовать один из найденных элементов как корневой? (да/нет): "):
                args.block_id = input("ID: ").strip()
        else:
            print("Ничего не найдено")
            return
    
    print("\nMaymunAI - Ваш персональный ассистент")
    print("Для выхода введите 'exit', 'quit' или 'выход'")
    print("Для перезапуска диалога введите 'начало'\n")
    
    if root_markers:
        print(f"Используются корневые маркеры: {', '.join(root_markers)}")
    if args.block_id:
        print(f"Используется корневой элемент: {args.block_id}")
    print()
    
    # Очистка кэша эмбеддингов
    if args.clear_cache:
        try:
            from db import clear_embeddings_table
            if clear_embeddings_table():
                print("Кэш эмбеддингов успешно очищен")
            return
        except Exception as e:
            logger.error(f"Ошибка при очистке кэша эмбеддингов: {str(e)}")
    
    # Предзагрузка частых запросов
    if args.preload:
        try:
            from preload_embeddings import preload_query_embeddings
            print("Запуск предзагрузки эмбеддингов частых запросов...")
            preload_query_embeddings()
            print("Предзагрузка завершена")
            return
        except Exception as e:
            logger.error(f"Ошибка при предзагрузке запросов: {str(e)}")
    
    # Обновление структуры базы данных
    if args.migrate:
        try:
            from migration import migrate_database
            print("Обновление структуры базы данных...")
            if migrate_database():
                print("Структура базы данных успешно обновлена")
            return
        except Exception as e:
            logger.error(f"Ошибка при обновлении базы данных: {str(e)}")
    
    # Перестроение таблиц эмбеддингов
    if args.rebuild_tables:
        try:
            from db import rebuild_tables
            print("ВНИМАНИЕ: Все таблицы эмбеддингов и их данные будут удалены и созданы заново.")
            confirm = input("Продолжить? (да/нет): ").strip().lower()
            if confirm in ['да', 'д', 'yes', 'y']:
                if rebuild_tables():
                    print("Таблицы эмбеддингов успешно перестроены")
                return
        except Exception as e:
            logger.error(f"Ошибка при перестроении таблиц: {str(e)}")
    
    # Очистка эмбеддингов с неправильной размерностью
    if args.clear_invalid:
        try:
            from db import clear_invalid_embeddings
            print("Очистка эмбеддингов с неправильной размерностью...")
            count = clear_invalid_embeddings()
            if count >= 0:
                print(f"Очистка завершена. Удалено эмбеддингов: {count}")
            return
        except Exception as e:
            logger.error(f"Ошибка при очистке эмбеддингов: {str(e)}")
    
    # Инициализируем переменную для хранения последнего запроса
    last_query = "Что такое бытие?"
    # Внешний цикл для обработки команды "начало"
    restart_dialog = True

    while restart_dialog:
        # Перезапуск диалога, не сбрасываем флаг здесь
        # ... existing code ...
        
        # Устанавливаем начальное значение запроса при каждом перезапуске
        last_query = "Что такое бытие?"
        
        while True:
            # Используем последний запрос вместо статического текста
            query = input(f"\nВведите ваш вопрос [{last_query}]: ").strip()
            
            if not query:
                query = last_query
            else:
                # Запоминаем новый запрос, только если он не пустой
                last_query = query
                
            if query.lower() in ['exit', 'quit', 'выход']:
                # Не нужно сбрасывать флаг restart_dialog, так как return завершит функцию
                print("\nЗавершение работы...")
                return  # Полностью выходим из функции main
            
            if query.lower() == 'начало':
                print("\nПерезапуск диалога...\n")
                print("MaymunAI - Ваш персональный ассистент")
                print("Для выхода введите 'exit', 'quit' или 'выход'")
                print("Для перезапуска диалога введите 'начало'\n")
                restart_dialog = True
                break
            
            # Запрос ключевых слов    
            keywords = input("Введите ключевые слова или фразы через запятую для поиска контекста: ").strip()
            
            try:
                logger.debug(f"Обработка запроса: {query}")
                logger.debug(f"Ключевые слова: {keywords}")
                
                if keywords:
                    keywords_list = [k.strip() for k in keywords.split(',') if k.strip()]
                    answer = process_query_with_keywords(
                        query, 
                        keywords_list, 
                        root_id=args.block_id,
                        parent_context=args.parent_context,
                        child_context=args.child_context
                    )
                else:
                    # Если ключевые слова не указаны, используем модель для их генерации
                    keywords_list = generate_keywords_for_query(query)
                    logger.info(f"Автоматически подобранные ключевые слова: {', '.join(keywords_list)}")
                    print(f"\nАвтоматически подобранные ключевые слова: {', '.join(keywords_list)}")

                    # Даем возможность пользователю отредактировать ключевые слова
                    edit_keywords = input("Хотите отредактировать ключевые слова? (да/нет): ").strip().lower()
                    if edit_keywords in ['да', 'д', 'yes', 'y']:
                        edited_keywords = input(f"Введите новые ключевые слова через запятую [{', '.join(keywords_list)}]: ").strip()
                        if edited_keywords:
                            keywords_list = [k.strip() for k in edited_keywords.split(',') if k.strip()]

                    print(f"Используем ключевые слова: {', '.join(keywords_list)}")
                    answer = process_query_with_keywords(
                        query, 
                        keywords_list, 
                        root_id=args.block_id,
                        parent_context=args.parent_context,
                        child_context=args.child_context
                    )
                    
                print("\nОтвет:", answer)
            except Exception as e:
                logger.error(f"Ошибка при обработке запроса: {str(e)}", exc_info=args.debug or args.debug_extended)
                print(f"\nПроизошла ошибка: {str(e)}")

    # Выводим отладочную информацию о БД только в расширенном режиме отладки
    if args.debug_extended:
        try:
            print("\nОтладочная информация о базе данных:")
            db_analyzer.analyze_database(verbose=True)
        except Exception as e:
            logger.error(f"Ошибка при анализе базы данных: {str(e)}", exc_info=True)
            print(f"\nОшибка при анализе базы данных: {str(e)}")

if __name__ == '__main__':
    main() 