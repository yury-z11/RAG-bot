#!/usr/bin/env python3
"""
RAG пайплайн с локальной LLM через Ollama
"""

import chromadb
from sentence_transformers import SentenceTransformer
from typing import List, Dict
import time

from config import config
from prompts import build_rasa_prompt, get_response_template
from llm_client import LLMClient


class RAGPipeline:
    def __init__(self):
        """Инициализация RAG пайплайна с локальной LLM"""
        print("🔧 Инициализация RAG пайплайна...")

        # Загрузка модели эмбеддингов
        self.embed_model = SentenceTransformer(config.EMBEDDING_MODEL)
        print(f"   ✅ Модель эмбеддингов загружена: {config.EMBEDDING_MODEL}")

        # Подключение к векторной БД
        self.client = chromadb.PersistentClient(path=config.VECTOR_DB_PATH)
        self.collection = self.client.get_collection(config.COLLECTION_NAME)
        print(f"   ✅ Векторная БД подключена: {self.collection.count()} чанков")

        # Инициализация клиента локальной LLM
        self.llm_client = LLMClient(model=config.LLM_MODEL)
        print("   ✅ LLM клиент инициализирован")

    def retrieve_chunks(self, query: str, n_results: int = None) -> Dict:
        """Поиск релевантных чанков"""
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
        """Проверка релевантности результатов"""
        if not distances:
            return False
        return min(distances) <= config.RELEVANCE_THRESHOLD

    def prepare_prompt(self, query: str, context_chunks: List[str]) -> str:
        """Подготовка промпта для LLM"""
        return build_rasa_prompt(
            question=query,
            context_chunks=context_chunks,
            use_cot=config.ENABLE_CHAIN_OF_THOUGHT
        )

    def generate_response(self, query: str, context_chunks: List[str]) -> str:
        """Генерация ответа через локальную LLM"""
        if not context_chunks:
            return "🤷 В базе знаний нет информации для ответа на этот вопрос"

        prompt = self.prepare_prompt(query, context_chunks)

        print("🧠 Генерация ответа через LLM...")
        start_time = time.time()

        response = self.llm_client.generate(prompt)

        duration = time.time() - start_time
        print(f"   ✅ Ответ сгенерирован за {duration:.2f} сек")

        return response

    def fallback_response(self, query: str, context_chunks: List[str]) -> str:
        """Запасной вариант ответа"""
        if not context_chunks:
            return "🤷 Я не знаю ответ на этот вопрос"

        main_answer = context_chunks[0]
        if len(main_answer) > 300:
            main_answer = main_answer[:300] + "..."

        template = get_response_template("general")
        return template.format(answer=main_answer)

    def process_query(self, query: str) -> str:
        """Полный процесс обработки запроса"""
        print(f"🔍 Обработка запроса: '{query}'")

        results = self.retrieve_chunks(query)

        if not results or not results.get("documents") or not results["documents"][0]:
            return "🤷 По вашему запросу ничего не найдено"

        distances = results.get("distances", [[]])[0]
        if not self.is_relevant(distances):
            return "🤷 Я не знаю ответ на этот вопрос"

        try:
            return self.generate_response(query, results["documents"][0])
        except Exception as e:
            print(f"⚠️ Ошибка генерации через LLM, fallback: {e}")
            return self.fallback_response(query, results["documents"][0])


# Синглтон экземпляр
rag_pipeline = RAGPipeline()
