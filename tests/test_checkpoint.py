from pathlib import Path

import pytest

from agent_graph import Checkpoint, Checkpointer, FileCheckpointer, MemoryCheckpointer, State


@pytest.fixture(params=["memory", "file"])
def checkpointer(request: pytest.FixtureRequest, tmp_path: Path) -> Checkpointer:
    if request.param == "memory":
        return MemoryCheckpointer()
    return FileCheckpointer(tmp_path / "checkpoints")


def checkpoint(run_id: str = "pr-42", step: int = 0, node: str = "fetch_diff") -> Checkpoint:
    return Checkpoint(run_id, step, node, State(pr_number=42, step=step))


def test_checkpoint_json_round_trip() -> None:
    original = Checkpoint("pr-42", 3, "review", State(files=["runtime.py"], notes=None))
    restored = Checkpoint.from_json(original.to_json())
    assert restored == original


def test_checkpoint_rejects_unsafe_run_ids() -> None:
    for run_id in ["", "pr/42", "../up", ".hidden", "pr 42"]:
        with pytest.raises(ValueError, match="run_id"):
            checkpoint(run_id=run_id)


def test_checkpoint_rejects_run_ids_containing_newlines() -> None:
    # A `$` anchor also matches before a trailing newline, so an id straight
    # off readline() must not slip through and mint its own run directory.
    for run_id in ["pr-42\n", "pr-42\r\n", "pr\n42", "pr-42\n\n", "pr-42\nx"]:
        with pytest.raises(ValueError, match="run_id"):
            checkpoint(run_id=run_id)


def test_checkpoint_rejects_negative_step() -> None:
    with pytest.raises(ValueError, match="step"):
        checkpoint(step=-1)


def test_checkpoint_rejects_empty_node() -> None:
    with pytest.raises(ValueError, match="node"):
        checkpoint(node="")


def test_checkpoint_rejects_non_state_state() -> None:
    with pytest.raises(TypeError, match="state must be a State"):
        Checkpoint("pr-42", 0, "fetch_diff", {"pr_number": 42})  # type: ignore[arg-type]


def test_checkpoint_to_json_applies_state_contract() -> None:
    unserializable = Checkpoint("pr-42", 0, "fetch_diff", State(handler=object()))
    with pytest.raises(TypeError):
        unserializable.to_json()
    lossy = Checkpoint("pr-42", 0, "fetch_diff", State(point=(1, 2)))
    with pytest.raises(ValueError, match="would not survive"):
        lossy.to_json()


def test_checkpoint_from_json_rejects_non_object_payloads() -> None:
    with pytest.raises(ValueError, match="expected a JSON object"):
        Checkpoint.from_json("[1, 2, 3]")


def test_checkpoint_from_json_rejects_wrong_fields() -> None:
    with pytest.raises(ValueError, match="expected fields"):
        Checkpoint.from_json('{"run_id": "pr-42", "step": 0}')


def test_checkpoint_from_json_rejects_non_object_state() -> None:
    payload = '{"node": "n", "run_id": "pr-42", "state": [1], "step": 0}'
    with pytest.raises(ValueError, match="state must be a JSON object"):
        Checkpoint.from_json(payload)


def test_checkpointer_contract_is_abstract() -> None:
    with pytest.raises(TypeError):
        Checkpointer()  # type: ignore[abstract]


def test_save_then_load_latest(checkpointer: Checkpointer) -> None:
    saved = checkpoint()
    checkpointer.save(saved)
    assert checkpointer.load_latest("pr-42") == saved


def test_latest_is_the_highest_step(checkpointer: Checkpointer) -> None:
    for step, node in enumerate(["fetch_diff", "review", "summarize"]):
        checkpointer.save(checkpoint(step=step, node=node))
    latest = checkpointer.load_latest("pr-42")
    assert latest is not None
    assert (latest.step, latest.node) == (2, "summarize")


def test_load_history_returns_oldest_first(checkpointer: Checkpointer) -> None:
    saved = [checkpoint(step=step) for step in range(3)]
    for one in saved:
        checkpointer.save(one)
    assert checkpointer.load_history("pr-42") == saved


def test_unknown_run_has_no_checkpoints(checkpointer: Checkpointer) -> None:
    assert checkpointer.load_latest("pr-42") is None
    assert checkpointer.load_history("pr-42") == []


def test_unsaveable_run_id_has_no_checkpoints(checkpointer: Checkpointer) -> None:
    for run_id in ["../escape", "pr-42\n", "pr\n42"]:
        assert checkpointer.load_latest(run_id) is None
        assert checkpointer.load_history(run_id) == []


def test_file_newline_run_id_never_reaches_the_filesystem(tmp_path: Path) -> None:
    root = tmp_path / "checkpoints"
    saver = FileCheckpointer(root)
    saver.save(checkpoint(run_id="pr-42", step=0))
    assert saver.load_latest("pr-42\n") is None
    assert [path.name for path in root.iterdir()] == ["pr-42"]


def test_save_rejects_non_increasing_steps(checkpointer: Checkpointer) -> None:
    checkpointer.save(checkpoint(step=1))
    for step in [0, 1]:
        with pytest.raises(ValueError, match="not after the last saved step"):
            checkpointer.save(checkpoint(step=step))
    checkpointer.save(checkpoint(step=2))


def test_runs_are_isolated(checkpointer: Checkpointer) -> None:
    checkpointer.save(checkpoint(run_id="pr-42", step=0))
    checkpointer.save(checkpoint(run_id="pr-43", step=5))
    latest = checkpointer.load_latest("pr-42")
    assert latest is not None
    assert latest.step == 0
    assert len(checkpointer.load_history("pr-43")) == 1


def test_file_checkpoints_survive_a_restart(tmp_path: Path) -> None:
    root = tmp_path / "checkpoints"
    for step in range(2):
        FileCheckpointer(root).save(checkpoint(step=step))
    revived = FileCheckpointer(root)  # a fresh process
    latest = revived.load_latest("pr-42")
    assert latest is not None
    assert latest.step == 1
    assert [one.step for one in revived.load_history("pr-42")] == [0, 1]


def test_file_kill_mid_write_keeps_last_completed_checkpoint(tmp_path: Path) -> None:
    root = tmp_path / "checkpoints"
    FileCheckpointer(root).save(checkpoint(step=0))
    # A kill mid-write leaves a partial temporary file, never a partial .json.
    (root / "pr-42" / "00000001.tmp").write_text('{"run_id": "pr-42", "st', encoding="utf-8")
    latest = FileCheckpointer(root).load_latest("pr-42")
    assert latest is not None
    assert latest.step == 0
    # The interrupted step can be saved again on resume.
    FileCheckpointer(root).save(checkpoint(step=1))


def test_file_ignores_foreign_files(tmp_path: Path) -> None:
    root = tmp_path / "checkpoints"
    saver = FileCheckpointer(root)
    saver.save(checkpoint(step=0))
    (root / "pr-42" / "notes.txt").write_text("not a checkpoint", encoding="utf-8")
    assert len(saver.load_history("pr-42")) == 1


def test_file_rejects_a_file_that_does_not_match_its_location(tmp_path: Path) -> None:
    root = tmp_path / "checkpoints"
    saver = FileCheckpointer(root)
    saver.save(checkpoint(run_id="pr-42", step=0))
    moved = (root / "pr-42" / "00000000.json").read_text(encoding="utf-8")
    (root / "pr-43").mkdir()
    (root / "pr-43" / "00000000.json").write_text(moved, encoding="utf-8")
    with pytest.raises(ValueError, match="does not match its location"):
        saver.load_latest("pr-43")
