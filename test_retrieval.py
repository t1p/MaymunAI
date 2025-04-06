import unittest
from unittest.mock import patch, MagicMock
import numpy as np
from retrieval import search_similar_items, bm25_search

class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.items = [
            {'id': 1, 'text': 'машинное обучение и искусственный интеллект', 'item': ['ML']},
            {'id': 2, 'text': 'глубокое обучение нейронных сетей', 'item': ['DL']},
            {'id': 3, 'text': 'обработка естественного языка', 'item': ['NLP']}
        ]
        self.query = "машинное обучение"
        
    def test_bm25_search(self):
        results = bm25_search(self.query, self.items)
        self.assertEqual(len(results), 3)
        self.assertTrue(results[0]['score'] > results[1]['score'])
        
    def test_hybrid_search(self):
        # Мокаем get_embedding и calculate_similarity для тестов
        with patch('retrieval.get_embedding', return_value=np.array([0.1, 0.2])):
            with patch('retrieval.calculate_similarity', side_effect=[0.9, 0.5, 0.3]):
                with patch('retrieval.bm25_search', return_value=[
                    {'item': self.items[0], 'score': 0.8},
                    {'item': self.items[1], 'score': 0.6},
                    {'item': self.items[2], 'score': 0.4}
                ]):
                    results = search_similar_items(
                        self.query,
                        self.items,
                        use_hybrid=True,
                        vector_weight=0.5,
                        bm25_weight=0.5
                    )

                    self.assertEqual(len(results), 3)
                    self.assertTrue(all('combined_score' in r for r in results))
                self.assertTrue(results[0]['combined_score'] > results[1]['combined_score'])
                
    def test_backward_compatibility(self):
        # Проверяем работу без гибридного поиска
        with patch('retrieval.get_embedding', return_value=np.array([0.1, 0.2])):
            with patch('retrieval.calculate_similarity', side_effect=[0.9, 0.5, 0.3]):
                results = search_similar_items(
                    self.query, 
                    self.items,
                    use_hybrid=False
                )
                
                self.assertEqual(len(results), 3)
                self.assertTrue(results[0]['similarity'] > results[1]['similarity'])

if __name__ == '__main__':
    unittest.main()