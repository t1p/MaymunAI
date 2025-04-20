import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from retrieval import search_similar_items, bm25_search, rerank_with_cross_encoder

class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.items = [
            {
                'id': 1,
                'text': 'машинное обучение и искусственный интеллект',
                'item': [1, 'ML', 'машинное обучение и искусственный интеллект'],
                'embeddings': [{'embedding': np.array([0.1, 0.2])}]
            },
            {
                'id': 2,
                'text': 'глубокое обучение нейронных сетей',
                'item': [2, 'DL', 'глубокое обучение нейронных сетей'],
                'embeddings': [{'embedding': np.array([0.3, 0.4])}]
            },
            {
                'id': 3,
                'text': 'обработка естественного языка',
                'item': [3, 'NLP', 'обработка естественного языка'],
                'embeddings': [{'embedding': np.array([0.5, 0.6])}]
            }
        ]
        self.query = "машинное обучение"
        
    def test_bm25_search(self):
        results = bm25_search(self.query, self.items)
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0]['score'] > results[1]['score'])
        
    def test_hybrid_search(self):
        # Мокаем внешние зависимости
        with patch('config_db.get_threshold', return_value=0.1):
            with patch('retrieval.get_embedding', return_value=np.array([0.1, 0.2])):
                with patch('retrieval.calculate_similarity', side_effect=[0.9, 0.5, 0.3]):
                    with patch('retrieval.SEARCH_SETTINGS', {
                        'similarity_threshold': 0.01,  # Уменьшаем порог для тестирования
                        'top_k': 10,
                        'hybrid_search_weights': {
                            'vector': 0.5,
                            'bm25': 0.5
                        }
                    }):
                        with patch('retrieval.create_embedding_for_item', side_effect=[
                            {
                                'text': self.items[0]['text'],
                                'embeddings': [{'embedding': np.array([0.1, 0.2])}],
                                'id': self.items[0]['id']
                            },
                            {
                                'text': self.items[1]['text'],
                                'embeddings': [{'embedding': np.array([0.3, 0.4])}],
                                'id': self.items[1]['id']
                            },
                            {
                                'text': self.items[2]['text'],
                                'embeddings': [{'embedding': np.array([0.5, 0.6])}],
                                'id': self.items[2]['id']
                            }
                        ]):
                            with patch('retrieval.bm25_search', return_value=[
                                {
                                    'item': [self.items[0]['id'], 'ML', self.items[0]['text']],
                                    'score': 0.8,
                                    'text': self.items[0]['text']
                                },
                                {
                                    'item': [self.items[1]['id'], 'DL', self.items[1]['text']],
                                    'score': 0.6,
                                    'text': self.items[1]['text']
                                },
                                {
                                    'item': [self.items[2]['id'], 'NLP', self.items[2]['text']],
                                    'score': 0.4,
                                    'text': self.items[2]['text']
                                }
                            ]):
                                # Тестируем с use_reranker=False (по умолчанию)
                                with self.assertLogs('retrieval', level='INFO') as logs:
                                    results = search_similar_items(
                                        self.query,
                                        self.items,
                                        use_hybrid=True,
                                        vector_weight=0.5,
                                        bm25_weight=0.5,
                                        use_reranker=False
                                    )
                                    
                                    # Проверяем что поиск выполнен и возвращены результаты
                                    self.assertEqual(len(results), 3)
                                    self.assertTrue(all('combined_score' in r for r in results))
                                    # Проверяем что реранжирование не вызывалось
                                    self.assertFalse(any("rerank" in log.lower() for log in logs.output))
                                
                                # Тестируем с невалидными данными
                                with self.assertRaises(ValueError):
                                    search_similar_items("", self.items)  # Пустой запрос
                                
                                with self.assertRaises(ValueError):
                                    search_similar_items(self.query, "not a list")  # Не список
                                
                                # Тестируем с частично невалидными данными
                                mixed_items = self.items + [
                                    {},  # Пустой элемент
                                    {'id': 4, 'text': ''},  # Пустой текст
                                    {'id': 5, 'item': 'invalid'}  # Неправильный формат
                                ]

                                with self.assertLogs('retrieval', level='WARNING') as warn_logs:
                                    results = search_similar_items(
                                        self.query,
                                        mixed_items,
                                        use_hybrid=True,
                                        vector_weight=0.5,
                                        bm25_weight=0.5,
                                        use_reranker=False
                                    )
                                    # Проверяем что вернулись только валидные элементы из исходного списка
                                    self.assertEqual(len(results), len(self.items))
                                    # Проверяем что были логи о пропущенных элементах
                                    self.assertTrue(any("Invalid item skipped" in log for log in warn_logs.output))
                                    self.assertTrue(any("invalid items skipped" in log for log in warn_logs.output))

                            # Добавляем расширенный отладочный вывод
                            print("\nDebug results:")
                            print(f"Number of results: {len(results)}")
                            if results:
                                for i, r in enumerate(results):
                                    print(f"\nResult {i+1}:")
                                    print(f"Item: {r.get('item', {}).get('id', 'N/A')}")
                                    print(f"Similarity: {r.get('similarity', 'N/A')}")
                                    print(f"Combined score: {r.get('combined_score', 'N/A')}")
                                    print(f"BM25 score: {r.get('bm25_score', 'N/A')}")
                            else:
                                print("No results returned")
                            
                            print("\nMocked data check:")
                            print(f"Items count: {len(self.items)}")
                            print(f"First item keys: {self.items[0].keys()}")
                            
                            self.assertEqual(len(results), 3, "Expected 3 results")
                            if results:
                                self.assertTrue(all('combined_score' in r for r in results), "Missing combined_score")
                                self.assertTrue(results[0]['combined_score'] > results[1]['combined_score'], "Incorrect sorting")
                        
                            # Тестируем с use_reranker=True
                            def mock_reranker(query, items, **kwargs):
                                print("\nMock reranker called with:")
                                print(f"Query: {query}")
                                print(f"Items count: {len(items)}")
                                if items:
                                    print(f"First item type: {type(items[0])}")
                                    print(f"First item keys: {items[0].keys()}")
                                
                                # Обрабатываем оба формата входных данных
                                processed_items = []
                                for item in items if items else self.items[:3]:
                                    # Поддерживаем оба формата - dict и list
                                    if isinstance(item.get('item', None), dict):
                                        processed_item = {
                                            'item': item['item'],
                                            'text': item['text'],
                                            'rerank_score': 0.9 if item['item']['id'] == 1 else
                                                          (0.6 if item['item']['id'] == 2 else 0.3)
                                        }
                                    else:
                                        processed_item = {
                                            'item': {'id': item['item'][0], 'text': item['item'][2]},
                                            'text': item['text'],
                                            'rerank_score': 0.9 if item['item'][0] == 1 else
                                                          (0.6 if item['item'][0] == 2 else 0.3)
                                        }
                                    processed_items.append(processed_item)
                                
                                return processed_items
                            
                            with patch('retrieval.rerank_with_cross_encoder', side_effect=mock_reranker):
                                results = search_similar_items(
                                    self.query,
                                    self.items,
                                    use_hybrid=True,
                                    vector_weight=0.4,
                                    bm25_weight=0.3,
                                    rerank_weight=0.3,
                                    use_reranker=True
                                )

                                # Добавляем отладочный вывод для реранжирования
                                print("\nReranking debug results:")
                                print(f"Number of results: {len(results)}")
                                if results:
                                    for i, r in enumerate(results):
                                        print(f"\nResult {i+1}:")
                                        print(f"Item: {r.get('item', {}).get('id', 'N/A')}")
                                        print(f"Similarity: {r.get('similarity', 'N/A')}")
                                        print(f"Combined score: {r.get('combined_score', 'N/A')}")
                                        print(f"BM25 score: {r.get('bm25_score', 'N/A')}")
                                        print(f"Rerank score: {r.get('rerank_score', 'N/A')}")
                                else:
                                    print("No results returned after reranking")

                                self.assertEqual(len(results), 3, "Expected 3 results after reranking")
                                self.assertTrue(all('combined_score' in r for r in results))
                                self.assertTrue(results[0]['combined_score'] > results[1]['combined_score'])
                
    def test_backward_compatibility(self):
        # Проверяем работу без гибридного поиска
        with patch('retrieval.get_embedding', return_value=np.array([0.1, 0.2])):
            with patch('retrieval.calculate_similarity', side_effect=[0.9, 0.5, 0.3]):
                with patch('retrieval.create_embedding_for_item', side_effect=[
                    {
                        'text': self.items[0]['text'],
                        'embeddings': [{'embedding': np.array([0.1, 0.2])}],
                        'id': self.items[0]['id']
                    },
                    {
                        'text': self.items[1]['text'],
                        'embeddings': [{'embedding': np.array([0.3, 0.4])}],
                        'id': self.items[1]['id']
                    },
                    {
                        'text': self.items[2]['text'],
                        'embeddings': [{'embedding': np.array([0.5, 0.6])}],
                        'id': self.items[2]['id']
                    }
                ]):
                    with self.assertLogs('retrieval', level='DEBUG') as cm:
                        results = search_similar_items(
                            self.query,
                            self.items,
                            use_hybrid=False
                        )
                        
                        self.assertEqual(len(results), 3)
                        self.assertTrue(results[0]['similarity'] > results[1]['similarity'])
                        self.assertTrue(any("Используется пороговое значение" in log for log in cm.output))

    def test_none_handling(self):
        """Тестирует обработку элементов с None значениями"""
        with patch('retrieval.get_embedding', return_value=np.array([0.1, 0.2])):
            with patch('retrieval.calculate_similarity', side_effect=[0.9, 0.5, 0.3]):
                with patch('retrieval.create_embedding_for_item', side_effect=[
                    {'text': self.items[0]['text'], 'embeddings': [{'embedding': np.array([0.1, 0.2])}]},
                    {'text': self.items[1]['text'], 'embeddings': [{'embedding': np.array([0.3, 0.4])}]},
                    {'text': self.items[2]['text'], 'embeddings': [{'embedding': np.array([0.5, 0.6])}]},
                    Exception("Cannot create embedding for None item")
                ]):
                    # Добавляем элемент с None значениями
                    items_with_none = self.items + [
                        {
                            'id': 4,
                            'text': None,
                            'item': None,
                            'embeddings': None
                        }
                    ]
                    
                    # Проверяем, что функция корректно обрабатывает None
                    results = search_similar_items(
                        self.query,
                        items_with_none,
                        use_hybrid=False
                    )
                    
                    # Должны вернуться только валидные элементы
                    self.assertEqual(len(results), 3)
                    self.assertTrue(all(r['item']['id'] in {1, 2, 3} for r in results))
                    
                    # Проверяем логирование ошибок
                    with self.assertLogs('retrieval', level='WARNING') as cm:
                        search_similar_items(
                            self.query,
                            [{'id': 5}],  # Элемент без обязательных полей
                            use_hybrid=False
                        )
                    self.assertTrue(any("Ошибка при обработке элемента" in log for log in cm.output))
    
    def test_empty_input(self):
        """Тестирует работу с пустыми входными данными"""
        with patch('retrieval.get_embedding', return_value=np.array([0.1, 0.2])):
            # Пустой список элементов
            with self.assertLogs('retrieval', level='WARNING') as logs:
                results = search_similar_items(
                    self.query,
                    [],
                    use_hybrid=False
                )
                self.assertEqual(len(results), 0)
                self.assertTrue(any("empty items list" in log for log in logs.output))
            
            # None вместо списка элементов
            with self.assertRaises(ValueError):
                search_similar_items(
                    self.query,
                    None,
                    use_hybrid=False
                )

    def test_reranker_formats_and_logging(self):
        """Тестирует обработку разных форматов данных и логирование"""
        test_items = [
            # Стандартный формат
            {'id': 1, 'text': 'текст 1', 'item': {'id': 1, 'text': 'текст 1'}},
            # Формат списка
            {'id': 2, 'item': [2, 'T2', 'текст 2']},
            # Неполный формат
            {'id': 3, 'item': 'неправильный формат'},
            # Пустой элемент
            {},
            # Элемент без текста
            {'id': 4, 'item': {'id': 4}}
        ]
        
        with patch('retrieval.FlagReranker') as mock_reranker:
            mock_reranker.return_value.compute_score.return_value = [0.9, 0.8]
            
            with self.assertLogs('retrieval', level='INFO') as logs:
                results = rerank_with_cross_encoder(
                    "тестовый запрос",
                    test_items,
                    top_k=2
                )
                
                # Проверяем что вернулись только валидные элементы
                self.assertEqual(len(results), 2)
                self.assertEqual(results[0]['item']['id'], 1)
                self.assertEqual(results[1]['item'][0], 2)
                
                # Проверяем логирование
                self.assertTrue(any("Starting reranking" in log for log in logs.output))
                self.assertTrue(any("invalid items skipped" in log for log in logs.output))
                self.assertTrue(any("Reranking completed" in log for log in logs.output))

if __name__ == '__main__':
    unittest.main()