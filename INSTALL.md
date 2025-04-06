# Инструкция по установке

## 1. Создание виртуального окружения

```bash
python -m venv venv311
```

## 2. Активация окружения

Windows:
```cmd
venv311\Scripts\activate
```

Linux/MacOS:
```bash
source venv311/bin/activate
```

## 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

## 4. Запуск тестов

```bash
python -m pytest test_retrieval.py -v
```

## 5. Проверка работы в чистом окружении

1. Создайте новое виртуальное окружение
2. Установите зависимости
3. Убедитесь, что все тесты проходят
4. Проверьте импорты в основных модулях

## Совместимость

Протестировано с:
- Python 3.11.9
- Все зависимости из requirements.txt