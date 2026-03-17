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

## Agent 01 Execution Model

Agent execution follows a strict pipeline:
1. Receive goal string.
2. Decompose goal into atomic tasks using rule-based logic.
3. Build dependency DAG from decomposed tasks.
4. Validate DAG has no cycles.
5. Topologically sort tasks in deterministic order.
6. Return a `Plan` object containing ordered `Task` objects.

Public entrypoint for Agent 01 decomposition internals:
- `TaskDecomposer.decompose(goal: str) -> Plan` in `app/planning/task_decomposer.py`

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
- Planning flow remains deterministic and DAG-validated.
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
from app.planning.task_decomposer import TaskDecomposer

decomposer = TaskDecomposer()
plan = decomposer.decompose("Build REST API")

for task in plan.tasks:
    print(task.name, task.priority, task.dependencies)
```

### Dependencies

Defined in `requirements.txt`:
- `pydantic`
- `pytest`

---

## Agent 02 — Planning Engine

### What was built

- DAG-based planning engine that converts structured task lists into deterministic execution plans.
- Cycle detection with fast-fail on invalid dependency graphs.
- Deterministic topological sort using Kahn's algorithm with alphabetical ID tie-breaking.
- Execution grouping is level-based during topological traversal:
  - level 0: no dependencies
  - level 1: depends only on level 0
  - level N: depends only on prior levels
- Input validation: catches duplicate task IDs and missing dependency references before planning begins.

### Architecture decisions

- **No external graph libraries** — pure Python standard library only.
- **Deterministic topological sort** — Kahn's algorithm with alphabetical ID order as the tie-breaker ensures identical input always produces identical output.
- **Separation of responsibilities** — graph construction, validation, and orchestration are intentionally split across three modules.
- **Single public planning interface** — Agent 02 exposes only `build_execution_plan(tasks: list[dict])`.
- **String-based task IDs** — the planning engine operates on plain string IDs (from the decomposition engine's output contract) rather than internal UUIDs.

### File structure

```text
app/planning/
├── graph.py        # DependencyGraph: DAG construction, cycle detection, topological sort, execution groups
├── validator.py    # PlanValidator: duplicate ID and missing dependency checks
├── models.py       # TaskNode, ExecutionPlan, ExecutionGroup, PlanMetadata (Agent 02 schemas, appended)
└── planner.py      # build_execution_plan public API and orchestration internals

tests/
├── test_graph.py       # DependencyGraph unit tests
├── test_validator.py   # PlanValidator unit tests
└── test_planner.py     # build_execution_plan API tests
```

### How to run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run all tests:

```bash
python -m pytest tests/ -v
```

### Example usage

```python
from app.planning.planner import build_execution_plan

tasks = [
  {"id": "design", "description": "Design the schema", "dependencies": []},
  {"id": "implement", "description": "Implement the API", "dependencies": ["design"]},
  {"id": "test", "description": "Write and run tests", "dependencies": ["implement"]},
  {"id": "docs", "description": "Write documentation", "dependencies": ["implement"]},
]

plan = build_execution_plan(tasks)

print("Ordered tasks:")
for task in plan.ordered_tasks:
    print(f"  {task.id}: {task.description}")

print("\nExecution groups (parallelisable):")
for group in plan.execution_groups:
    print(f"  Group {group.group_id}: {group.task_ids}")

print(f"\nTotal tasks: {plan.metadata.total_tasks}")
```

Output:

```
Ordered tasks:
  design: Design the schema
  implement: Implement the API
  docs: Write documentation
  test: Write and run tests

Execution groups (parallelisable):
  Group 0: ['design']
  Group 1: ['implement']
  Group 2: ['docs', 'test']

Total tasks: 4
```

### Dependencies

- None beyond what Agent 01 already uses (standard library only for graph logic).

---

## Agent 03 — Execution Engine

### What was built

- Sequential execution engine that takes a validated `ExecutionPlan` from the Planning Engine and runs each task in topological order.
- Per-task lifecycle tracking: `pending → running → completed / failed / skipped`.
- Two failure modes: `stop_on_failure=True` (default) halts the run after the first failure and skips remaining tasks; `stop_on_failure=False` continues executing independent tasks.
- Dependency-aware skipping: if a dependency failed or was skipped, its dependent task is automatically skipped.
- Skipped tasks include explicit reason metadata via `skip_reason` (for example, failed dependency chain propagation).
- Structured execution report (`ExecutionReport`) containing per-task status, output, error, and timestamps.
- Step-level and summary JSON logging via a dedicated `ExecutionLogger`.

### Architecture decisions

- **Clean interface** — execution consumes `ExecutionPlan` from planning without modifying planning internals.
- **Stateless `Executor`** — handles a single task; testable in isolation with a custom `handler` callable.
- **`Runner` orchestrates** — converts `TaskNode` → `ExecutionTask`, iterates in plan order, delegates to `Executor`, accumulates results.
- **Pluggable handlers** — callers supply a `dict[task_id, callable]`; tasks without handlers default to a no-op (always succeed, empty output). Enables deterministic simulation and easy testing.
- **No hidden behaviour** — failure skipping and stop-on-failure logic are explicit in `runner.py`.

### Execution modes

- `stop_on_failure=True` (default): halt after first failed task, mark remaining as skipped.
- `stop_on_failure=False`: continue executing tasks in plan order; dependent tasks still skip if dependencies fail.

### Deterministic execution guarantee

- No randomness in execution logic.
- No parallel execution inside the runner.
- Same input `ExecutionPlan` always produces the same execution order and task-state transitions.

### Handler contract

Task handlers are expected to follow:

`Callable[[ExecutionTask], tuple[bool, str | None]]`

Returns:
- `success: bool`
- `message: str | None` (output when success is `True`, error message when `False`)

Backward compatibility:
- A handler may also return `str` directly, which is treated as successful output.

### ExecutionReport schema

`ExecutionReport` contains:
- `status`: overall execution status
- `total_tasks`: int
- `completed_tasks`: int
- `failed_tasks`: int
- `skipped_tasks`: int
- `tasks`: `list[ExecutionTask]`
- `started_at`: datetime
- `completed_at`: datetime

### File structure

```text
app/execution/
├── __init__.py    # Public API exports
├── models.py      # ExecutionStatus (Enum), ExecutionTask, ExecutionReport
├── executor.py    # Executor: single-task execution with handler protocol
├── runner.py      # Runner: plan orchestration, dep-skip, report building
└── logger.py      # ExecutionLogger: step-level + summary structured logging

tests/
└── test_execution_engine.py   # 30 tests across Executor, Runner, report + integration
```

### How to run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run all tests:

```bash
python -m pytest tests/ -v
```

### Example usage

```python
from app.planning.planner import build_execution_plan
from app.execution.runner import run_plan

tasks = [
  {"id": "init", "description": "Initialise environment", "dependencies": []},
  {"id": "build", "description": "Build the project", "dependencies": ["init"]},
  {"id": "test", "description": "Run test suite", "dependencies": ["build"]},
  {"id": "deploy", "description": "Deploy to staging", "dependencies": ["test"]},
]

plan   = build_execution_plan(tasks)
report = run_plan(plan)

print(f"Status:     {report.status}")
print(f"Completed:  {report.completed_tasks}/{report.total_tasks}")

for task in report.tasks:
    print(f"  {task.id}: {task.status} | output={task.output!r}")
```

Output:

```
Status:     completed
Completed:  4/4
  init:   completed | output=''
  build:  completed | output=''
  test:   completed | output=''
  deploy: completed | output=''
```

### Dependencies

- Standard library only (`datetime`, `enum`, `collections.abc`).
- Reuses `app.core.logger` and `app.planning.models` from existing layers.
