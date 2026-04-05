Использование:

Создание индекса с локальной моделью:

```bash
python build_index.py --model-path ./paraphrase-multilingual-MiniLM-L12-v2
```

Создание индекса с онлайн моделью:
```bash
python build_index.py --model-name sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

Запуск комплексного тестирования:
```bash
python test_index.py
```

Быстрое тестирование:
```bash
python test_index.py --quick
```
