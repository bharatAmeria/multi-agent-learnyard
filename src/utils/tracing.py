"""LangSmith tracing decorator with a transparent no-op fallback.

Set LANGSMITH_TRACING=true and LANGSMITH_API_KEY in .env to get real traces
for every agent node (Phase 9). Without those, @traceable is a pass-through
so nothing else has to change.
"""
try:
    from langsmith import traceable
except ImportError:  # pragma: no cover

    def traceable(*_args, **_kwargs):
        def decorator(func):
            return func

        return decorator
