import unittest
from embeddings import semantic_chunking, create_embedding_for_item
import tiktoken

class TestSemanticChunking(unittest.TestCase):
    def setUp(self):
        self.long_text = """
        Раздел 1. Введение
        
        Это первый раздел документа. Он содержит вводную информацию.
        Здесь описываются основные понятия и цели документа.
        
        Раздел 2. Основная часть
        
        Этот раздел содержит основное содержание. Он разбит на несколько подразделов.
        Каждый подраздел посвящен отдельной теме.
        
        Подраздел 2.1. Первая тема
        
        Описание первой темы. Довольно длинный текст, который может быть разбит на несколько абзацев.
        
        Подраздел 2.2. Вторая тема
        
        Описание второй темы. Также содержит много текста.
        """
        
        self.short_text = "Короткий текст, который не требует разбиения."
        
    def test_chunking_long_text(self):
        chunks = semantic_chunking(self.long_text)
        self.assertGreater(len(chunks), 1)
        
        # Проверяем структуру чанков
        for chunk, metadata in chunks:
            self.assertIsInstance(chunk, str)
            self.assertIsInstance(metadata, dict)
            self.assertIn('type', metadata)
            self.assertIn('tokens', metadata)
            self.assertIn('is_complete', metadata)
            
    def test_chunking_short_text(self):
        chunks = semantic_chunking(self.short_text)
        self.assertEqual(len(chunks), 1)
        
    def test_chunk_overlap(self):
        chunks = semantic_chunking(self.long_text, overlap=0.2)
        if len(chunks) > 1:
            # Проверяем перекрытие между чанками
            prev_chunk = chunks[0][0]
            current_chunk = chunks[1][0]
            self.assertTrue(prev_chunk.endswith(current_chunk[:100]))
            
    def test_max_tokens(self):
        max_tokens = 100
        chunks = semantic_chunking(self.long_text, max_tokens=max_tokens)
        
        encoding = tiktoken.get_encoding("cl100k_base")
        for chunk, metadata in chunks:
            tokens = encoding.encode(chunk)
            self.assertLessEqual(len(tokens), max_tokens * 1.1)  # Допускаем 10% отклонение
            
    def test_create_embedding_chunked(self):
        item = {
            'item': ('test_id', None, self.long_text)
        }
        result = create_embedding_for_item(item, chunked=True)
        self.assertTrue(result['chunked'])
        self.assertGreater(len(result['embeddings']), 1)
        
    def test_create_embedding_not_chunked(self):
        item = {
            'item': ('test_id', None, self.short_text)
        }
        result = create_embedding_for_item(item, chunked=False)
        self.assertFalse(result['chunked'])
        self.assertIn('embedding', result)

if __name__ == '__main__':
    unittest.main()