"""
LLM factory — builds a ChatAnthropic instance from settings.

Auth priority:
  1. ANTHROPIC_AUTH_TOKEN  → AsyncAnthropic(auth_token=..., base_url=...)  (proxy / enterprise)
  2. ANTHROPIC_API_KEY     → x-api-key header                              (direct Anthropic API)
"""

from anthropic import Anthropic, AsyncAnthropic
from langchain_anthropic import ChatAnthropic

from app.config import settings


def build_llm() -> ChatAnthropic:
    if settings.anthropic_auth_token:
        # Inject custom clients so auth_token + base_url are used directly
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
