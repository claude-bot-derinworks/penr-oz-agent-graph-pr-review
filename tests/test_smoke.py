import agent_graph


def test_package_imports_and_has_version() -> None:
    assert agent_graph.__version__ == "0.1.0"
