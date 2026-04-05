#!/usr/bin/env python3
"""
Улучшенный скрипт для создания векторного индекса с поддержкой локальной модели
"""

import os
import time
import re
import shutil
import argparse
from langchain.text_splitter import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb
import numpy as np

def batch_data(data, batch_size=4000):
    """Разбивает данные на батчи"""
    for i in range(0, len(data), batch_size):
        yield data[i:i + batch_size]

def preprocess_text(text):
    """Очистка и нормализация текста"""
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\sа-яА-ЯёЁ\-_.,!?;:]', ' ', text)
    return text.strip()

def load_embedding_model(model_path=None, model_name=None):
    """Загрузка модели с поддержкой локального пути"""
    try:
        if model_path and os.path.exists(model_path):
            print(f"   📂 Загрузка локальной модели из: {model_path}")
            model = SentenceTransformer(model_path)
            # Получаем имя модели из пути или конфига
            model._model_name = os.path.basename(model_path)
            return model
        elif model_name:
            print(f"   🌐 Загрузка онлайн модели: {model_name}")
            model = SentenceTransformer(model_name)
            model._model_name = model_name
            return model
        else:
            # Резервные варианты
            models_to_try = [
                "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
                "sentence-transformers/all-MiniLM-L6-v2"
            ]

            for model_name in models_to_try:
                try:
                    print(f"   🔄 Попытка загрузить: {model_name}")
                    model = SentenceTransformer(model_name)
                    model._model_name = model_name
                    return model
                except Exception as e:
                    print(f"   ⚠️ Не удалось загрузить {model_name}: {e}")
                    continue

            raise Exception("Не удалось загрузить ни одну модель")

    except Exception as e:
        print(f"   ❌ Ошибка загрузки модели: {e}")
        return None

def create_vector_index(model_path=None, model_name=None, chunk_size=384):
    """Создает векторный индекс с указанной моделью"""

    print("🔍 Шаг 1: Загрузка модели...")
    embed_model = load_embedding_model(model_path, model_name)

    if not embed_model:
        return None

    model_name = getattr(embed_model, '_model_name', 'Unknown')
    print(f"   ✅ Модель загружена: {model_name}")
    print(f"   📊 Размер эмбеддингов: {embed_model.get_sentence_embedding_dimension()} измерений")

    print("\n📄 Шаг 2: Загрузка и обработка документов...")
    source_folder = "knowledge_base"

    if not os.path.exists(source_folder):
        print(f"   ❌ Ошибка: Папка '{source_folder}' не найдена!")
        return None

    text_files = [f for f in os.listdir(source_folder) if f.endswith(('.txt', '.md'))]
    print(f"   📁 Найдено {len(text_files)} документов")

    all_chunks = []
    chunks_metadatas = []

    for filename in text_files:
        filepath = os.path.join(source_folder, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as file:
                content = file.read()

            content = preprocess_text(content)
            title = os.path.splitext(filename)[0].replace('_', ' ')

            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=50,
                length_function=len,
                separators=["\n\n", "\n", ". ", "! ", "? ", "; ", ", ", " "],
                add_start_index=True,
            )

            chunks = text_splitter.create_documents([content])

            for i, chunk in enumerate(chunks):
                enhanced_content = f"Документ: {title}\nТема: {title}\n\n{chunk.page_content}"

                all_chunks.append(enhanced_content)
                chunks_metadatas.append({
                    "source": filename,
                    "title": title,
                    "chunk_id": i,
                    "start_index": chunk.metadata.get('start_index', 0),
                    "content_length": len(chunk.page_content)
                })

        except Exception as e:
            print(f"   ⚠️ Ошибка при обработке файла {filename}: {e}")

    print(f"   ✅ Создано {len(all_chunks)} чанков")

    print("\n🧮 Шаг 3: Генерация эмбеддингов...")
    start_time = time.time()

    try:
        chunk_embeddings = embed_model.encode(
            all_chunks,
            show_progress_bar=True,
            batch_size=16,
            convert_to_numpy=True,
            normalize_embeddings=True,
            device='cpu'
        )

        embedding_time = time.time() - start_time
        print(f"   ✅ Эмбеддинги сгенерированы за {embedding_time:.2f} секунд")

    except Exception as e:
        print(f"   ❌ Ошибка генерации эмбеддингов: {e}")
        return None

    print("\n💾 Шаг 4: Создание векторного индекса...")
    persist_directory = "vector_index"

    if os.path.exists(persist_directory):
        try:
            shutil.rmtree(persist_directory)
            print("   🗑️ Удален старый индекс")
        except:
            pass

    try:
        client = chromadb.PersistentClient(path=persist_directory)

        collection = client.get_or_create_collection(
            name="knowledge_base",
            metadata={
                "hnsw:space": "cosine",
                "model": model_name,
                "chunk_size": str(chunk_size),
                "embedding_dim": str(embed_model.get_sentence_embedding_dimension())
            }
        )

        # Батчинг
        batch_size = 3500
        total_batches = (len(all_chunks) + batch_size - 1) // batch_size

        print(f"   📦 Добавление данных ({total_batches} батчей)...")

        for batch_num, (batch_indices, batch_embeddings, batch_metadatas, batch_documents) in enumerate(
            zip(
                batch_data(list(range(len(all_chunks))), batch_size),
                batch_data(chunk_embeddings.tolist(), batch_size),
                batch_data(chunks_metadatas, batch_size),
                batch_data(all_chunks, batch_size)
            )
        ):
            print(f"   🔄 Батч {batch_num + 1}/{total_batches} ({len(batch_indices)} элементов)")

            batch_ids = [f"chunk_{i}" for i in batch_indices]

            collection.add(
                embeddings=batch_embeddings,
                metadatas=batch_metadatas,
                documents=batch_documents,
                ids=batch_ids
            )

        print(f"   ✅ Векторный индекс сохранен в '{persist_directory}/'")

        return {
            "client": client,
            "collection": collection,
            "embed_model": embed_model,
            "chunk_count": len(all_chunks),
            "embedding_time": embedding_time,
            "model_name": model_name
        }

    except Exception as e:
        print(f"   ❌ Ошибка создания индекса: {e}")
        return None

def interactive_search(collection, embed_model):
    """Интерактивный поиск"""
    print("\n" + "="*80)
    print("🔍 ИНТЕРАКТИВНЫЙ ПОИСК")
    print("="*80)

    while True:
        try:
            query = input("\n🎯 Введите запрос (или 'quit' для выхода): ").strip()

            if query.lower() in ['quit', 'exit', 'q']:
                break
            elif not query:
                continue

            start_time = time.time()
            query_embedding = embed_model.encode([query]).tolist()

            results = collection.query(
                query_embeddings=query_embedding,
                n_results=5,
                include=["metadatas", "documents", "distances"]
            )

            search_time = time.time() - start_time

            if results['documents'] and results['documents'][0]:
                print(f"✅ Найдено результатов: {len(results['documents'][0])} (время: {search_time:.3f}с)")
                print("=" * 70)

                for i, (doc, metadata, distance) in enumerate(zip(
                    results['documents'][0],
                    results['metadatas'][0],
                    results['distances'][0]
                )):
                    print(f"\n🏆 РЕЗУЛЬТАТ {i+1} (качество: {1-distance:.3f})")
                    print(f"📄 Документ: {metadata.get('title', 'N/A')}")
                    print(f"📁 Файл: {metadata.get('source', 'N/A')}")

                    content_start = doc.find('\n\n') + 2
                    content = doc[content_start:] if content_start > 2 else doc
                    snippet = content[:200] + "..." if len(content) > 200 else content

                    print(f"📝 Сниппет: {snippet}")
                    print(f"📐 Расстояние: {distance:.4f}")
                    print("-" * 50)
            else:
                print("❌ Ничего не найдено")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"⚠️ Ошибка: {e}")

def main():
    parser = argparse.ArgumentParser(description="Создание векторного индекса")
    parser.add_argument("--model-path", help="Путь к локальной модели")
    parser.add_argument("--model-name", help="Название онлайн модели")
    parser.add_argument("--chunk-size", type=int, default=384, help="Размер чанков")
    parser.add_argument("--no-interactive", action="store_true", help="Не запускать интерактивный поиск")

    args = parser.parse_args()

    print("="*80)
    print("🛠️  СОЗДАНИЕ ВЕКТОРНОГО ИНДЕКСА")
    print("="*80)

    if os.path.exists("vector_index"):
        response = input("Индекс уже существует. Пересоздать? (y/N): ").strip().lower()
        if response != 'y':
            print("Загрузка существующего индекса...")
            try:
                client = chromadb.PersistentClient(path="vector_index")
                collection = client.get_collection("knowledge_base")
                # Загружаем модель для поиска
                embed_model = load_embedding_model(args.model_path, args.model_name)
                if embed_model and not args.no_interactive:
                    interactive_search(collection, embed_model)
                return
            except Exception as e:
                print(f"❌ Ошибка загрузки индекса: {e}")

    result = create_vector_index(args.model_path, args.model_name, args.chunk_size)

    if result:
        print("\n" + "="*80)
        print("✅ ИНДЕКС УСПЕШНО СОЗДАН!")
        print("="*80)
        print(f"🤖 Модель: {result['model_name']}")
        print(f"📦 Чанков: {result['chunk_count']}")
        print(f"⏱️ Время: {result['embedding_time']:.2f} секунд")

        if not args.no_interactive:
            interactive_search(result['collection'], result['embed_model'])
    else:
        print("❌ Не удалось создать индекс")

if __name__ == "__main__":
    main()