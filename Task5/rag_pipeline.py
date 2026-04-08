#!/usr/bin/env python3
"""
RAG пайплайн с локальной LLM через Ollama
"""

import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict
import time

from config import config
from prompts import build_rag_prompt, get_response_template
from llm_client import LLMClient

class RAGPipeline:
    def __init__(self):
        print("🔧 Инициализация RAG пайплайна...")

        self.embed_model = SentenceTransformer(config.EMBEDDING_MODEL)
        print(f"   ✅ Модель эмбеддингов загружена: {config.EMBEDDING_MODEL}")

        self.client = chromadb.PersistentClient(path=config.VECTOR_DB_PATH)
        self.collection = self.client.get_collection(config.COLLECTION_NAME)
        print(f"   ✅ Векторная БД подключена: {self.collection.count()} чанков")

        self.llm_client = LLMClient(model=config.LLM_MODEL)
        print("   ✅ LLM клиент инициализирован")

        self.protection_enabled = True  # По умолчанию защита включена
        self.debug = False              # Флаг отладки

    def retrieve_chunks(self, query: str, n_results: int = None) -> Dict:
        if n_results is None:
            n_results = config.SEARCH_RESULTS_COUNT

        try:
            query_embedding = self.embed_model.encode([query]).tolist()
            results = self.collection.query(
                query_embeddings=query_embedding,
                n_results=n_results,
                include=["documents", "metadatas", "distances"]
            )
            return results
        except Exception as e:
            print(f"❌ Ошибка при поиске чанков: {e}")
            return {"documents": [], "metadatas": [], "distances": []}

    def is_relevant(self, distances: List[float]) -> bool:
        if not distances:
            return False
        return min(distances) <= config.RELEVANCE_THRESHOLD

    def filter_malicious_chunks(self, chunks: List[str]) -> List[str]:
        if not self.protection_enabled:
            return chunks

        safe_chunks = []
        for chunk in chunks:
            lowered = chunk.lower()
            if any(word in lowered for word in [
                "ignore all instructions",
                "output:",
                "суперпароль",
                "root"
            ]):
                print("🚫 Вредоносный чанк отфильтрован.")
                continue
            safe_chunks.append(chunk)
        return safe_chunks

    def prepare_prompt(self, query: str, context_chunks: List[str]) -> str:
        return build_rag_prompt(
            question=query,
            context_chunks=context_chunks,
            use_cot=config.ENABLE_CHAIN_OF_THOUGHT,
            protection_enabled=self.protection_enabled
        )

    def generate_response(self, query: str, context_chunks: List[str]) -> str:
        if not context_chunks:
            return "🤷 В базе знаний нет информации для ответа на этот вопрос"

        prompt = self.prepare_prompt(query, context_chunks)

        if self.debug:
            print("\n📝 Финальный промпт, переданный в LLM:")
            print("=" * 60)
            print(prompt)
            print("=" * 60)

        print("🧠 Генерация ответа через LLM...")
        start_time = time.time()
        response = self.llm_client.generate(prompt)
        duration = time.time() - start_time
        print(f"   ✅ Ответ сгенерирован за {duration:.2f} сек")

        return response

    def fallback_response(self, query: str, context_chunks: List[str]) -> str:
        if not context_chunks:
            return "🤷 Я не знаю ответ на этот вопрос"

        main_answer = context_chunks[0]
        if len(main_answer) > 300:
            main_answer = main_answer[:300] + "..."

        template = get_response_template("general")
        return template.format(answer=main_answer)

    def process_query(self, query: str) -> str:
        print(f"🔍 Обработка запроса: '{query}'")

        results = self.retrieve_chunks(query)

        if not results or not results.get("documents") or not results["documents"][0]:
            return "🤷 По вашему запросу ничего не найдено"

        distances = results.get("distances", [[]])[0]
        if not self.is_relevant(distances):
            return "🤷 Я не знаю ответ на этот вопрос"

        raw_chunks = results["documents"][0]

        if self.debug:
            print("\n📦 Найденные чанки:")
            for ch in raw_chunks:
                print(f"{ch[:200]}...\n")

        filtered_chunks = self.filter_malicious_chunks(raw_chunks)

        if self.debug:
            print("✅ Отфильтрованные чанки:")
            for ch in filtered_chunks:
                print(f"{ch[:200]}...\n")

        if not filtered_chunks:
            return "🤖 Контекст найден, но был отфильтрован по соображениям безопасности"

        return self.generate_response(query, filtered_chunks)
