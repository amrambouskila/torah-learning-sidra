"""The shape a long job reports its progress in.

A callback rather than a job passed down into the crawler: the catalog and calendar modules know
nothing about jobs, screens or HTTP, and giving them a `Job` to mutate would be the first thread
tying them to the API layer.
"""

from __future__ import annotations

from collections.abc import Callable

OnProgress = Callable[[str, int, int], None]
"""``(phase, done, total)``. Called from inside the work, so it must be cheap and must not raise."""
