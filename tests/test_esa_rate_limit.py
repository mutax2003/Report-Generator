"""Tests for rate limiting."""

from __future__ import annotations

import os
import unittest

from esa_rate_limit import RateLimitExceeded, check_rate_limit, reset_rate_limits


class RateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_rate_limits()
        self._prev_max = os.environ.get("ESA_RATE_LIMIT_MAX")
        os.environ["ESA_RATE_LIMIT_MAX"] = "2"

    def tearDown(self) -> None:
        reset_rate_limits()
        if self._prev_max is None:
            os.environ.pop("ESA_RATE_LIMIT_MAX", None)
        else:
            os.environ["ESA_RATE_LIMIT_MAX"] = self._prev_max

    def test_allows_under_cap(self) -> None:
        check_rate_limit("client-a")
        check_rate_limit("client-a")

    def test_blocks_over_cap(self) -> None:
        check_rate_limit("client-b")
        check_rate_limit("client-b")
        with self.assertRaises(RateLimitExceeded):
            check_rate_limit("client-b")

    def test_disable_rate_limit_env(self) -> None:
        prev = os.environ.get("ESA_DISABLE_RATE_LIMIT")
        os.environ["ESA_DISABLE_RATE_LIMIT"] = "1"
        try:
            check_rate_limit("client-c")
            check_rate_limit("client-c")
            check_rate_limit("client-c")  # would raise if enabled with MAX=2
        finally:
            if prev is None:
                os.environ.pop("ESA_DISABLE_RATE_LIMIT", None)
            else:
                os.environ["ESA_DISABLE_RATE_LIMIT"] = prev
            reset_rate_limits()

    def test_failed_auth_bucket_is_separate_from_render_quota(self) -> None:
        from esa_rate_limit import record_failed_auth

        prev = os.environ.get("ESA_AUTH_FAIL_MAX")
        os.environ["ESA_AUTH_FAIL_MAX"] = "2"
        try:
            record_failed_auth("ip:10.0.0.5")
            record_failed_auth("ip:10.0.0.5")
            with self.assertRaises(RateLimitExceeded):
                record_failed_auth("ip:10.0.0.5")
            # Failures never consume the authenticated render quota (MAX=2 here).
            check_rate_limit("key:abc")
            check_rate_limit("key:abc")
            # Another IP is unaffected.
            record_failed_auth("ip:10.0.0.6")
        finally:
            if prev is None:
                os.environ.pop("ESA_AUTH_FAIL_MAX", None)
            else:
                os.environ["ESA_AUTH_FAIL_MAX"] = prev

    def test_failed_auth_map_has_hard_cap_and_constant_time_inserts(self) -> None:
        """Many distinct IPs must not grow the map unbounded or make inserts O(n)."""
        import time

        import esa_rate_limit
        from esa_rate_limit import record_failed_auth

        cap = esa_rate_limit._AUTH_FAIL_MAX_TRACKED
        total = cap * 2 + 500
        started = time.perf_counter()
        for i in range(total):
            record_failed_auth(f"ip:10.{i // 65536}.{(i // 256) % 256}.{i % 256}")
        elapsed = time.perf_counter() - started
        self.assertLessEqual(len(esa_rate_limit._auth_failures), cap)
        # O(n) scans under the lock took ~45 s for 8k IPs; O(1) amortized is well under this.
        self.assertLess(elapsed, 10.0, f"{total} inserts took {elapsed:.1f}s")
        # Oldest entries are evicted first; the newest are still tracked.
        self.assertNotIn("ip:10.0.0.0", esa_rate_limit._auth_failures)
        last = total - 1
        newest = f"ip:10.{last // 65536}.{(last // 256) % 256}.{last % 256}"
        self.assertIn(newest, esa_rate_limit._auth_failures)

    def test_failed_auth_limit_survives_other_traffic_within_cap(self) -> None:
        from esa_rate_limit import record_failed_auth

        prev = os.environ.get("ESA_AUTH_FAIL_MAX")
        os.environ["ESA_AUTH_FAIL_MAX"] = "2"
        try:
            record_failed_auth("ip:192.0.2.1")
            record_failed_auth("ip:192.0.2.1")
            for i in range(200):
                record_failed_auth(f"ip:198.51.100.{i}")
            with self.assertRaises(RateLimitExceeded):
                record_failed_auth("ip:192.0.2.1")
        finally:
            if prev is None:
                os.environ.pop("ESA_AUTH_FAIL_MAX", None)
            else:
                os.environ["ESA_AUTH_FAIL_MAX"] = prev


if __name__ == "__main__":
    unittest.main()
