import unittest

from log_record_backpressure_signal_tools import (
    BackpressureMonitor,
    BackpressureSignal,
    DEFAULT_THRESHOLD,
)


class FakeDepth:
    """Mutable depth provider so tests never depend on real queue state."""

    def __init__(self, value=0):
        self.value = value

    def __call__(self):
        return self.value


class BackpressureSignalTests(unittest.TestCase):
    def test_message_includes_depth_and_threshold(self):
        signal = BackpressureSignal(depth=5, threshold=3, handler_name="main")
        self.assertEqual(signal.depth, 5)
        self.assertEqual(signal.threshold, 3)
        self.assertEqual(signal.handler_name, "main")
        self.assertIn("main", signal.message)
        self.assertIn("5", signal.message)
        self.assertIn("3", signal.message)

    def test_message_without_handler_name(self):
        signal = BackpressureSignal(depth=1, threshold=1)
        self.assertIn("handler", signal.message)
        self.assertNotIn("None", signal.message)

    def test_signal_is_frozen(self):
        signal = BackpressureSignal(depth=1, threshold=1)
        with self.assertRaises(Exception):
            signal.depth = 2  # type: ignore[misc]


class BackpressureMonitorTests(unittest.TestCase):
    def test_default_threshold_is_exported(self):
        self.assertEqual(DEFAULT_THRESHOLD, 100)

    def test_no_signal_below_threshold(self):
        depth = FakeDepth(2)
        monitor = BackpressureMonitor(depth, threshold=5)
        self.assertIsNone(monitor.poll())
        self.assertEqual(monitor.signals, [])

    def test_signal_at_threshold(self):
        depth = FakeDepth(5)
        monitor = BackpressureMonitor(depth, threshold=5, handler_name="h")
        signal = monitor.poll()
        self.assertIsInstance(signal, BackpressureSignal)
        self.assertEqual(signal.depth, 5)
        self.assertEqual(signal.threshold, 5)
        self.assertEqual(signal.handler_name, "h")

    def test_signal_above_threshold(self):
        depth = FakeDepth(9)
        monitor = BackpressureMonitor(depth, threshold=5)
        signal = monitor.poll()
        self.assertIsNotNone(signal)
        self.assertEqual(signal.depth, 9)

    def test_edge_triggered_only_once_per_crossing(self):
        depth = FakeDepth(5)
        monitor = BackpressureMonitor(depth, threshold=5)
        first = monitor.poll()
        self.assertIsNotNone(first)
        depth.value = 6
        self.assertIsNone(monitor.poll())
        depth.value = 100
        self.assertIsNone(monitor.poll())
        self.assertEqual(len(monitor.signals), 1)

    def test_rearms_after_dropping_below_threshold(self):
        depth = FakeDepth(5)
        monitor = BackpressureMonitor(depth, threshold=5)
        self.assertIsNotNone(monitor.poll())
        depth.value = 4
        self.assertIsNone(monitor.poll())
        depth.value = 5
        second = monitor.poll()
        self.assertIsNotNone(second)
        self.assertEqual(len(monitor.signals), 2)

    def test_on_signal_callback_receives_signal(self):
        depth = FakeDepth(5)
        seen = []
        monitor = BackpressureMonitor(depth, threshold=5, on_signal=seen.append)
        signal = monitor.poll()
        self.assertEqual(seen, [signal])

    def test_signals_property_returns_copy(self):
        depth = FakeDepth(5)
        monitor = BackpressureMonitor(depth, threshold=5)
        monitor.poll()
        snapshot = monitor.signals
        snapshot.clear()
        self.assertEqual(len(monitor.signals), 1)

    def test_threshold_zero_emits_at_zero(self):
        depth = FakeDepth(0)
        monitor = BackpressureMonitor(depth, threshold=0)
        signal = monitor.poll()
        self.assertIsNotNone(signal)
        self.assertEqual(signal.depth, 0)

    def test_negative_threshold_rejected(self):
        with self.assertRaises(ValueError):
            BackpressureMonitor(FakeDepth(0), threshold=-1)

    def test_non_callable_depth_provider_rejected(self):
        with self.assertRaises(TypeError):
            BackpressureMonitor(5)  # type: ignore[arg-type]

    def test_non_int_depth_rejected(self):
        monitor = BackpressureMonitor(lambda: "5")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            monitor.poll()

    def test_bool_depth_rejected(self):
        # bool is an int subclass; a boolean depth is almost certainly a bug.
        monitor = BackpressureMonitor(lambda: True)
        with self.assertRaises(TypeError):
            monitor.poll()

    def test_negative_depth_rejected(self):
        monitor = BackpressureMonitor(lambda: -1)
        with self.assertRaises(ValueError):
            monitor.poll()


if __name__ == "__main__":
    unittest.main()
