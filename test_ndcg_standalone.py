import unittest
import math

class TestNDCG(unittest.TestCase):
    def setUp(self):
        self.retrieved = [0, 1, 2]  # Результаты поиска системы
        self.relevance_scores = [3, 1, 2]  # Оценки релевантности
        
    def test_ndcg_at_k(self):
        """Тест расчета метрики NDCG@k"""
        def ndcg_at_k(retrieved, relevance_scores, k):
            """Вычисляет NDCG@k"""
            # Рассчитываем DCG
            dcg = 0.0
            for i in range(k):
                if i < len(retrieved):
                    rank = i + 1
                    doc_idx = retrieved[i]
                    rel = relevance_scores[doc_idx]
                    dcg += rel / math.log(rank + 1, 2)
                    
            # Рассчитываем IDCG (идеальное ранжирование)
            ideal_sorted = sorted(relevance_scores, reverse=True)
            idcg = 0.0
            for i in range(k):
                if i < len(ideal_sorted):
                    rank = i + 1
                    idcg += ideal_sorted[i] / math.log(rank + 1, 2)
                    
            return dcg / idcg if idcg > 0 else 0.0
            
        # Тест 1: NDCG@1
        self.assertAlmostEqual(
            ndcg_at_k(self.retrieved, self.relevance_scores, 1),
            1.0
        )
        
        # Тест 2: NDCG@2
        expected_ndcg_2 = (3 + 1/math.log(3, 2)) / (3 + 2/math.log(3, 2))
        self.assertAlmostEqual(
            ndcg_at_k(self.retrieved, self.relevance_scores, 2),
            expected_ndcg_2
        )
        
        # Тест 3: NDCG@3
        expected_ndcg_3 = (3 + 1/math.log(3, 2) + 2/math.log(4, 2)) / (3 + 2/math.log(3, 2) + 1/math.log(4, 2))
        self.assertAlmostEqual(
            ndcg_at_k(self.retrieved, self.relevance_scores, 3),
            expected_ndcg_3
        )

if __name__ == '__main__':
    unittest.main()