# log_record_backpressure_signal_tools

Monitors a handler queue depth and emits a structured warning event when depth
crosses a configurable threshold.

```python
from log_record_backpressure_signal_tools import BackpressureMonitor

queue = []

def depth():
    return len(queue)

monitor = BackpressureMonitor(depth, threshold=3, handler_name="audit")

queue.extend(["a", "b", "c"])
signal = monitor.poll()
print(signal.message)
# audit queue depth 3 reached threshold 3
```

## Why this exists

A logging handler that accepts records faster than it can flush will grow its
queue without bound, and the first sign of trouble is usually an out-of-memory
kill. The useful moment to warn is the moment the queue crosses a line, not on
every record while it stays deep. This library is edge-triggered for that
reason: one warning per crossing.

The trade-off is that the monitor does not own the queue. It takes a callable
that returns the current depth. That keeps it free of threading assumptions
and makes it trivial to test, at the cost of trusting the caller's callable.

## The awkward edge

The monitor emits once when depth first reaches the threshold and then stays
quiet until depth drops strictly below the threshold. If your queue hovers
exactly at the threshold, you will get exactly one signal, not a stream. If you
want a signal every time depth changes, call `poll()` yourself and compare
`monitor.signals` between calls.

## API

- `BackpressureMonitor(depth_provider, threshold=100, handler_name=None, on_signal=None)`
- `BackpressureMonitor.poll()` returns a `BackpressureSignal` or `None`.
- `BackpressureMonitor.signals` returns a copy of every signal emitted so far.
- `BackpressureMonitor.threshold` and `BackpressureMonitor.handler_name` expose
the configured values.
- `BackpressureSignal` is a frozen dataclass with `depth`, `threshold`,
  `handler_name`, and a derived `message`.
- `DEFAULT_THRESHOLD` is `100`.

`depth_provider` must return a non-negative `int`; booleans and other types are
rejected. A negative `threshold` is rejected at construction time.
