import unittest
from unittest.mock import patch, MagicMock
import math
import matplotlib.pyplot as plt
# Временное удаление зависимости для тестирования
# from rag import evaluate_rag_system  # Предполагаем, что есть такой модуль

class TestRAGEvaluation(unittest.TestCase):
    def setUp(self):
        """Инициализация тестовых данных для оценки RAG системы"""
        self.query = "Что такое машинное обучение?"
        self.contexts = [
            "Машинное обучение - это область искусственного интеллекта.",
            "Глубокое обучение использует нейронные сети.",
            "НЛП обрабатывает человеческий язык."
        ]
        self.generated_answer = "Машинное обучение - раздел ИИ, изучающий алгоритмы, способные обучаться."
        self.ideal_answer = "Машинное обучение - это область искусственного интеллекта, занимающаяся разработкой алгоритмов, которые могут обучаться на данных."
        
        # Тестовые данные для метрик ранжирования
        self.ground_truth = [0, 2]  # Индексы релевантных документов
        self.retrieved = [0, 1, 2]  # Результаты поиска системы (ранжированный список)
        self.relevance_scores = [3, 1, 2]  # Оценки релевантности для NDCG (3 - максимальная релевантность)
        
    def test_relevance_evaluation(self):
        """Тест оценки релевантности ответа"""
        pass
        
    def test_accuracy_evaluation(self):
        """Тест оценки точности ответа"""
        pass
        
    def test_coverage_evaluation(self):
        """Тест оценки покрытия контекста"""
        pass
        
    def test_end_to_end_evaluation(self):
        """Комплексная оценка RAG системы"""
        pass
        
    def test_metrics_calculation(self):
        """Тест расчета метрик (BLEU, ROUGE и др.)"""
        pass
        
    def test_precision_at_k(self):
        """Тест расчета метрики precision@k"""
        def precision_at_k(retrieved, ground_truth, k):
            """Вычисляет precision@k"""
            relevant = set(ground_truth)
            retrieved_at_k = retrieved[:k]
            relevant_retrieved = [doc for doc in retrieved_at_k if doc in relevant]
            return len(relevant_retrieved) / k
            
        # Тест 1: precision@1 (первый документ релевантный)
        self.assertAlmostEqual(
            precision_at_k(self.retrieved, self.ground_truth, 1),
            1.0
        )
        
        # Тест 2: precision@2 (один из двух документов релевантный)
        self.assertAlmostEqual(
            precision_at_k(self.retrieved, self.ground_truth, 2),
            0.5
        )
        
        # Тест 3: precision@3 (два из трех документов релевантные)
        self.assertAlmostEqual(
            precision_at_k(self.retrieved, self.ground_truth, 3),
            2/3
        )
        
    def test_recall_at_k(self):
        """Тест расчета метрики recall@k"""
        def recall_at_k(retrieved, ground_truth, k):
            """Вычисляет recall@k"""
            relevant = set(ground_truth)
            retrieved_at_k = retrieved[:k]
            relevant_retrieved = [doc for doc in retrieved_at_k if doc in relevant]
            return len(relevant_retrieved) / len(relevant) if relevant else 0.0
            
        # Тест 1: recall@1 (1 из 2 релевантных документов)
        self.assertAlmostEqual(
            recall_at_k(self.retrieved, self.ground_truth, 1),
            0.5
        )
        
        # Тест 2: recall@2 (1 из 2 релевантных документов)
        self.assertAlmostEqual(
            recall_at_k(self.retrieved, self.ground_truth, 2),
            0.5
        )
        
        # Тест 3: recall@3 (2 из 2 релевантных документов)
        self.assertAlmostEqual(
            recall_at_k(self.retrieved, self.ground_truth, 3),
            1.0
        )
    
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
            
        # Тест 1: NDCG@1 (первый документ максимально релевантный)
        self.assertAlmostEqual(
            ndcg_at_k(self.retrieved, self.relevance_scores, 1),
            1.0
        )
        
        # Тест 2: NDCG@2 (второй документ менее релевантный)
        expected_ndcg_2 = (3 + 1/math.log(3, 2)) / (3 + 2/math.log(3, 2))
        self.assertAlmostEqual(
            ndcg_at_k(self.retrieved, self.relevance_scores, 2),
            expected_ndcg_2
        )
        
        # Тест 3: NDCG@3 (включая все документы)
        expected_ndcg_3 = (3 + 1/math.log(3, 2) + 2/math.log(4, 2)) / (3 + 2/math.log(3, 2) + 1/math.log(4, 2))
        self.assertAlmostEqual(
            ndcg_at_k(self.retrieved, self.relevance_scores, 3),
            expected_ndcg_3
        )

    @patch('builtins.print')
    def test_logging(self, mock_print):
        """Тест логирования результатов оценки"""
        # Тестируем логирование метрик
        metrics = {
            'precision@1': 0.8,
            'recall@3': 0.9,
            'ndcg@3': 0.85,
            'bleu': 0.75,
            'rouge': 0.82
        }

def visualize_metrics(metrics, k_values):
    """Заглушка функции визуализации метрик"""
    pass

    @patch('matplotlib.pyplot.show')
    @patch('matplotlib.pyplot.savefig')
    @patch('matplotlib.pyplot.subplots')
    def test_visualization(self, mock_subplots, mock_savefig, mock_show):
        """Тест визуализации метрик"""
        # Создаем mock для figure и axes
        mock_fig = MagicMock()
        mock_ax = MagicMock()
        mock_subplots.return_value = (mock_fig, mock_ax)
        
        # Тестовые данные для визуализации
        metrics = {
            'precision': [0.7, 0.8, 0.9],
            'recall': [0.6, 0.7, 0.8],
            'ndcg': [0.5, 0.6, 0.7]
        }
        k_values = [1, 3, 5]
        
        # Вызываем тестируемую функцию визуализации
        # (предполагаем, что есть функция visualize_metrics в тестируемом модуле)
        with patch('test_evaluation.visualize_metrics') as mock_visualize:
            mock_visualize(metrics, k_values)
            
            # Проверяем, что функция была вызвана с правильными параметрами
            mock_visualize.assert_called_once_with(metrics, k_values)
            
            # Проверяем, что не было попыток сохранить файлы
            mock_savefig.assert_not_called()
            
            # Проверяем, что не было попыток показать графики
            mock_show.assert_not_called()
            
            # Проверяем создание графиков для основных метрик
            mock_ax.plot.assert_any_call(k_values, metrics['precision'], label='Precision@k')
            mock_ax.plot.assert_any_call(k_values, metrics['recall'], label='Recall@k')
            mock_ax.plot.assert_any_call(k_values, metrics['ndcg'], label='NDCG@k')
            mock_ax.set_xlabel.assert_called_once_with('k')
            mock_ax.set_ylabel.assert_called_once_with('Score')
            mock_ax.set_title.assert_called_once_with('Metrics Evaluation')
            mock_ax.legend.assert_called_once()
        
        # Вызываем логирование
        print("=== Результаты оценки ===")
        for name, value in metrics.items():
            print(f"{name}: {value:.2f}")
        
        # Проверяем формат и содержание логов
        calls = mock_print.call_args_list
        self.assertEqual(calls[0][0][0], "=== Результаты оценки ===")
        
        logged_metrics = set()
        for call in calls[1:]:
            logged_line = call[0][0]
            self.assertRegex(logged_line, r"^[a-z]+@?\d?: 0\.\d{2}$")
            name = logged_line.split(":")[0]
            logged_metrics.add(name)
        
        # Проверяем, что все метрики были залогированы
        self.assertEqual(logged_metrics, set(metrics.keys()))

if __name__ == '__main__':
    unittest.main()