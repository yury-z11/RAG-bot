#!/usr/bin/env python3
"""
Конфигурационные параметры RAG-бота с LLM
"""

import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Настройки модели эмбеддингов
    EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIMENSION = 384

    # Настройки векторной БД
    VECTOR_DB_PATH = "../Task3/vector_index"
    COLLECTION_NAME = "knowledge_base"
    SEARCH_RESULTS_COUNT = 5
    RELEVANCE_THRESHOLD = 0.4

    # Настройки генерации
    LLM_MODEL = "llama3:instruct"  # имя модели для Ollama
    MAX_RESPONSE_LENGTH = 1000
    CONFIDENCE_THRESHOLD = 0.6

    # Настройки промптинга
    ENABLE_FEW_SHOT = True
    ENABLE_CHAIN_OF_THOUGHT = True
    FEW_SHOT_EXAMPLES_COUNT = 2

# Создаем экземпляр конфигурации
config = Config()