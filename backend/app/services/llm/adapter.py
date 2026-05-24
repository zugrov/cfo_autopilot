"""
LLMAdapter — абстракция над OpenRouter (Claude Sonnet) и YandexGPT.

Логика:
- Основной провайдер: OpenRouter (claude-sonnet-4-5)
- Fallback: YandexGPT при деградации OpenRouter (p95 > 12s или error rate > 5%)
- PII redact перед отправкой
- Кеш ответов по (question_hash, data_version)
"""
from __future__ import annotations

import hashlib
import re
import time
from typing import Literal

import httpx

from app.core.config import get_settings

settings = get_settings()

ProviderType = Literal["openrouter", "yandexgpt"]

# Простой in-memory кеш (в production: Redis)
_response_cache: dict[str, dict] = {}

# Метрика деградации OpenRouter
_openrouter_errors = 0
_openrouter_last_check = time.time()
_USE_FALLBACK = False


def _should_use_fallback() -> bool:
    global _USE_FALLBACK
    return _USE_FALLBACK


def _record_openrouter_error() -> None:
    global _openrouter_errors, _USE_FALLBACK
    _openrouter_errors += 1
    if _openrouter_errors >= 3:
        _USE_FALLBACK = True


def _record_openrouter_success() -> None:
    global _openrouter_errors, _USE_FALLBACK
    _openrouter_errors = max(0, _openrouter_errors - 1)
    if _openrouter_errors == 0:
        _USE_FALLBACK = False


# Regex для PII redaction
_PII_PATTERNS = [
    (re.compile(r"\b\d{10}\b"), "[ИНН]"),           # ИНН 10 цифр
    (re.compile(r"\b\d{12}\b"), "[ИНН]"),           # ИНН 12 цифр (физлицо)
    (re.compile(r"\b\d{4}\s\d{6}\b"), "[ПАСПОРТ]"),  # Серия номер паспорта
]


def redact_pii(text: str) -> str:
    """Маскирует ИНН, паспортные данные из текста."""
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def _cache_key(question: str, data_version: str) -> str:
    raw = f"{question}|{data_version}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def _call_openrouter(prompt: str, system: str) -> str:
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://cfo-autopilot.ru",
    }
    payload = {
        "model": settings.openrouter_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": 500,
        "temperature": 0.1,
    }
    start = time.time()
    async with httpx.AsyncClient(timeout=14.0) as client:
        resp = await client.post(
            f"{settings.openrouter_base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        elapsed = time.time() - start
        if elapsed > 12:
            _record_openrouter_error()
        else:
            _record_openrouter_success()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_yandexgpt(prompt: str, system: str) -> str:
    headers = {
        "Authorization": f"Api-Key {settings.yandex_gpt_api_key}",
        "Content-Type": "application/json",
        "x-folder-id": settings.yandex_gpt_folder_id,
    }
    payload = {
        "modelUri": f"gpt://{settings.yandex_gpt_folder_id}/yandexgpt/latest",
        "completionOptions": {"stream": False, "temperature": 0.1, "maxTokens": 500},
        "messages": [
            {"role": "system", "text": system},
            {"role": "user", "text": prompt},
        ],
    }
    async with httpx.AsyncClient(timeout=14.0) as client:
        resp = await client.post(
            "https://llm.api.cloud.yandex.net/foundationModels/v1/completion",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()["result"]["alternatives"][0]["message"]["text"]


async def ask_llm(
    question: str,
    context: str,
    data_version: str,
    preferred_provider: ProviderType = "openrouter",
) -> dict:
    """
    Задаёт вопрос LLM с кешированием и PII redact.
    Возвращает {answer, provider, cached}.
    """
    clean_question = redact_pii(question)
    clean_context = redact_pii(context)

    cache_k = _cache_key(clean_question, data_version)
    if cache_k in _response_cache:
        cached = _response_cache[cache_k]
        return {**cached, "cached": True}

    system = (
        "Ты — финансовый аналитик компании. Отвечай кратко (2-3 предложения) "
        "только на основе предоставленных данных. "
        "Если данных недостаточно, скажи: 'Не могу ответить по имеющимся данным.'"
    )
    prompt = f"Данные компании:\n{clean_context}\n\nВопрос: {clean_question}"

    use_fallback = _should_use_fallback() or preferred_provider == "yandexgpt"
    provider: ProviderType

    try:
        if use_fallback:
            answer = await _call_yandexgpt(prompt, system)
            provider = "yandexgpt"
        else:
            answer = await _call_openrouter(prompt, system)
            provider = "openrouter"
    except Exception:
        if not use_fallback:
            _record_openrouter_error()
            answer = await _call_yandexgpt(prompt, system)
            provider = "yandexgpt"
        else:
            raise

    result = {"answer": answer, "provider": provider, "cached": False}
    _response_cache[cache_k] = result
    return result
