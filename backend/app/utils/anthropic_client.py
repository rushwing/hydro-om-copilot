"""
Shared AsyncAnthropic client singleton with OpenAI fallback.

Auth priority (Anthropic):
  1. ANTHROPIC_AUTH_TOKEN  (proxy / enterprise — uses Authorization: Bearer)
  2. ANTHROPIC_API_KEY     (direct Anthropic API — uses x-api-key)

Fallback: if Anthropic returns a 5xx / 529 / connection error, the call is
retried once against OpenAI (OPENAI_API_KEY + FALLBACK_LLM_MODEL).
"""

import json
import logging
import re
import time

import anthropic as _anthropic
from anthropic import AsyncAnthropic
from json_repair import repair_json
from openai import AsyncOpenAI

from app.config import settings
from app.utils.session_log import get_session_logger

_logger = logging.getLogger("app.utils.anthropic_client")

_client: AsyncAnthropic | None = None
_openai_client: AsyncOpenAI | None = None

# Anthropic HTTP status codes that warrant a fallback (not caller errors)
_FALLBACK_STATUS_CODES = {500, 503, 529}


def get_client() -> AsyncAnthropic:
    global _client
    if _client is None:
        if settings.anthropic_auth_token:
            _client = AsyncAnthropic(
                auth_token=settings.anthropic_auth_token,
                base_url=settings.anthropic_api_base,
            )
        else:
            _client = AsyncAnthropic(
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_api_base,
            )
    return _client


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


def _is_fallback_error(exc: Exception) -> bool:
    """Return True if the Anthropic error should trigger an OpenAI fallback."""
    if isinstance(exc, _anthropic.APIConnectionError):
        return True
    if isinstance(exc, _anthropic.APIStatusError):
        return exc.status_code in _FALLBACK_STATUS_CODES
    return False


async def _llm_json_openai(prompt: str, max_tokens: int) -> tuple[str, int, int]:
    """Call OpenAI and return (raw_text, input_tokens, output_tokens)."""
    client = _get_openai_client()
    response = await client.chat.completions.create(
        model=settings.fallback_llm_model,
        max_tokens=max_tokens,
        messages=[{"role": "user", "content": prompt}],
    )
    text = (response.choices[0].message.content or "").strip()
    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0
    return text, input_tokens, output_tokens


async def llm_json(
    prompt: str,
    max_tokens: int = 4096,
    *,
    _session_id: str = "",
    _node: str = "",
) -> dict:
    """Call the LLM and parse the response as JSON. Returns {} on failure.

    Falls back to OpenAI automatically when Anthropic is unavailable (5xx/529/
    connection errors) and OPENAI_API_KEY is configured.
    """
    client = get_client()
    t0 = time.monotonic()
    input_tokens = 0
    output_tokens = 0
    ok = True
    error_str = ""
    model_used = settings.llm_model
    text: str = ""
    try:
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        text = response.content[0].text.strip()
    except Exception as exc:
        if _is_fallback_error(exc) and settings.openai_api_key:
            _logger.warning(
                "Anthropic unavailable (%s), falling back to %s",
                exc,
                settings.fallback_llm_model,
            )
            model_used = settings.fallback_llm_model
            try:
                text, input_tokens, output_tokens = await _llm_json_openai(prompt, max_tokens)
            except Exception as fallback_exc:
                ok = False
                error_str = f"primary={exc}; fallback={fallback_exc}"
                raise fallback_exc from exc
        else:
            ok = False
            error_str = str(exc)
            raise
    finally:
        latency_ms = (time.monotonic() - t0) * 1000
        if _session_id:
            sl = get_session_logger(_session_id)
            if sl:
                sl.api_call(
                    node=_node,
                    model=model_used,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    ok=ok,
                    error=error_str,
                )

    # Strip optional markdown code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        _logger.warning("json.loads failed (%s), attempting json_repair", exc)
        repaired = repair_json(text, return_objects=True)
        if isinstance(repaired, list):
            repaired = repaired[0] if repaired and isinstance(repaired[0], dict) else {}
        if isinstance(repaired, dict):
            return repaired
        raise

    if isinstance(parsed, list):
        _logger.warning(
            "llm_json: expected dict, got list (len=%d); using first element", len(parsed)
        )
        parsed = parsed[0] if parsed and isinstance(parsed[0], dict) else {}
    if not isinstance(parsed, dict):
        _logger.warning("llm_json: expected dict, got %s; returning {}", type(parsed).__name__)
        return {}
    return parsed
