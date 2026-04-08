#!/usr/bin/env python3
"""
Интерактивный режим тестирования векторного индекса
"""

import os
import time
from sentence_transformers import SentenceTransformer
import chromadb

def load_embedding_model():
    try:
        model = SentenceTransformer("sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        print("✅ Модель эмбеддингов загружена")
        return model
    except Exception as e:
        print(f"❌ Ошибка загрузки модели: {e}")
        return None

def connect_vector_db():
    try:
        client = chromadb.PersistentClient(path="vector_index")
        collection = client.get_collection("knowledge_base")
        print(f"✅ Векторная база подключена. Чанков: {collection.count()}")
        return collection
    except Exception as e:
        print(f"❌ Ошибка подключения к базе: {e}")
        return None

def search_query(collection, embed_model, query, top_k=5):
    try:
        embedding = embed_model.encode([query]).tolist()
        results = collection.query(
            query_embeddings=embedding,
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        return list(zip(documents, metadatas, distances))
    except Exception as e:
        print(f"❌ Ошибка при поиске: {e}")
        return []

def interactive_test():
    print("🧪 ИНТЕРАКТИВНОЕ ТЕСТИРОВАНИЕ ВЕКТОРНОГО ИНДЕКСА")
    print("Для выхода введите 'exit' или Ctrl+C")
    print("=" * 80)

    embed_model = load_embedding_model()
    if not embed_model:
        return

    collection = connect_vector_db()
    if not collection:
        return

    while True:
        try:
            query = input("\n🔍 Ваш запрос: ").strip()
            if query.lower() in ['exit', 'quit']:
                print("👋 Выход из режима тестирования.")
                break

            start_time = time.time()
            results = search_query(collection, embed_model, query)
            elapsed = time.time() - start_time

            if not results:
                print("⚠️ Ничего не найдено.")
                continue

            print(f"\n🔎 Результаты поиска (за {elapsed:.2f} сек):")
            for i, (doc, meta, dist) in enumerate(results, 1):
                source = meta.get("source", "неизвестно")
                preview = doc[:200].replace("\n", " ") + ("..." if len(doc) > 200 else "")
                print(f"\n📄 #{i}:")
                print(f"   Источник: {source}")
                print(f"   Расстояние: {dist:.4f}")
                print(f"   Фрагмент: {preview}")

        except KeyboardInterrupt:
            print("\n👋 Прервано пользователем.")
            break
        except Exception as e:
            print(f"❌ Ошибка: {e}")

if __name__ == "__main__":
    interactive_test()
