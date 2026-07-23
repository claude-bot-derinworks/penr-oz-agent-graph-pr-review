# penr-oz-agent-graph-pr-review

A minimal agentic graph runtime — typed state, conditional edges, checkpointing, and a worked PR-review example.

## Status

Early scaffolding. The `agent_graph` package is a stub; the runtime (typed state, conditional
edges, checkpointing) and the PR-review example land in upcoming milestones.

## Requirements

- Python 3.11+

## Getting started

```bash
git clone https://github.com/derinworks/penr-oz-agent-graph-pr-review.git
cd penr-oz-agent-graph-pr-review
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

## Development

```bash
ruff check .          # lint
ruff format --check . # formatting
pytest                # tests
```

CI runs the same three steps on Python 3.11–3.13 for every push to `main` and every pull request.

## Project layout

```
src/agent_graph/   # the runtime package
tests/             # test suite
```

## License

[MIT](LICENSE)
