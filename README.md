# Personal Devin

## Core Mission

Personal Devin is a production-focused autonomous engineering system that converts natural-language goals into deterministic execution plans and reliable implementation workflows.

Agent 01 in this repository is the Task Decomposition Engine, responsible for:
- Turning a user goal into a structured plan.
- Building and validating a dependency DAG.
- Producing deterministic task execution order.

## Operating Principles

- Determinism first: same input and rules produce stable execution order.
- Explicit dependency management: all task relationships are represented in a DAG.
- No hidden logic: planning behavior is inspectable in rule definitions and graph code.
- Production validation: cycle checks, input validation, and test-enforced behavior.
- Modular architecture: decomposition logic is rule-based and extensible for future LLM augmentation.

## Agent Execution Model

Agent execution follows a strict pipeline:
1. Receive goal string.
2. Decompose goal into atomic tasks using rule-based logic.
3. Build dependency DAG from decomposed tasks.
4. Validate DAG has no cycles.
5. Topologically sort tasks in deterministic order.
6. Return a `Plan` object containing ordered `Task` objects.

Public entrypoint:
- `create_plan(goal: str) -> Plan` in `app/planning/planner.py`

## Repository Structure

```text
personal-devin/
├── app/
│   ├── core/
│   │   └── logger.py
│   └── planning/
│       ├── models.py
│       ├── planner.py
│       ├── task_decomposer.py
│       └── task_graph.py
├── tests/
│   ├── test_basic.py
│   └── test_task_decomposer.py
├── README.md
└── requirements.txt
```

## Development Workflow

Use a strict delivery workflow for all agent changes:
1. Branch: create a feature branch from `main`.
2. Implement: make focused, deterministic, test-covered changes.
3. Test: run `python -m pytest tests/` locally.
4. PR: open pull request with implementation summary and test evidence.
5. CI: require passing checks before merge.
6. Merge: squash or merge only after review approval and green CI.

## CI Enforcement

All changes should be blocked from merge unless:
- Unit/integration tests pass.
- No cycle-detection regressions are introduced.
- Planner flow remains: decompose -> DAG build -> validate -> return.
- Public interfaces remain typed and documented.

Recommended minimum CI checks:
- `python -m pytest tests/`
- Static lint/type checks as the project evolves.

## Agent 01 - Task Decomposition Engine

### What It Builds

Agent 01 converts a natural-language goal into a typed, validated `Plan` made of atomic `Task` entries with dependencies, priorities, and deterministic execution order.

### Architecture

- `app/planning/models.py`
  - Pydantic models for `Task` and `Plan`.
  - Strict typing for status, dependencies, metadata, and identifiers.

- `app/planning/task_decomposer.py`
  - Rule-based decomposition engine.
  - Pattern-specific strategies for domains such as API, database, and frontend.
  - Generic decomposition fallback for unmatched goals.
  - Designed for future LLM integration by keeping decomposition modular.

- `app/planning/task_graph.py`
  - DAG implementation with:
    - `add_task(task)`
    - `add_dependency(task_id, depends_on_id)`
    - `validate_no_cycles()` using DFS
    - `topological_sort()` using deterministic Kahn-style ordering
  - Enforces no self-dependency and consistent ordering of ready tasks.

- `app/planning/planner.py`
  - Orchestrates end-to-end planning:
    1. Decompose
    2. Build DAG
    3. Validate DAG
    4. Return ordered plan

- `app/core/logger.py`
  - Reusable JSON structured logging.
  - Standard fields include `timestamp`, `module`, `action`, and `data`.

### How To Run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run tests:

```bash
python -m pytest tests/
```

### Example Usage

```python
from app.planning.planner import create_plan

plan = create_plan("Build REST API")

for task in plan.tasks:
    print(task.name, task.priority, task.dependencies)
```

### Dependencies

Defined in `requirements.txt`:
- `pydantic`
- `pytest`
