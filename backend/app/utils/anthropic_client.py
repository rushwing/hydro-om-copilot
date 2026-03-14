"""
Shared AsyncAnthropic client singleton.

Auth priority:
  1. ANTHROPIC_AUTH_TOKEN  (proxy / enterprise — uses Authorization: Bearer)
  2. ANTHROPIC_API_KEY     (direct Anthropic API — uses x-api-key)
"""

import json
import logging
import re
import time

from anthropic import AsyncAnthropic
from json_repair import repair_json

from app.config import settings
from app.utils.session_log import get_session_logger

_logger = logging.getLogger("app.utils.anthropic_client")

_client: AsyncAnthropic | None = None


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


async def llm_json(
    prompt: str,
    max_tokens: int = 4096,
    *,
    _session_id: str = "",
    _node: str = "",
) -> dict:
    """Call the LLM and parse the response as JSON. Returns {} on failure."""
    client = get_client()
    t0 = time.monotonic()
    input_tokens = 0
    output_tokens = 0
    ok = True
    error_str = ""
    try:
        response = await client.messages.create(
            model=settings.llm_model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
    except Exception as exc:
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
                    model=settings.llm_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    latency_ms=latency_ms,
                    ok=ok,
                    error=error_str,
                )

    text = response.content[0].text.strip()

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
