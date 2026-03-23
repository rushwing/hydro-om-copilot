"""
LLM factory — builds a ChatAnthropic instance with an optional OpenAI fallback.

Auth priority (Anthropic):
  1. ANTHROPIC_AUTH_TOKEN  → AsyncAnthropic(auth_token=..., base_url=...)  (proxy / enterprise)
  2. ANTHROPIC_API_KEY     → x-api-key header                              (direct Anthropic API)

Fallback: if OPENAI_API_KEY is set, the returned model is wrapped with
.with_fallbacks([ChatOpenAI(...)]) so LangChain retries on 5xx/connection errors.
"""

import anthropic as _anthropic
from anthropic import Anthropic, AsyncAnthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import settings

# Only fall back on server-side / network failures, not on caller errors (4xx).
_FALLBACK_EXCEPTIONS = (
    _anthropic.APIConnectionError,  # network / timeout
    _anthropic.InternalServerError,  # 500 / 503 / 529
)


def _build_primary() -> ChatAnthropic:
    if settings.anthropic_auth_token:
        llm = ChatAnthropic(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            anthropic_api_key="dummy",  # required field, overridden below
        )
        llm._client = Anthropic(
            auth_token=settings.anthropic_auth_token,
            base_url=settings.anthropic_api_base,
        )
        llm._async_client = AsyncAnthropic(
            auth_token=settings.anthropic_auth_token,
            base_url=settings.anthropic_api_base,
        )
        return llm

    return ChatAnthropic(
        model=settings.llm_model,
        temperature=settings.llm_temperature,
        api_key=settings.anthropic_api_key,
        anthropic_api_url=settings.anthropic_api_base,
    )


def build_llm() -> BaseChatModel:
    """Build the primary LLM with an optional OpenAI fallback.

    NOTE: this function is currently unused by the graph nodes, which call
    llm_json() directly.  It is provided as a ready-to-wire interface for
    future LangChain streaming integration.
    """
    primary = _build_primary()
    if settings.openai_api_key:
        fallback = ChatOpenAI(
            model=settings.fallback_llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.openai_api_key,
        )
        return primary.with_fallbacks(
            [fallback],
            exceptions_to_handle=_FALLBACK_EXCEPTIONS,
        )
    return primary
