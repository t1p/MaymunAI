import unittest
import sys
import os
import types
from unittest.mock import patch, MagicMock

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Импортируем модули напрямую, чтобы избежать зависимостей из rag/__init__.py
import importlib.util

def ensure_httpx_stub():
    if 'httpx' in sys.modules:
        return
    httpx_stub = types.ModuleType('httpx')

    class DummyClient:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, *args, **kwargs):
            raise RuntimeError("httpx is not installed")

    httpx_stub.Client = DummyClient
    sys.modules['httpx'] = httpx_stub


def load_module_from_path(module_name, file_path):
    ensure_httpx_stub()
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

fastgpt_module = load_module_from_path(
    "retriever_fastgpt",
    os.path.join(os.path.dirname(__file__), '..', 'rag', 'retriever_fastgpt.py'),
)
ragflow_module = load_module_from_path(
    "retriever_ragflow",
    os.path.join(os.path.dirname(__file__), '..', 'rag', 'retriever_ragflow.py'),
)


class TestRetrieverSyntax(unittest.TestCase):
    """Тесты на синтаксис и базовую структуру ретриверов."""

    def test_fastgpt_syntax(self):
        """Тест что модуль retriever_fastgpt импортируется без синтаксических ошибок."""
        try:
            load_module_from_path(
                "retriever_fastgpt_syntax",
                os.path.join(os.path.dirname(__file__), '..', 'rag', 'retriever_fastgpt.py'),
            )
            # Если импорт прошел, синтаксис в порядке
            self.assertTrue(True)
        except SyntaxError as e:
            self.fail(f"Syntax error in retriever_fastgpt.py: {e}")
        except ImportError as e:
            # ImportError может быть из-за зависимостей, но не синтаксиса
            self.fail(f"Import error in retriever_fastgpt.py: {e}")

    def test_ragflow_syntax(self):
        """Тест что модуль retriever_ragflow импортируется без синтаксических ошибок."""
        try:
            load_module_from_path(
                "retriever_ragflow_syntax",
                os.path.join(os.path.dirname(__file__), '..', 'rag', 'retriever_ragflow.py'),
            )
            self.assertTrue(True)
        except SyntaxError as e:
            self.fail(f"Syntax error in retriever_ragflow.py: {e}")
        except ImportError as e:
            self.fail(f"Import error in retriever_ragflow.py: {e}")


class TestRetrieverImports(unittest.TestCase):
    """Тесты на правильность импортов."""

    def test_fastgpt_imports(self):
        """Тест что все необходимые импорты в retriever_fastgpt работают."""
        # Проверяем что httpx импортирован
        self.assertTrue(hasattr(fastgpt_module, 'httpx') or 'httpx' in str(fastgpt_module.__dict__))

        # Проверяем что load_config импортирован
        self.assertTrue(hasattr(fastgpt_module, 'load_config'))

    def test_ragflow_imports(self):
        """Тест что все необходимые импорты в retriever_ragflow работают."""
        self.assertTrue(hasattr(ragflow_module, 'httpx') or 'httpx' in str(ragflow_module.__dict__))
        self.assertTrue(hasattr(ragflow_module, 'load_config'))


class TestRetrieverStructure(unittest.TestCase):
    """Тесты на структуру функций."""

    def test_fastgpt_retrieve_function_exists(self):
        """Тест что функция retrieve существует в retriever_fastgpt."""
        self.assertTrue(hasattr(fastgpt_module, 'retrieve'))
        self.assertTrue(callable(getattr(fastgpt_module, 'retrieve')))

    def test_ragflow_retrieve_function_exists(self):
        """Тест что функция retrieve существует в retriever_ragflow."""
        self.assertTrue(hasattr(ragflow_module, 'retrieve'))
        self.assertTrue(callable(getattr(ragflow_module, 'retrieve')))

    def test_fastgpt_retrieve_signature(self):
        """Тест сигнатуры функции retrieve в retriever_fastgpt."""
        import inspect
        sig = inspect.signature(fastgpt_module.retrieve)
        params = list(sig.parameters.keys())
        self.assertIn('query', params)
        self.assertIn('top_k', params)

    def test_ragflow_retrieve_signature(self):
        """Тест сигнатуры функции retrieve в retriever_ragflow."""
        import inspect
        sig = inspect.signature(ragflow_module.retrieve)
        params = list(sig.parameters.keys())
        self.assertIn('query', params)
        self.assertIn('top_k', params)


class TestRetrieverFunctionality(unittest.TestCase):
    """Тесты функциональности ретриверов с мокированием."""

    @patch.object(fastgpt_module, 'load_config')
    @patch.object(fastgpt_module.httpx, 'Client')
    def test_fastgpt_retrieve_success(self, mock_client_class, mock_load_config):
        """Тест успешного выполнения retrieve в retriever_fastgpt."""
        # Мокаем конфиг
        mock_config = MagicMock()
        mock_config.fastgpt.base_url = "http://test.com"
        mock_config.fastgpt.api_key = "test_key"
        mock_config.fastgpt.dataset_id = "test_dataset"
        mock_load_config.return_value = mock_config

        # Мокаем HTTP клиент
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"content": "test content", "score": 0.9, "source": {"url": "test.com"}}
            ]
        }
        mock_client.post.return_value = mock_response

        # Вызываем функцию
        result = fastgpt_module.retrieve("test query", top_k=5)

        # Проверяем результат
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], "test content")
        self.assertEqual(result[0]['score'], 0.9)

    @patch.object(ragflow_module, 'load_config')
    @patch.object(ragflow_module.httpx, 'Client')
    def test_ragflow_retrieve_success(self, mock_client_class, mock_load_config):
        """Тест успешного выполнения retrieve в retriever_ragflow."""
        # Мокаем конфиг
        mock_config = MagicMock()
        mock_config.ragflow.base_url = "http://test.com"
        mock_config.ragflow.api_key = "test_key"
        mock_config.ragflow.index = "test_index"
        mock_load_config.return_value = mock_config

        # Мокаем HTTP клиент
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__.return_value = mock_client
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [
                {"content": "test content", "score": 0.8, "citation": {"url": "test.com"}}
            ]
        }
        mock_client.post.return_value = mock_response

        # Вызываем функцию
        result = ragflow_module.retrieve("test query", top_k=5)

        # Проверяем результат
        self.assertIsInstance(result, list)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['text'], "test content")
        self.assertEqual(result[0]['score'], 0.8)


if __name__ == '__main__':
    unittest.main()
