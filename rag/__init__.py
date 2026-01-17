"""RAG package."""

# Импорт функций из корневого rag.py для обратной совместимости
import sys
import os
import importlib.util

# Загружаем корневой rag.py как модуль
spec = importlib.util.spec_from_file_location("rag_module", os.path.join(os.path.dirname(os.path.dirname(__file__)), "rag.py"))
rag_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rag_module)

# Импортируем функции
generate_answer = rag_module.generate_answer

