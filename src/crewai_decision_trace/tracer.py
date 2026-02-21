from __future__ import annotations

from functools import wraps
from typing import Any, Callable

_DEFAULT_EMITTER: Any | None = None


def set_default_emitter(emitter: Any) -> None:
    """Set the process-wide default emitter used by trace_decision."""
    global _DEFAULT_EMITTER
    _DEFAULT_EMITTER = emitter


def trace_decision(policy_id: str | None = None) -> Callable[[Callable[..., dict[str, Any]]], Callable[..., dict[str, Any]]]:
    """Decorator for decision builders that emit returned event dicts."""

    def decorator(func: Callable[..., dict[str, Any]]) -> Callable[..., dict[str, Any]]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            event = func(*args, **kwargs)
            if _DEFAULT_EMITTER is None:
                raise RuntimeError(
                    "Default decision emitter is not set. Call set_default_emitter(emitter) before traced decisions."
                )

            if (
                policy_id is not None
                and isinstance(event, dict)
                and isinstance(event.get("context"), dict)
                and "policy_id" not in event["context"]
            ):
                event["context"]["policy_id"] = policy_id

            _DEFAULT_EMITTER.emit(event)
            return event

        return wrapper

    return decorator
