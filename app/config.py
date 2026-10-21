import os
from langchain_openai import ChatOpenAI

def get_llm():
    """Retorna la instancia del LLM utilizando OpenRouter."""
    return ChatOpenAI(
        model="meta-llama/llama-3.1-8b-instruct",  # Slug exacto indicado por OpenRouter
        api_key=os.getenv("OPENROUTER_API_KEY"),
        base_url="https://openrouter.ai/api/v1",
        temperature=0.3,
        timeout=30.0
    )