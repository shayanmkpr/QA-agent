import os
import requests
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

load_dotenv()

PROVIDER = os.getenv("LLM_PROVIDER", "openrouter")

_FALLBACK_CONTEXT: dict[str, int] = {
    "gpt-4o-mini": 128000,
    "gpt-4o": 128000,
    "gpt-4": 8192,
    "gpt-4-turbo": 128000,
    "gpt-3.5-turbo": 16385,
    "claude-3-5-sonnet": 200000,
    "claude-3-opus": 200000,
    "gemini/gemini-2.0-flash": 1000000,
}


def get_max_context_window() -> int:
    """Return the model's max context window.

    For OpenRouter: fetches /api/v1/models and looks up the configured model.
    Falls back to _FALLBACK_CONTEXT on failure.
    """
    if PROVIDER == "openrouter":
        model_name = os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini")
        base = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
        try:
            resp = requests.get(f"{base}/models", timeout=5)
            resp.raise_for_status()
            for m in resp.json().get("data", []):
                if m.get("id") == model_name:
                    ctx = m.get("context_length", _FALLBACK_CONTEXT.get(model_name, 128000))
                    print(f"[config] {model_name} max context: {ctx:,} tokens (from API)")
                    return ctx
        except Exception as e:
            print(f"[config] models API failed ({e}), using fallback")
            pass
        ctx = _FALLBACK_CONTEXT.get(model_name, 128000)
        print(f"[config] {model_name} max context: {ctx:,} tokens (fallback)")
        return ctx

    # OpenAI
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    ctx = _FALLBACK_CONTEXT.get(model_name, 128000)
    print(f"[config] {model_name} max context: {ctx:,} tokens (fallback)")
    return ctx


def _openai():
    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        temperature=0,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


def _openrouter():
    return ChatOpenAI(
        model=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o-mini"),
        temperature=0,
        base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )


_registry = {
    "openai": _openai,
    "openrouter": _openrouter,
}


def get_llm():
    factory = _registry[PROVIDER]
    return factory()
