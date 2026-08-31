from __future__ import annotations

import threading
import unittest
from types import SimpleNamespace

from app.config.settings import ApiKeyConfig
from app.core.ai.groq import GroqProvider
from app.core.ai.key_manager import AllApiKeysUnavailableError, ApiKeyManager


def make_keys(count: int = 5) -> tuple[ApiKeyConfig, ...]:
    return tuple(ApiKeyConfig(slot=index, key=f"test-key-{index}") for index in range(1, count + 1))


class ApiKeyManagerTests(unittest.TestCase):
    def test_round_robin_distributes_ten_requests_across_five_slots(self) -> None:
        manager = ApiKeyManager(make_keys())

        slots = [manager.acquire().slot for _ in range(10)]

        self.assertEqual(slots, [1, 2, 3, 4, 5, 1, 2, 3, 4, 5])

    def test_rate_limited_key_is_skipped_until_cooldown_expires(self) -> None:
        now = [100.0]
        manager = ApiKeyManager(make_keys(2), rate_limit_cooldown_seconds=10, clock=lambda: now[0])

        first = manager.acquire()
        manager.record_rate_limit(first)

        self.assertEqual(manager.acquire().slot, 2)
        with self.assertRaises(AllApiKeysUnavailableError):
            manager.acquire(excluded_slots={2})

        now[0] += 10
        self.assertEqual(manager.acquire().slot, 1)

    def test_excluded_slots_prevent_reusing_a_key_during_one_request(self) -> None:
        manager = ApiKeyManager(make_keys(2))
        first = manager.acquire()

        second = manager.acquire(excluded_slots={first.slot})

        self.assertEqual((first.slot, second.slot), (1, 2))
        with self.assertRaises(AllApiKeysUnavailableError):
            manager.acquire(excluded_slots={1, 2})

    def test_concurrent_acquires_are_race_free(self) -> None:
        manager = ApiKeyManager(make_keys())
        barrier = threading.Barrier(5)
        slots: list[int] = []
        result_lock = threading.Lock()

        def acquire_slot() -> None:
            barrier.wait()
            slot = manager.acquire().slot
            with result_lock:
                slots.append(slot)

        threads = [threading.Thread(target=acquire_slot) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sorted(slots), [1, 2, 3, 4, 5])

    def test_provider_rotates_to_next_slot_after_a_retryable_failure(self) -> None:
        calls: list[str] = []
        success = object()

        def client_factory(key: str):
            def create(**_kwargs):
                calls.append(key)
                if key == "test-key-1":
                    raise RuntimeError("simulated rate limit")
                return success

            return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))

        provider = GroqProvider(
            api_keys=make_keys(2),
            base_url="https://example.invalid/v1",
            model="test-model",
            timeout=1,
            max_api_attempts=2,
            client_factory=client_factory,
        )
        provider._retry_action = lambda _error: "rate_limit"  # type: ignore[method-assign]

        response = provider._create_completion_with_rotation({"model": "test-model", "messages": []})

        self.assertIs(response, success)
        self.assertEqual(calls, ["test-key-1", "test-key-2"])


if __name__ == "__main__":
    unittest.main()
