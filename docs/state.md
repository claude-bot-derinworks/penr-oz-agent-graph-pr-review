# State

`agent_graph.State` is the typed payload that flows node to node: an immutable
`Mapping[str, Any]` of named channels. A node reads the channels it needs and returns
`state.update(...)` — a new snapshot with its changes applied. The original snapshot is never
modified.

```python
from agent_graph import State

state = State(pr_number=42, files=["runtime.py"])
after = state.update(review="LGTM")

state.get("review")  # None — the old snapshot is untouched
after["review"]  # "LGTM"
State.from_json(after.to_json()) == after  # True — snapshots round-trip through JSON
```

## The trade-off: mutate in place vs. copy on write

Two ways a node can hand data to the next node were considered.

**Mutate in place.** The graph allocates one state object and every node writes into it.

- Cheapest possible updates: no allocation, no copying, however large the state grows.
- One node's write is instantly visible to everything holding the reference — including nodes
  running on a parallel branch, and including "past" states a checkpointer thought it had saved.
  Checkpointing requires an explicit deep copy at every save point, and replaying a run requires
  trusting that nothing aliased the saved copies.
- Bugs hide well: a misbehaving node can clobber a channel it doesn't own and the damage is only
  observed downstream, with no record of which node wrote what.

**Copy on write.** Every update produces a new snapshot; old snapshots stay valid forever.

- A checkpoint is just a reference to the snapshot that crossed an edge — saving is free, and
  replay/time-travel debugging fall out naturally: the history of a run is the list of snapshots.
- Conditional edges and fan-out are safe by construction: two branches receiving the same
  snapshot cannot observe each other's writes.
- Each update shallow-copies the channel dict: O(number of channels) per node step, and values
  are shared between snapshots rather than copied.

## Decision: copy on write

This runtime exists for checkpointing and conditional edges, which is exactly where in-place
mutation is weakest. State here is a small dict of channels (a PR number, a file list, review
notes — not tensors), so the shallow copy per node step costs nanoseconds while buying free
checkpoints, safe branching, and a replayable history. We pay O(channels) per update to make
every edge crossing a durable fact.

Two consequences of the choice:

- **Values are shared, not copied.** The snapshot is immutable; the values inside it are
  whatever you put there. Mutating a list you stored in one snapshot mutates it in every
  snapshot that shares it — treat channel values as immutable, replacing rather than mutating
  them (`update(files=[*state["files"], new_file])`).
- **Serialization is the contract.** Checkpointing means `to_json()` / `from_json()`, so channel
  names are strings and values must be JSON-serializable. This is enforced when a snapshot is
  serialized, not on construction, so in-memory-only runs may carry richer values at their own
  risk.
