"""DB adapters package."""

# Импорт функций из корневого db.py для обратной совместимости
import sys
import os
import importlib.util

# Загружаем корневой db.py как модуль
spec = importlib.util.spec_from_file_location("db_module", os.path.join(os.path.dirname(os.path.dirname(__file__)), "db.py"))
db_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(db_module)

# Импортируем функции
get_items_sample = db_module.get_items_sample
view_item_tree = db_module.view_item_tree
view_root_items = db_module.view_root_items
search_text = db_module.search_text
print_search_results = db_module.print_search_results
get_block_info_by_name = db_module.get_block_info_by_name
get_block_info_by_id = db_module.get_block_info_by_id
print_block_info = db_module.print_block_info
ensure_text_search_index = db_module.ensure_text_search_index
search_by_keywords = db_module.search_by_keywords
create_embeddings_table = db_module.create_embeddings_table
create_query_embeddings_table = db_module.create_query_embeddings_table
clear_embeddings_table = db_module.clear_embeddings_table
rebuild_tables = db_module.rebuild_tables
clear_invalid_embeddings = db_module.clear_invalid_embeddings

