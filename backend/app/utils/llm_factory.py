"""
LLM factory — builds a ChatAnthropic instance with an optional OpenAI fallback.

Auth priority (Anthropic):
  1. ANTHROPIC_AUTH_TOKEN  → AsyncAnthropic(auth_token=..., base_url=...)  (proxy / enterprise)
  2. ANTHROPIC_API_KEY     → x-api-key header                              (direct Anthropic API)

Fallback: if OPENAI_API_KEY is set, the returned model is wrapped with
.with_fallbacks([ChatOpenAI(...)]) so LangChain retries on 5xx/connection errors.
"""

from anthropic import Anthropic, AsyncAnthropic
from langchain_anthropic import ChatAnthropic
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI

from app.config import settings


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
    primary = _build_primary()
    if settings.openai_api_key:
        fallback = ChatOpenAI(
            model=settings.fallback_llm_model,
            temperature=settings.llm_temperature,
            api_key=settings.openai_api_key,
        )
        return primary.with_fallbacks([fallback])
    return primary
