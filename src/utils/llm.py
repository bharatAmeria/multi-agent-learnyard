"""Thin wrapper around the OpenAI SDK shared by all agents.

LLM_AVAILABLE is False when no API key is configured (or the `openai`
package isn't installed). Every agent checks this flag and falls back to a
small deterministic default so the graph stays runnable offline (tests, CI,
first-time setup before a key is added).

The key can come from `.env` (loaded into `config.settings` at startup) or
be set later at runtime via `configure_api_key()` — e.g. from the Streamlit
UI's "API Key" field, with no process restart required.
"""
import json
import sys

from config import settings
from exception import MyException
from logger import GLOBAL_LOGGER as logger

try:
    import openai
except ImportError:  # pragma: no cover
    openai = None

_client = None
if openai is not None and settings.openai_api_key:
    _client = openai.OpenAI(api_key=settings.openai_api_key)


class _LLMAvailableFlag:
    """Bool-like flag that re-checks `_client` on every evaluation.

    Agents do `from utils.llm import LLM_AVAILABLE` — a plain bool would be
    copied at import time and go stale the moment `configure_api_key()`
    changes `_client` later. Importing this singleton object instead means
    `if not LLM_AVAILABLE:` always reflects the current client state,
    everywhere it's been imported, without touching any agent module.
    """

    def __bool__(self) -> bool:
        return _client is not None

    def __repr__(self) -> str:  # pragma: no cover
        return repr(bool(self))


LLM_AVAILABLE = _LLMAvailableFlag()


def configure_api_key(api_key: str) -> bool:
    """Set (or clear, if blank) the OpenAI API key at runtime.

    Returns True if a client was constructed successfully, False otherwise
    (missing `openai` package, blank key, or a malformed key rejected by
    the SDK's own validation). This does not make a network call, so a
    True result means "client constructed", not "key confirmed valid by
    the API" — that's only confirmed on the first real call_llm().
    """
    global _client
    api_key = (api_key or "").strip()
    if not api_key:
        _client = None
        logger.info("configure_api_key_cleared")
        return False
    if openai is None:
        logger.error("configure_api_key_failed", error="openai package not installed")
        return False
    try:
        _client = openai.OpenAI(api_key=api_key)
        logger.info("configure_api_key_set")
        return True
    except Exception as e:
        _client = None
        logger.error("configure_api_key_failed", error=str(e))
        return False


def call_llm(system: str, user: str, max_tokens: int = 4096) -> str:
    """Single-turn completion. Raises if LLM_AVAILABLE is False — callers
    must check the flag first and use their own offline fallback."""
    if not LLM_AVAILABLE:
        raise MyException(RuntimeError("No OPENAI_API_KEY configured; check LLM_AVAILABLE first."), sys)
    try:
        response = _client.chat.completions.create(
            model=settings.model_name,
            max_completion_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = response.choices[0].message.content or ""
        logger.info("call_llm_completed", max_tokens=max_tokens)
        return text
    except Exception as e:
        logger.error("call_llm_failed", error=str(e))
        raise MyException(e, sys) from e


def call_llm_json(system: str, user: str, max_tokens: int = 4096):
    """Like call_llm but parses the response as JSON, tolerating code fences
    or stray prose around the JSON payload."""
    full_system = system + "\n\nRespond with ONLY valid JSON. No prose, no markdown code fences."
    text = call_llm(full_system, user, max_tokens=max_tokens).strip()
    return _parse_json_loose(text)


def _parse_json_loose(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    stripped = strip_code_fences(text)
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass
    start_candidates = [i for i in (stripped.find("{"), stripped.find("[")) if i != -1]
    if not start_candidates:
        logger.error("json_parse_failed", text_excerpt=text[:200])
        raise MyException(ValueError(f"Could not parse JSON from LLM response: {text[:200]!r}"), sys)
    start = min(start_candidates)
    end = max(stripped.rfind("}"), stripped.rfind("]"))
    try:
        return json.loads(stripped[start : end + 1])
    except Exception as e:
        logger.error("json_parse_failed", text_excerpt=text[:200], error=str(e))
        raise MyException(e, sys) from e


def strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()