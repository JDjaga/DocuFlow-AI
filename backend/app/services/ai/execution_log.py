"""AI execution log - one honest record per logical request.

WHAT THIS FILE DOES
    Records what actually happened when the provider manager ran:
    requested provider, actual provider, model, operation, duration,
    success/failure, whether fallback was used, error category, token
    usage when available, and a timestamp.

    It also keeps aggregate counters (requests, successes, failures,
    fallback events, average response time) that the health endpoint
    reports.

RULES
    - Only real events are recorded - nothing is ever invented.
    - Never stores API keys, passwords or document content.
    - Bounded memory: the newest `maxlen` events are kept.

HOW IT CONNECTS
    provider_manager.execute() -> execution_log.record()
    GET /api/health/ai        -> execution_log.snapshot()
"""
from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any


class ExecutionLog:
    """Thread-safe in-memory execution log with aggregate metrics."""

    def __init__(self, maxlen: int = 200) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=maxlen)
        self._lock = Lock()
        self._requests = 0
        self._successes = 0
        self._failures = 0
        self._fallback_events = 0
        self._duration_total_ms = 0.0

    def record(
        self,
        *,
        operation: str,
        requested_provider: str,
        provider: str,
        model: str,
        duration_ms: float,
        success: bool,
        fallback_used: bool = False,
        error_category: str | None = None,
        usage: dict[str, Any] | None = None,
    ) -> None:
        """Append one event and update the counters."""
        event = {
            "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "operation": operation,
            "requested_provider": requested_provider,
            "provider": provider,
            "model": model,
            "duration_ms": round(duration_ms, 1),
            "success": success,
            "fallback_used": fallback_used,
            "error_category": error_category,
            "tokens": dict(usage) if usage else None,
        }
        with self._lock:
            self._events.append(event)
            self._requests += 1
            self._duration_total_ms += duration_ms
            if success:
                self._successes += 1
            else:
                self._failures += 1
            if fallback_used:
                self._fallback_events += 1

    def metrics(self) -> dict[str, Any]:
        """Real counters only - zeros until the first request runs."""
        with self._lock:
            average = (
                round(self._duration_total_ms / self._requests, 1)
                if self._requests
                else 0.0
            )
            return {
                "requests": self._requests,
                "success": self._successes,
                "failed": self._failures,
                "fallback_events": self._fallback_events,
                "avg_response_time_ms": average,
            }

    def recent_fallbacks(self, limit: int = 5) -> list[dict[str, Any]]:
        """Newest fallback events with only safe fields."""
        with self._lock:
            events = [event for event in self._events if event["fallback_used"]]
        safe = [
            {
                "at": event["at"],
                "operation": event["operation"],
                "from": event["requested_provider"],
                "to": event["provider"],
                "error_category": event["error_category"],
            }
            for event in events
        ]
        return safe[-limit:]

    def snapshot(self) -> dict[str, Any]:
        """Metrics + recent fallbacks for the health endpoint."""
        return {
            "metrics": self.metrics(),
            "recent_fallbacks": self.recent_fallbacks(),
        }

    def reset(self) -> None:
        """Clear everything (used by tests)."""
        with self._lock:
            self._events.clear()
            self._requests = 0
            self._successes = 0
            self._failures = 0
            self._fallback_events = 0
            self._duration_total_ms = 0.0


# Process-wide singleton used by the provider manager.
execution_log = ExecutionLog()
