#!/usr/bin/env python3
"""
Главный скрипт запуска RAG-бота
"""

import argparse
import sys
from rag_pipeline import RAGPipeline
from tqdm import tqdm  # Прогресс-бар для пакетной обработки

def parse_args():
    parser = argparse.ArgumentParser(description="RAG-бот с локальной LLM")
    parser.add_argument("--debug", action="store_true", help="Включить режим отладки (печать промптов и чанков)")
    parser.add_argument("--no-protection", action="store_true", help="Отключить фильтрацию вредоносных чанков")
    parser.add_argument("--query", type=str, help="Задать один вопрос при запуске")
    parser.add_argument("--file", type=str, help="Файл с вопросами (по одному в строке)")
    return parser.parse_args()

def process_batch_file(rag: RAGPipeline, file_path: str):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            questions = [line.strip() for line in f if line.strip()]

        print(f"\n📄 Обработка {len(questions)} вопросов из файла: {file_path}\n")

        for idx, question in enumerate(tqdm(questions, desc="📊 Прогресс", unit="вопрос"), 1):
            print(f"\n📌 Вопрос {idx}: {question}")
            response = rag.process_query(question)
            print("🤖 Ответ:")
            print(response)
            print("------------------------------------------------------------")

    except FileNotFoundError:
        print(f"❌ Файл не найден: {file_path}")
    except Exception as e:
        print(f"❌ Ошибка при чтении файла: {e}")

def main():
    args = parse_args()

    rag = RAGPipeline()

    rag.debug = args.debug
    rag.protection_enabled = not args.no_protection

    # Если передан файл с вопросами
    if args.file:
        process_batch_file(rag, args.file)
        return

    # Если передан одиночный вопрос
    if args.query:
        print("\n🎯 Вопрос:", args.query)
        response = rag.process_query(args.query)
        print("\n🤖 Ответ:")
        print(response)
        return

    # Режим интерактивного чата
    print("\n============================================================")
    print("🤖 Локальный RAG БОТ (LLM + векторный поиск)")
    print("============================================================")
    print("Для выхода: 'quit', 'exit' или Ctrl+C")
    print("------------------------------------------------------------")

    while True:
        try:
            query = input("\n🎯 Ваш вопрос: ").strip()
            if query.lower() in ["quit", "exit"]:
                print("👋 До встречи!")
                break

            response = rag.process_query(query)
            print("\n============================================================")
            print("🤖 ОТВЕТ:")
            print(response.strip())
            print("============================================================")

        except KeyboardInterrupt:
            print("\n👋 До встречи!")
            break
        except Exception as e:
            print(f"❌ Произошла ошибка: {e}")

if __name__ == "__main__":
    main()
