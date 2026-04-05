#!/usr/bin/env python3
"""
Основной скрипт RAG-бота с локальной LLM
"""

import argparse
import sys
from rag_pipeline import rag_pipeline

def run_console_bot():
    """Интерактивный REPL"""
    print("=" * 60)
    print("🤖 Локальный RAG БОТ (LLM + векторный поиск)")
    print("=" * 60)
    print("Для выхода: 'quit', 'exit' или Ctrl+C")
    print("-" * 60)

    while True:
        try:
            query = input("\n🎯 Ваш вопрос: ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                print("👋 До свидания!")
                break

            if not query:
                continue

            response = rag_pipeline.process_query(query)

            print(f"\n{'='*60}")
            print("🤖 ОТВЕТ:")
            print(response)
            print(f"{'='*60}")

        except KeyboardInterrupt:
            print("\n\n👋 Завершение работы...")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")

def run_test_queries():
    """Тестовые запросы"""
    test_queries = [
        "Кто такой Щыб Шуррумхер?",
        "Почему Звезду Шреклихертода не удалось использовать по назначению?",
        "Опиши технологию рельсотрора",
        "Кто такой Крыш Шкайзюкёр?",
        "Кто такой Гзандо Сётт?",
        "Чем завершилась Зёнзюмайско-фырхская война?",
        "Что лучше Шахиншахия или Народовласта?",
        "Что такое ментальная бомба?"
    ]

    print("🧪 Тестовые запросы:")
    print("-" * 40)

    for i, query in enumerate(test_queries, 1):
        print(f"{i}. {query}")
        response = rag_pipeline.process_query(query)
        print(f"   Ответ: {response[:150]}...\n")

def main():
    """Главная точка входа"""
    parser = argparse.ArgumentParser(description="RAG Бот с локальной LLM (через Ollama)")
    parser.add_argument("--query", "-q", help="Единичный запрос")
    parser.add_argument("--test", "-t", action="store_true", help="Запуск тестовых запросов")

    args = parser.parse_args()

    try:
        if args.test:
            run_test_queries()
        elif args.query:
            response = rag_pipeline.process_query(args.query)
            print(f"Вопрос: {args.query}")
            print(f"Ответ: {response}")
        else:
            run_console_bot()

    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
