import pytest

from agent_graph import State


def test_constructs_from_mapping_and_kwargs() -> None:
    state = State({"pr_number": 42}, files=["runtime.py"])
    assert state["pr_number"] == 42
    assert state["files"] == ["runtime.py"]


def test_kwargs_override_mapping() -> None:
    assert State({"count": 1}, count=2)["count"] == 2


def test_behaves_as_a_mapping() -> None:
    state = State(a=1, b=2)
    assert len(state) == 2
    assert set(state) == {"a", "b"}
    assert "a" in state
    assert state.get("missing") is None
    assert dict(state) == {"a": 1, "b": 2}


def test_rejects_non_string_channel_names() -> None:
    with pytest.raises(TypeError, match="channel names must be str"):
        State({1: "one"})


def test_update_returns_new_snapshot_and_leaves_original_untouched() -> None:
    before = State(pr_number=42)
    after = before.update(review="LGTM")
    assert after is not before
    assert after == {"pr_number": 42, "review": "LGTM"}
    assert before == {"pr_number": 42}


def test_update_accepts_mapping_and_kwargs() -> None:
    state = State(a=1).update({"b": 2}, c=3)
    assert state == {"a": 1, "b": 2, "c": 3}


def test_equality_with_states_and_mappings() -> None:
    assert State(a=1) == State(a=1)
    assert State(a=1) == {"a": 1}
    assert State(a=1) != State(a=2)
    assert State(a=1) != "not a mapping"


def test_to_dict_returns_a_copy() -> None:
    state = State(a=1)
    snapshot = state.to_dict()
    snapshot["a"] = 99
    assert state["a"] == 1


def test_json_round_trip() -> None:
    state = State(pr_number=42, files=["runtime.py"], review=None)
    assert State.from_json(state.to_json()) == state


def test_to_json_rejects_unserializable_values() -> None:
    with pytest.raises(TypeError):
        State(handler=object()).to_json()


def test_from_json_rejects_non_object_payloads() -> None:
    with pytest.raises(ValueError, match="expected a JSON object"):
        State.from_json("[1, 2, 3]")


def test_repr_shows_channels() -> None:
    assert repr(State(a=1)) == "State({'a': 1})"
