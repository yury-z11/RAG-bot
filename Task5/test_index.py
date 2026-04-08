#!/usr/bin/env python3
"""
Скрипт для тестирования качества векторного индекса
"""

import os
import time
import json
from sentence_transformers import SentenceTransformer
import chromadb

def load_embedding_model(model_path=None, model_name=None):
    """Загрузка модели для тестирования"""
    try:
        if model_path and os.path.exists(model_path):
            model = SentenceTransformer(model_path)
            model._model_name = os.path.basename(model_path)
            return model
        elif model_name:
            model = SentenceTransformer(model_name)
            model._model_name = model_name
            return model
        else:
            model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
            model._model_name = "paraphrase-multilingual-MiniLM-L12-v2"
            return model
    except Exception as e:
        print(f"❌ Ошибка загрузки модели: {e}")
        return None

def test_search(collection, embed_model, query, expected_files=None, n_results=5):
    """Тестирование одного запроса"""
    start_time = time.time()

    try:
        query_embedding = embed_model.encode([query]).tolist()

        results = collection.query(
            query_embeddings=query_embedding,
            n_results=n_results,
            include=["metadatas", "documents", "distances"]
        )

        search_time = time.time() - start_time

        found_files = []
        if results['metadatas'] and results['metadatas'][0]:
            found_files = [meta['source'] for meta in results['metadatas'][0]]

        # Расчет точности
        precision = 0
        if expected_files and found_files:
            relevant = sum(1 for file in found_files if any(exp in file for exp in expected_files))
            precision = relevant / len(found_files)

        return {
            "query": query,
            "time": search_time,
            "results_count": len(found_files),
            "found_files": found_files,
            "precision": precision,
            "distances": results['distances'][0] if results['distances'] else [],
            "success": True
        }

    except Exception as e:
        return {
            "query": query,
            "error": str(e),
            "success": False
        }

def run_comprehensive_test():
    """Запуск комплексного тестирования"""

    print("="*80)
    print("🧪 КОМПЛЕКСНОЕ ТЕСТИРОВАНИЕ ВЕКТОРНОГО ИНДЕКСА")
    print("="*80)

    # Загрузка модели и индекса
    embed_model = load_embedding_model()
    if not embed_model:
        print("❌ Не удалось загрузить модель")
        return

    if not os.path.exists("vector_index"):
        print("❌ Векторный индекс не найден")
        return

    try:
        client = chromadb.PersistentClient(path="vector_index")
        collection = client.get_collection("knowledge_base")

        print(f"✅ Индекс загружен. Чанков: {collection.count()}")

    except Exception as e:
        print(f"❌ Ошибка загрузки индекса: {e}")
        return

    # Тестовые запросы с ожидаемыми результатами
    test_cases = [
        # Персонажи
        {"query": "Крыш Шкайзюкёр", "expected": ["Крыш_Шкайзюкёр.txt"]},
        {"query": "Щыб Шуррумхер", "expected": ["Щыб_Шуррумхер.txt"]},
        {"query": "Оби-Два-Вани Кинури", "expected": ["Оби-Два-Вани_Кинури.txt"]},
        {"query": "Лёя Органа", "expected": ["Лёя_Органа.txt"]},
        {"query": "Унакын Шкайзюкёр", "expected": ["Унакын_Шкайзюкёр.txt"]},

        # Организации
        {"query": "Галактическая Народовласта", "expected": ["Галактическая_Народовласта.txt"]},
        {"query": "Орден зёнзюмаев", "expected": ["Орден_зёнзюмаев.txt"]},
        {"query": "Фырхи", "expected": ["Фырхи.txt", "Гарт_Плудаф.txt", "Гарт_Мол.txt"]},
        {"query": "Шахиншахия", "expected": ["Шахиншахия.txt", "Щыб_Шуррумхер.txt"]},

        # События и битвы
        {"query": "Зёнзюмайско-фырхская война", "expected": ["Зёнзюмайско-фырхская_война.txt"]},
        {"query": "Битва при Унгюре", "expected": ["Битва_при_Унгюре.txt"]},
        {"query": "Битва при Абырвалге", "expected": ["Битва_при_Абырвалге.txt"]},
        {"query": "Войны клонов", "expected": ["Войны_клонов.txt"]},

        # Технологии и объекты
        {"query": "SKEX спидер", "expected": ["SKEX_спидер.txt"]},
        {"query": "Звезда Шреклихертода", "expected": ["Звезда_Шреклихертода_I.txt"]},
        {"query": "Световой меч", "expected": ["Сборка_светового_меча.txt"]},
        {"query": "Дроид", "expected": ["Дроид.txt", "Eleganz.txt", "U6-B7.txt"]},

        # Планеты и места
        {"query": "Сёлэчия", "expected": ["Сёлэчия.txt"]},
        {"query": "Чатэин", "expected": ["Чатэин.txt", "Унакын_Шкайзюкёр.txt"]},
        {"query": "Навэ", "expected": ["Навэ.txt", "Прагме_Шмыгала.txt"]},
        {"query": "Абырвалг", "expected": ["Абырвалг.txt", "Битва_при_Абырвалге.txt"]},
    ]

    print(f"\n📊 Запуск {len(test_cases)} тестовых запросов...")
    print("-" * 80)

    results = []
    total_precision = 0
    total_time = 0
    successful_tests = 0

    for i, test_case in enumerate(test_cases, 1):
        print(f"🧪 Тест {i}/{len(test_cases)}: '{test_case['query']}'")

        result = test_search(collection, embed_model, test_case['query'], test_case['expected'])

        if result['success']:
            status = "✅" if result['precision'] > 0.5 else "⚠️" if result['precision'] > 0 else "❌"
            print(f"   {status} Точность: {result['precision']:.3f} | Время: {result['time']:.3f}с")
            print(f"   📁 Найдено: {', '.join(result['found_files'][:3])}{'...' if len(result['found_files']) > 3 else ''}")

            total_precision += result['precision']
            total_time += result['time']
            successful_tests += 1
        else:
            print(f"   ❌ Ошибка: {result['error']}")

        results.append(result)
        print()

    # Статистика
    if successful_tests > 0:
        avg_precision = total_precision / successful_tests
        avg_time = total_time / successful_tests

        print("="*80)
        print("📈 СТАТИСТИКА ТЕСТИРОВАНИЯ")
        print("="*80)
        print(f"✅ Успешных тестов: {successful_tests}/{len(test_cases)}")
        print(f"🎯 Средняя точность: {avg_precision:.3f}")
        print(f"⏱️ Среднее время поиска: {avg_time:.3f}с")

        # Категоризация результатов
        excellent = sum(1 for r in results if r.get('precision', 0) > 0.8)
        good = sum(1 for r in results if 0.5 < r.get('precision', 0) <= 0.8)
        poor = sum(1 for r in results if 0 < r.get('precision', 0) <= 0.5)
        failed = len(results) - excellent - good - poor

        print(f"\n📊 Качество результатов:")
        print(f"   🏆 Отлично (>0.8): {excellent}")
        print(f"   👍 Хорошо (0.5-0.8): {good}")
        print(f"   ⚠️ Плохо (0-0.5): {poor}")
        print(f"   ❌ Ошибки: {failed}")

        # Сохранение результатов
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        results_file = f"test_results_{timestamp}.json"

        with open(results_file, 'w', encoding='utf-8') as f:
            json.dump({
                "timestamp": timestamp,
                "total_tests": len(test_cases),
                "successful_tests": successful_tests,
                "average_precision": avg_precision,
                "average_time": avg_time,
                "results": results
            }, f, ensure_ascii=False, indent=2)

        print(f"\n💾 Результаты сохранены в: {results_file}")

    else:
        print("❌ Не удалось выполнить ни одного теста")

def quick_test():
    """Быстрое тестирование основных запросов"""

    print("🚀 БЫСТРОЕ ТЕСТИРОВАНИЕ")
    print("-" * 40)

    embed_model = load_embedding_model()
    if not embed_model or not os.path.exists("vector_index"):
        print("❌ Модель или индекс не найдены")
        return

    try:
        client = chromadb.PersistentClient(path="vector_index")
        collection = client.get_collection("knowledge_base")

        quick_queries = [
            "Крыш Шкайзюкёр",
            "Галактическая Народовласта",
            "Звезда Шреклихертода",
            "СКЕХ спидер",
            "Щыб Шуррумхер"
        ]

        for query in quick_queries:
            result = test_search(collection, embed_model, query)
            if result['success']:
                status = "✅" if result['precision'] > 0 else "❌"
                print(f"{status} '{query}' -> {result['precision']:.3f}")
            else:
                print(f"❌ '{query}' -> Ошибка")

    except Exception as e:
        print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Тестирование векторного индекса")
    parser.add_argument("--quick", action="store_true", help="Быстрое тестирование")
    parser.add_argument("--model-path", help="Путь к локальной модели")
    parser.add_argument("--model-name", help="Название онлайн модели")

    args = parser.parse_args()

    if args.quick:
        quick_test()
    else:
        run_comprehensive_test()