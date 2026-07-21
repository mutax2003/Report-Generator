"""Tests for observability helpers."""

from __future__ import annotations

import unittest

from esa_observability import increment, observe_duration, reset_metrics, snapshot_metrics


class ObservabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_metrics()

    def test_counters_and_timers(self) -> None:
        increment("render.success")
        with observe_duration("render.duration"):
            pass
        snap = snapshot_metrics()
        self.assertEqual(snap["counters"]["render.success"], 1)
        self.assertIn("render.duration", snap["timers"])


if __name__ == "__main__":
    unittest.main()
