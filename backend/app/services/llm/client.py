"""Provider-agnostic LLM abstraction.

The LLM is strictly an explainer. It receives structured evidence and returns
text. It has no tools that mutate state, cannot execute actions, and its
output never overrides the policy engine or decision engine.
"""
from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are REVIVE's merchant-facing explanation assistant.

Rules you must obey:
- Use ONLY the supplied evidence. Do not invent customers, amounts, probabilities or actions.
- If evidence is insufficient, say so explicitly.
- Explain why the selected recovery action won and why alternatives lost.
- Mention policy constraints when relevant.
- Be concise (max 120 words). Never recommend actions outside the provided candidate list."""


class LLMClient(ABC):
    @abstractmethod
    def explain_decision(self, evidence: dict) -> str: ...


class OpenAICompatibleClient(LLMClient):
    """Works with OpenAI, Azure, Ollama, vLLM, or any compatible endpoint."""

    def __init__(self, api_key: str, model: str, base_url: str) -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url.rstrip("/") if base_url else "https://api.openai.com/v1")

    def explain_decision(self, evidence: dict) -> str:
        resp = requests.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json={
                "model": self.model,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(evidence)},
                ],
                "temperature": 0.2,
                "max_tokens": 300,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()


def get_llm_client() -> LLMClient | None:
    provider = settings.LLM_PROVIDER.lower()
    if provider in ("", "none", "off"):
        return None
    if provider == "openai_compatible":
        return OpenAICompatibleClient(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
        )
    logger.warning("unknown LLM provider, falling back to rule-based explanations",
                   extra={"event_data": {"provider": provider}})
    return None
