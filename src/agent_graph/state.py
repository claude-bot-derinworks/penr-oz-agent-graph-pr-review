"""The typed payload that flows node to node.

`State` is an immutable mapping of string channels to values. Nodes never mutate
a state in place; they call :meth:`State.update` to produce a new snapshot that
shares unchanged values with its predecessor (copy-on-write). The reasoning
behind this choice is documented in ``docs/state.md``.
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping
from typing import Any

__all__ = ["State"]


class State(Mapping[str, Any]):
    """An immutable snapshot of the data flowing through the graph.

    Behaves as a read-only ``Mapping[str, Any]`` keyed by channel name. Values
    must be JSON-serializable for a snapshot to be checkpointable; this is
    enforced at serialization time, not on construction.
    """

    __slots__ = ("_channels",)

    def __init__(self, channels: Mapping[str, Any] | None = None, /, **kwargs: Any) -> None:
        merged = {**(channels or {}), **kwargs}
        for key in merged:
            if not isinstance(key, str):
                raise TypeError(f"channel names must be str, got {type(key).__name__}: {key!r}")
        self._channels: dict[str, Any] = merged

    def __getitem__(self, key: str) -> Any:
        return self._channels[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._channels)

    def __len__(self) -> int:
        return len(self._channels)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, State):
            return self._channels == other._channels
        if isinstance(other, Mapping):
            return self._channels == dict(other)
        return NotImplemented

    def __repr__(self) -> str:
        return f"{type(self).__name__}({self._channels!r})"

    def update(self, changes: Mapping[str, Any] | None = None, /, **kwargs: Any) -> State:
        """Return a new snapshot with ``changes`` applied; ``self`` is untouched."""
        return State(self._channels, **{**(changes or {}), **kwargs})

    def to_dict(self) -> dict[str, Any]:
        """Return the channels as a plain dict (a shallow copy)."""
        return dict(self._channels)

    def to_json(self) -> str:
        """Serialize to a JSON object string.

        Raises ``TypeError`` if a channel value is not JSON-serializable, and
        ``ValueError`` if a value would not survive the round trip unchanged —
        JSON silently turns tuples into lists and non-string mapping keys into
        strings, which would corrupt a restored checkpoint.
        """
        payload = json.dumps(self._channels, sort_keys=True)
        restored = json.loads(payload)
        if restored != self._channels:
            lossy = sorted(
                name for name, value in self._channels.items() if restored[name] != value
            )
            raise ValueError(
                f"channels {lossy} would not survive a JSON round trip unchanged "
                "(tuples become lists, non-string mapping keys become strings); "
                "store JSON-native values instead"
            )
        return payload

    @classmethod
    def from_json(cls, payload: str) -> State:
        """Rebuild a snapshot from :meth:`to_json` output."""
        channels = json.loads(payload)
        if not isinstance(channels, dict):
            raise ValueError(f"expected a JSON object, got {type(channels).__name__}")
        return cls(channels)
