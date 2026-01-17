"""Тест-кейсы для интеграции MCP: проверка синтаксиса, структуры, импортов."""

import ast
import sys
from pathlib import Path

# Файлы для тестирования
FILES_TO_TEST = [
    "core/mcp_server.py",
    "db/pg_mcp_client.py",
    "db/schema_introspect.py"
]

def test_syntax():
    """Проверить синтаксис всех файлов."""
    for file_path in FILES_TO_TEST:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        try:
            ast.parse(source)
            print(f"✓ Синтаксис {file_path} корректен")
        except SyntaxError as e:
            print(f"✗ Синтаксис {file_path} ошибочен: {e}")
            return False
    return True

def test_structure():
    """Проверить базовую структуру кода."""
    # core/mcp_server.py
    with open("core/mcp_server.py", 'r') as f:
        tree = ast.parse(f.read())

    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    expected_functions = ["tool_retrieval", "tool_info_schema", "run_mcp_server"]
    for func in expected_functions:
        if func not in functions:
            print(f"✗ Функция {func} отсутствует в core/mcp_server.py")
            return False

    # Проверка TOOLS
    tools_found = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            target = node.targets[0] if isinstance(node, ast.Assign) else node.target
            if isinstance(target, ast.Name) and target.id == "TOOLS":
                tools_found = True
                break
    if not tools_found:
        print("✗ Переменная TOOLS отсутствует в core/mcp_server.py")
        return False

    print("✓ Структура core/mcp_server.py корректна")

    # db/pg_mcp_client.py
    with open("db/pg_mcp_client.py", 'r') as f:
        tree = ast.parse(f.read())

    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    expected_functions = ["list_tables", "fetch_documents", "fetch_by_text"]
    for func in expected_functions:
        if func not in functions:
            print(f"✗ Функция {func} отсутствует в db/pg_mcp_client.py")
            return False

    print("✓ Структура db/pg_mcp_client.py корректна")

    # db/schema_introspect.py
    with open("db/schema_introspect.py", 'r') as f:
        tree = ast.parse(f.read())

    functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    if "describe_schema" not in functions:
        print("✗ Функция describe_schema отсутствует в db/schema_introspect.py")
        return False

    print("✓ Структура db/schema_introspect.py корректна")

    return True

def test_imports():
    """Проверить импорты в файлах."""
    # Проверка импортов через AST
    for file_path in FILES_TO_TEST:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read())

        imports = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imports.extend(f"{module}.{alias.name}" if module else alias.name for alias in node.names)

        print(f"Импорты в {file_path}: {imports}")

        # Базовая проверка - импорты начинаются с правильных модулей
        for imp in imports:
            if imp.startswith("from __future__"):
                continue
            if imp.startswith("from typing"):
                continue
            # Остальные импорты должны быть относительными или известными
            if not (imp.startswith("db.") or imp.startswith("rag.") or imp in ["db", "rag"]):
                print(f"⚠ Неизвестный импорт: {imp} в {file_path}")

    return True

if __name__ == "__main__":
    print("Запуск тест-кейсов интеграции MCP...")
    results = []
    results.append(test_syntax())
    results.append(test_structure())
    results.append(test_imports())

    if all(results):
        print("✓ Все тест-кейсы пройдены")
        sys.exit(0)
    else:
        print("✗ Некоторые тест-кейсы не пройдены")
        sys.exit(1)