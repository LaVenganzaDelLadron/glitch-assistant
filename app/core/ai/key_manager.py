"""Thread-safe API key selection and cooldown tracking."""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable

from app.config.settings import ApiKeyConfig

logger = logging.getLogger(__name__)


class AllApiKeysUnavailableError(RuntimeError):
    """Raised when every configured key is cooling down or excluded."""


@dataclass(frozen=True)
class ApiKeyLease:
    """The credential selected for one request attempt."""

    slot: int
    key: str


@dataclass
class _KeyState:
    config: ApiKeyConfig
    cooldown_until: float = 0.0
    consecutive_rate_limits: int = 0


class ApiKeyManager:
    """Select keys in round-robin order while safely respecting cooldowns."""

    def __init__(
        self,
        keys: Iterable[ApiKeyConfig],
        *,
        rate_limit_cooldown_seconds: float = 60.0,
        temporary_failure_cooldown_seconds: float = 5.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        configs = tuple(keys)
        if not configs:
            raise ValueError("ApiKeyManager needs at least one API key.")
        if len({config.slot for config in configs}) != len(configs):
            raise ValueError("API key slots must be unique.")
        self._states = [_KeyState(config) for config in configs]
        self._next_index = 0
        self._rate_limit_cooldown_seconds = rate_limit_cooldown_seconds
        self._temporary_failure_cooldown_seconds = temporary_failure_cooldown_seconds
        self._clock = clock
        self._lock = threading.RLock()

    def acquire(self, *, excluded_slots: Iterable[int] = ()) -> ApiKeyLease:
        """Return the next non-cooling-down, non-excluded key in round-robin order."""
        excluded = set(excluded_slots)
        now = self._clock()
        with self._lock:
            for offset in range(len(self._states)):
                index = (self._next_index + offset) % len(self._states)
                state = self._states[index]
                if state.config.slot in excluded or state.cooldown_until > now:
                    continue
                self._next_index = (index + 1) % len(self._states)
                logger.info("Using Groq API key slot %s", state.config.slot)
                return ApiKeyLease(slot=state.config.slot, key=state.config.key)
        raise AllApiKeysUnavailableError(self._unavailable_message(excluded))

    def record_success(self, lease: ApiKeyLease) -> None:
        with self._lock:
            self._state_for(lease.slot).consecutive_rate_limits = 0

    def record_rate_limit(self, lease: ApiKeyLease) -> None:
        """Cool a rate-limited key down, with bounded escalating backoff."""
        with self._lock:
            state = self._state_for(lease.slot)
            state.consecutive_rate_limits += 1
            multiplier = min(state.consecutive_rate_limits, 5)
            delay = self._rate_limit_cooldown_seconds * multiplier
            state.cooldown_until = max(state.cooldown_until, self._clock() + delay)
            logger.warning("Groq API key slot %s rate limited; cooling down for %.1fs", lease.slot, delay)

    def record_temporary_failure(self, lease: ApiKeyLease) -> None:
        with self._lock:
            state = self._state_for(lease.slot)
            state.cooldown_until = max(
                state.cooldown_until,
                self._clock() + self._temporary_failure_cooldown_seconds,
            )
            logger.warning("Groq API key slot %s had a temporary failure; cooling down", lease.slot)

    def _state_for(self, slot: int) -> _KeyState:
        for state in self._states:
            if state.config.slot == slot:
                return state
        raise ValueError(f"Unknown API key slot {slot}.")

    def _unavailable_message(self, excluded: set[int]) -> str:
        available_later = [state for state in self._states if state.config.slot not in excluded]
        if available_later:
            retry_after = max(0.0, min(state.cooldown_until for state in available_later) - self._clock())
            return f"All eligible Groq API keys are cooling down; retry in about {retry_after:.1f}s."
        return "All eligible Groq API keys were exhausted for this request."
