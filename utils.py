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