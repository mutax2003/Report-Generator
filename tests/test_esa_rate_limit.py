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


if __name__ == "__main__":
    unittest.main()
