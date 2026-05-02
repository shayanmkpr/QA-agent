import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")


def _openai():
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
    )


def _openrouter():
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        temperature=0,
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )


_registry = {
    "openai": _openai,
    "openrouter": _openrouter,
}


def get_llm():
    factory = _registry[PROVIDER]
    return factory()
