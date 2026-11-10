"""Public API for log_record_backpressure_signal_tools.

Only the names re-exported here are part of the supported surface. Keeping the
surface small makes it obvious what callers may rely on and what is an internal
detail free to change.
"""

from .core import (
    BackpressureMonitor,
    BackpressureSignal,
    DEFAULT_THRESHOLD,
)

__all__ = [
    "BackpressureMonitor",
    "BackpressureSignal",
    "DEFAULT_THRESHOLD",
]
