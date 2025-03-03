from typing import List, Dict, Any
import argparse
import logging
from db import get_items_sample, view_item_tree, view_root_items, search_text, print_search_results, get_block_info_by_name, get_block_info_by_id, print_block_info
from retrieval import search_similar_items
from rag import generate_answer
from config import DEBUG, SEARCH_SETTINGS, RAG_SETTINGS
from debug_utils import confirm_action, debug_step

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
    
    # Ищем релевантные элементы
    logger.debug(f"Ищем {top_k} релевантных элементов")
    relevant_items = search_similar_items(query, items, top_k)
    logger.debug(f"Найдено {len(relevant_items)} релевантных элементов")
    
    # В режиме отладки показываем найденные элементы
    if DEBUG['enabled']:
        print("\nНайденные релевантные элементы:")
        for i, item in enumerate(relevant_items, 1):
            print(f"\n--- Элемент {i} (сходство: {item['similarity']:.4f}) ---")
            print(item['text'][:200] + "..." if len(item['text']) > 200 else item['text'])
    
    # Генерируем ответ
    logger.debug("Генерируем ответ")
    answer = generate_answer(query, relevant_items)
    logger.debug("Ответ получен")
    
    return answer

def main():
    parser = argparse.ArgumentParser(description='MaymunAI - Ваш персональный ассистент')
    parser.add_argument('-d', '--debug', action='store_true', help='Включить режим отладки')
    parser.add_argument('-i', '--info', action='store_true', help='Режим просмотра информации о блоках')
    parser.add_argument('-n', '--name', help='Поиск блока по названию')
    parser.add_argument('-b', '--block-id', help='ID блока для просмотра информации')
    parser.add_argument('-r', '--roots', nargs='+', help='Корневые маркеры для поиска')
    parser.add_argument('-v', '--view-tree', action='store_true', help='Показать дерево элементов')
    parser.add_argument('-s', '--search', help='Поиск по тексту в базе данных')
    parser.add_argument('-c', '--context', type=int, default=2, help='Размер контекста при поиске')
    args = parser.parse_args()
    
    # Настройка логгирования и режима отладки
    setup_logging(args.debug)
    DEBUG['enabled'] = args.debug
    logger = logging.getLogger('main')
    
    if args.debug:
        logger.info("Запуск в режиме отладки")
        try:
            from db import debug_database, get_table_structure
            debug_database()
            get_table_structure()  # Добавляем вывод структуры таблицы
        except Exception as e:
            logger.error(f"Ошибка при отладке базы данных: {str(e)}")
    
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
    print("Для выхода введите 'exit' или 'quit'\n")
    
    if root_markers:
        print(f"Используются корневые маркеры: {', '.join(root_markers)}")
    if args.block_id:
        print(f"Используется корневой элемент: {args.block_id}")
    print()
    
    while True:
        default_query = "Как меня зовут?"
        query = input(f"\nВведите ваш вопрос [{default_query}]: ").strip()
        
        if not query:
            query = default_query
            
        if query.lower() in ['exit', 'quit']:
            break
            
        try:
            logger.debug(f"Обработка запроса: {query}")
            answer = process_query(query, root_id=args.block_id)
            print("\nОтвет:", answer)
        except Exception as e:
            logger.error(f"Ошибка при обработке запроса: {str(e)}", exc_info=args.debug)
            print(f"\nПроизошла ошибка: {str(e)}")

if __name__ == '__main__':
    main() 