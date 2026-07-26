# Checkpointing

A `Checkpoint` is the `State` as it stood after one node finished, tagged with the run it
belongs to (`run_id`), its position in that run (`step`, strictly increasing from 0), and the
`node` that produced it. A `Checkpointer` persists one after every node so that a killed run
resumes from the last completed node instead of restarting:

```python
from agent_graph import Checkpoint, FileCheckpointer, State

saver = FileCheckpointer("checkpoints")
saver.save(Checkpoint("pr-42", 0, "fetch_diff", State(pr_number=42)))
# ...process dies...

saver = FileCheckpointer("checkpoints")  # new process
latest = saver.load_latest("pr-42")
# resume from latest.state at latest.step + 1; load_history() replays the run
```

Two backends ship: `MemoryCheckpointer` (a dict — for tests and in-process replay) and
`FileCheckpointer` (one JSON file per checkpoint under `root/<run_id>/<step>.json`).

## Decisions

- **A crash can never corrupt the latest checkpoint.** `FileCheckpointer` writes each
  checkpoint to a temporary name, fsyncs, and atomically renames it into place. A checkpoint
  therefore exists complete or not at all; killing the process mid-write leaves the previous
  checkpoint as the latest, which is exactly the last node that actually finished. Leftover
  `*.tmp` files are ignored by loading.
- **Steps strictly increase within a run.** `save` rejects a step at or below the last saved
  one. This keeps "latest" unambiguous across backends and makes `load_history` a faithful,
  ordered replay of the run — the history of a run *is* the list of snapshots, as
  [docs/state.md](state.md) intends.
- **Serialization is `State`'s contract.** A checkpoint serializes its state through
  `State.to_json`, so the same refusals apply: values JSON cannot represent raise `TypeError`,
  and values JSON would silently alter (tuples, non-string mapping keys) raise `ValueError`.
  A checkpoint that restores to different data is worse than no checkpoint.
- **Run ids are backend-portable.** `run_id` is restricted to `[A-Za-z0-9._-]` (no leading
  `.`), so the same id keys a dict, a directory name, or a future database row without
  escaping. Loading an id that could never have been saved returns nothing rather than
  touching the filesystem.
- **Files self-identify.** Each file embeds its `run_id` and `step`; loading verifies they
  match the file's location and refuses mismatched (moved or hand-edited) files.
