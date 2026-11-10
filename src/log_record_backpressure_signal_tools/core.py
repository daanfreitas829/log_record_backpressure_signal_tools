"""Core backpressure signal logic.

The monitor watches a handler queue depth and emits a structured warning event
once depth crosses a configurable threshold. The event is a plain dataclass so
it can be serialised by whatever logging pipeline the caller already uses
without this library taking a dependency on one.

Design decision: the monitor does not own the queue. It is given a callable
that returns the current depth. That keeps the monitor free of threading and
container assumptions, and makes it trivially testable with a fake depth
provider. The trade-off is that the caller must supply a correct callable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

#: Threshold used when the caller does not specify one. Chosen to match the
#: common "queue is getting long" default seen in logging handlers.
DEFAULT_THRESHOLD = 100


@dataclass(frozen=True)
class BackpressureSignal:
    """A structured warning event emitted when queue depth crosses a threshold.

    Attributes:
        depth: The queue depth observed when the signal was emitted.
        threshold: The threshold that was crossed.
        handler_name: Optional name of the handler the queue belongs to.
        message: Human-readable summary, derived from the other fields.
    """

    depth: int
    threshold: int
    handler_name: Optional[str] = None
    message: str = field(init=False)

    def __post_init__(self) -> None:
        # Compute the message once at construction so every consumer sees the
        # same text and no consumer has to know how to format it.
        subject = self.handler_name if self.handler_name else "handler"
        object.__setattr__(
            self,
            "message",
            f"{subject} queue depth {self.depth} reached threshold {self.threshold}",
        )


class BackpressureMonitor:
    """Watches a depth provider and emits signals when depth crosses a threshold.

    The monitor is edge-triggered: it emits once when depth first crosses the
    threshold, and does not emit again until depth drops back below the
    threshold and crosses again. This avoids flooding the log with one signal
    per record while the queue stays deep.

    Parameters:
        depth_provider: Callable returning the current queue depth as an int.
        threshold: Depth at or above which a signal is emitted.
        handler_name: Optional label included in emitted signals.
        on_signal: Optional callback invoked with each emitted signal.
    """

    def __init__(
        self,
        depth_provider: Callable[[], int],
        threshold: int = DEFAULT_THRESHOLD,
        handler_name: Optional[str] = None,
        on_signal: Optional[Callable[[BackpressureSignal], None]] = None,
    ) -> None:
        if not callable(depth_provider):
            raise TypeError("depth_provider must be callable")
        if threshold < 0:
            raise ValueError("threshold must be non-negative")
        self._depth_provider = depth_provider
        self._threshold = threshold
        self._handler_name = handler_name
        self._on_signal = on_signal
        self._armed = True
        self._signals: List[BackpressureSignal] = []

    @property
    def threshold(self) -> int:
        """The configured threshold."""
        return self._threshold

    @property
    def handler_name(self) -> Optional[str]:
        """The configured handler name, if any."""
        return self._handler_name

    @property
    def signals(self) -> List[BackpressureSignal]:
        """Signals emitted so far, in emission order.

        A copy is returned so callers cannot mutate the monitor's history.
        """
        return list(self._signals)

    def poll(self) -> Optional[BackpressureSignal]:
        """Check the current depth and emit a signal if the edge is crossed.

        Returns the emitted signal, or ``None`` if no signal was emitted on
        this poll.
        """
        depth = self._depth_provider()
        if not isinstance(depth, int) or isinstance(depth, bool):
            raise TypeError("depth_provider must return an int")
        if depth < 0:
            raise ValueError("depth_provider returned a negative depth")

        if depth < self._threshold:
            # Depth is below the threshold; re-arm so the next crossing emits.
            self._armed = True
            return None

        if not self._armed:
            # Already emitted for this crossing; stay quiet until re-armed.
            return None

        self._armed = False
        signal = BackpressureSignal(
            depth=depth,
            threshold=self._threshold,
            handler_name=self._handler_name,
        )
        self._signals.append(signal)
        if self._on_signal is not None:
            self._on_signal(signal)
        return signal
