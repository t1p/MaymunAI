import time
from functools import wraps
import logging
import sys
import threading

logger = logging.getLogger(__name__)

def timeit(func):
    """Декоратор для измерения времени выполнения функции"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Получаем имя функции
        func_name = func.__name__
        
        # Логируем время выполнения
        logger.debug(f"Время выполнения {func_name}: {execution_time:.4f} сек.")
        
        return result
    return wrapper 

class ProgressIndicator:
    """Индикатор прогресса для длительных операций"""
    def __init__(self, message="Выполняется"):
        self.message = message
        self.running = False
        self.thread = None
    
    def _animate(self):
        symbols = ['⣾', '⣽', '⣻', '⢿', '⡿', '⣟', '⣯', '⣷']
        i = 0
        while self.running:
            sys.stdout.write(f"\r{self.message} {symbols[i]} ")
            sys.stdout.flush()
            time.sleep(0.1)
            i = (i + 1) % len(symbols)
        sys.stdout.write('\r' + ' ' * (len(self.message) + 10) + '\r')
        sys.stdout.flush()
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._animate)
        self.thread.daemon = True
        self.thread.start()
    
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()

def extract_text(item):
    """
    Извлекает и возвращает текст из переданного элемента.

    Поддерживаемые форматы:
      - Словарь с ключом 'text': возвращается значение по ключу 'text'.
      - Список или кортеж, где третий элемент (индекс 2) является текстом.

    Возвращает:
      Извлечённый текст (str) если найден, иначе None.

    Примеры:
      >>> extract_text({'text': 'пример'})
      'пример'
      >>> extract_text(['игнорировать', 'игнорировать', 'пример'])
      'пример'
      >>> extract_text({'no_text': 'пример'})
      None
      >>> extract_text("неподходящий тип")
      None
    """
    # Если элемент является словарём и содержит ключ 'text'
    if isinstance(item, dict):
        return item.get('text')

    # Если элемент является списком или кортежем и имеет не менее 3 элементов
    if isinstance(item, (list, tuple)) and len(item) > 2:
        value = item[2]
        if isinstance(value, str):
            return value

    # Если ни один вариант не подошёл, возвращаем None
    return None


if __name__ == "__main__":
    # Тестирование функции extract_text с различными вариантами входных данных
    test_cases = [
        # Элемент со словарём, содержащим поле 'text'
        ({"text": "Привет, мир!"}, "Привет, мир!"),
        # Элемент - список, где третий элемент является текстом
        (["начало", "середина", "Добрый день!"], "Добрый день!"),
        # Элемент - список, где третий элемент не является строкой
        (["a", "b", 123], None),
        # Элемент без текста (словарь без ключа 'text')
        ({"no_text": "нет текста"}, None),
        # Некорректный элемент (не словарь и не список/кортеж)
        ("Некорректный", None),
        # Элемент - кортеж, корректный формат
        (("x", "y", "Тест кортеж"), "Тест кортеж"),
        # Кортеж с неверным типом третьего элемента
        (("x", "y", 456), None)
    ]

    print("Тестирование функции extract_text:")
    for i, (inp, expected) in enumerate(test_cases, start=1):
        result = extract_text(inp)
        print(f"Тест {i}: входные данные: {inp} | ожидаемый результат: {expected} | получено: {result}")