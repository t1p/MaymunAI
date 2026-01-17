import unittest
import os
import sys
import tempfile
from unittest.mock import patch, MagicMock

# Добавляем родительскую директорию в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from core.settings import load_config, AppConfig, ModeConfig, PostgresConfig, MCPConfig, FastGPTConfig, RAGFlowConfig, PromptsConfig, LoggingConfig


class TestConfigLoading(unittest.TestCase):

    def setUp(self):
        self.test_config = {
            "mode": {
                "db_access": "test_db_access",
                "retriever": "test_retriever",
                "run_as": "test_run_as"
            },
            "postgres": {
                "host": "test_host",
                "port": 9999,
                "dbname": "test_db",
                "user": "test_user",
                "password": "test_password",
                "schema": "test_schema",
                "use_pgvector": False
            },
            "mcp": {
                "pg_server": {
                    "command": "test_command",
                    "transport": "test_transport",
                    "args": ["arg1", "arg2"]
                }
            },
            "fastgpt": {
                "base_url": "http://test.fastgpt",
                "api_key": "test_api_key",
                "dataset_id": "test_dataset_id"
            },
            "ragflow": {
                "base_url": "http://test.ragflow",
                "api_key": "test_ragflow_key",
                "index": "test_index"
            },
            "prompts": {
                "pack": "test_pack",
                "preload_paths": ["path1", "path2"]
            },
            "logging": {
                "level": "DEBUG",
                "fmt": "test_fmt",
                "file": "test_log.log",
                "module_levels": {"test": "INFO"},
                "trace_id": False
            }
        }

    def test_load_config_success(self):
        """Тест успешной загрузки конфигурации из YAML файла"""
        import yaml

        # Создаем временный файл с тестовым конфигом
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.test_config, f)
            temp_file = f.name

        try:
            config = load_config(temp_file)

            # Проверяем тип результата
            self.assertIsInstance(config, AppConfig)

            # Проверяем парсинг mode
            self.assertEqual(config.mode.db_access, "test_db_access")
            self.assertEqual(config.mode.retriever, "test_retriever")
            self.assertEqual(config.mode.run_as, "test_run_as")

            # Проверяем парсинг postgres
            self.assertEqual(config.postgres.host, "test_host")
            self.assertEqual(config.postgres.port, 9999)
            self.assertEqual(config.postgres.dbname, "test_db")
            self.assertEqual(config.postgres.user, "test_user")
            self.assertEqual(config.postgres.password, "test_password")
            self.assertEqual(config.postgres.schema, "test_schema")
            self.assertEqual(config.postgres.use_pgvector, False)

            # Проверяем парсинг mcp
            self.assertEqual(config.mcp.pg_server.command, "test_command")
            self.assertEqual(config.mcp.pg_server.transport, "test_transport")
            self.assertEqual(config.mcp.pg_server.args, ["arg1", "arg2"])

            # Проверяем парсинг fastgpt
            self.assertEqual(config.fastgpt.base_url, "http://test.fastgpt")
            self.assertEqual(config.fastgpt.api_key, "test_api_key")
            self.assertEqual(config.fastgpt.dataset_id, "test_dataset_id")

            # Проверяем парсинг ragflow
            self.assertEqual(config.ragflow.base_url, "http://test.ragflow")
            self.assertEqual(config.ragflow.api_key, "test_ragflow_key")
            self.assertEqual(config.ragflow.index, "test_index")

            # Проверяем парсинг prompts
            self.assertEqual(config.prompts.pack, "test_pack")
            self.assertEqual(config.prompts.preload_paths, ["path1", "path2"])

            # Проверяем парсинг logging
            self.assertEqual(config.logging.level, "DEBUG")
            self.assertEqual(config.logging.fmt, "test_fmt")
            self.assertEqual(config.logging.file, "test_log.log")
            self.assertEqual(config.logging.module_levels, {"test": "INFO"})
            self.assertEqual(config.logging.trace_id, False)
        finally:
            os.unlink(temp_file)

    def test_load_config_env_overrides(self):
        """Тест применения переменных окружения"""
        import yaml

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(self.test_config, f)
            temp_file = f.name

        try:
            with patch.dict(os.environ, {
                'PG_PASSWORD': 'env_password',
                'FASTGPT_API_KEY': 'env_api_key',
                'FASTGPT_DATASET_ID': 'env_dataset_id',
                'RAGFLOW_API_KEY': 'env_ragflow_key'
            }):
                config = load_config(temp_file)

                # Проверяем применение env переменных
                self.assertEqual(config.postgres.password, "env_password")
                self.assertEqual(config.fastgpt.api_key, "env_api_key")
                self.assertEqual(config.fastgpt.dataset_id, "env_dataset_id")
                self.assertEqual(config.ragflow.api_key, "env_ragflow_key")
        finally:
            os.unlink(temp_file)

    def test_load_config_file_not_exists(self):
        """Тест загрузки когда файл не существует"""
        with patch('os.path.exists', return_value=False):
            config = load_config("nonexistent.yaml")

            # Должен вернуться дефолтный конфиг
            self.assertIsInstance(config, AppConfig)
            self.assertEqual(config.mode.db_access, "native_pg")  # дефолтное значение

    def test_load_config_yaml_none(self):
        """Тест загрузки когда PyYAML не установлен"""
        with patch('core.settings.yaml', None):
            config = load_config("test_config.yaml")

            # Должен вернуться дефолтный конфиг
            self.assertIsInstance(config, AppConfig)
            self.assertEqual(config.mode.db_access, "native_pg")

    def test_load_config_invalid_section(self):
        """Тест игнорирования неизвестных секций"""
        import yaml

        invalid_config = {
            "mode": {"db_access": "test"},
            "unknown_section": {"some": "value"}
        }

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(invalid_config, f)
            temp_file = f.name

        try:
            config = load_config(temp_file)

            # Неизвестная секция должна быть проигнорирована
            self.assertEqual(config.mode.db_access, "test")
            self.assertFalse(hasattr(config, 'unknown_section'))
        finally:
            os.unlink(temp_file)

    def test_load_config_partial_config(self):
        """Тест загрузки частичной конфигурации"""
        import yaml

        partial_config = {
            "mode": {"db_access": "partial"}
        }

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(partial_config, f)
            temp_file = f.name

        try:
            config = load_config(temp_file)

            # Частично загруженная конфигурация
            self.assertEqual(config.mode.db_access, "partial")
            # Остальные значения должны быть дефолтными
            self.assertEqual(config.mode.retriever, "RAG_NATIVE")
        finally:
            os.unlink(temp_file)

    def test_load_config_empty_yaml(self):
        """Тест загрузки пустого YAML файла"""
        import yaml

        # Создаем временный пустой файл
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({}, f)
            temp_file = f.name

        try:
            config = load_config(temp_file)

            # Должен вернуться дефолтный конфиг
            self.assertIsInstance(config, AppConfig)
            self.assertEqual(config.mode.db_access, "native_pg")
        finally:
            os.unlink(temp_file)

    def test_dataclass_defaults(self):
        """Тест дефолтных значений датаклассов"""
        config = AppConfig()

        self.assertEqual(config.mode.db_access, "native_pg")
        self.assertEqual(config.postgres.host, "localhost")
        self.assertEqual(config.postgres.port, 5432)
        self.assertEqual(config.fastgpt.base_url, "http://localhost:3000")
        self.assertEqual(config.logging.level, "INFO")
        self.assertTrue(config.logging.trace_id)


if __name__ == '__main__':
    unittest.main()
