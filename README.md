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
- Skipped tasks include explicit reason metadata via `skip_reason` (for example, `dependency_failed:<task_id>`).
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

---

## Agent 04 — Memory System

### What was built

- Deterministic memory subsystem under `app/memory/` for storing execution intelligence.
- Typed memory records for executions, tasks, failures, and decisions.
- File-based append-only persistence in `data/memory/` with one JSON file per memory type.
- Repository abstraction for save/read/query operations.
- Service API for high-level logging and retrieval helpers (`get_recent`, `get_failures`, `get_patterns`).
- Schema-safe serialization with explicit datetime conversion and model validation.

### Architecture decisions

- **Typed records first** — all memory entries share a strict base contract (`id`, `timestamp`, `type`, `data`) via Pydantic models.
- **Deterministic file storage** — records are appended in insertion order; writes are atomic and JSON keys are sorted for stable output.
- **Layered design** — `memory_store` handles I/O, `repository` handles persistence queries, `service` handles business-level operations.
- **No external database** — JSON files are used to satisfy deterministic, local, and dependency-light constraints.
- **Structured observability** — every read/write path logs memory `type`, `id`, and `status` using the shared structured logger.

### How to run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run all tests:

```bash
python -m pytest tests/ -v
```

Validation result (test environment): `124 passed in 0.64s`

Manual memory file verification:

```bash
ls data/memory/
cat data/memory/executions.json
```

### Dependencies

- No additional third-party dependencies.
- Reuses existing project dependencies (`pydantic`, `pytest`) and `app.core.logger`.

---

## Agent 05 — Agent Loop

### What was built

A deterministic orchestration layer that connects the Planning Engine, Execution Engine, and Memory System into a single controlled runtime loop.

The Agent Loop executes the following sequence:

Plan → Execute → Validate → Reflect → Persist

It accepts a high-level goal, converts it into a minimal deterministic task structure, generates an execution plan, runs it, evaluates outcomes, logs structured memory, and returns a unified result.

---

### Architecture decisions

- No abstraction layers introduced
  - Directly uses:
    - build_execution_plan
    - run_plan
    - MemoryService

- Deterministic goal normalization
  - Raw goals are wrapped into a single explicit task
  - No AI-based parsing or decomposition

- Strict orchestration boundary
  - Planning, execution, and memory modules remain unchanged
  - Agent Loop only coordinates flow

- Explicit validation model
  - Execution outcomes classified as:
    - success
    - partial
    - failure

- Structured reflection model
  - Captures:
    - failed task IDs
    - success rate
    - deterministic notes

- Comprehensive memory logging
  - Execution summaries logged
  - Per-task results logged
  - Failures explicitly recorded
  - Reflection decisions persisted

---

### How to run

Example usage:

```python
from app.agent.agent_loop import AgentLoop

agent = AgentLoop()
result = agent.run("Sample goal")

print(result)
```

---

Run tests:

```bash
pytest tests/ -v
```

### Dependencies

Planning Engine (app/planning)

Execution Engine (app/execution)

Memory System (app/memory)

Agent schemas (app/agent/schemas.py)

---

## Agent 06 — Integrations Layer

### What was built

A deterministic integrations framework that enables the Personal Devin system to interact with external systems through controlled, testable abstractions.

Key components:

- **Integration base interface** enforcing a standard execution contract
- **Integration registry** for dynamic registration and retrieval
- **Filesystem integration** with safe, sandboxed file operations
- **Mock API integration** simulating external API behavior without network calls

All integrations follow a strict input/output contract and are designed to be fully deterministic.

---

### Architecture decisions

**1. Deterministic-only integrations**

- No real network calls allowed
- No randomness or time-based behavior
- Ensures reproducibility and testability

**2. Registry pattern**

- Centralized integration management
- Prevents tight coupling between execution and integrations
- Enables future plug-and-play integrations

**3. Strict execution contract**

All integrations follow:

```json
{
  "integration": "name",
  "action": "action_name",
  "payload": {}
}

Return:

{
  "status": "success | error",
  "data": {},
  "error": null
}

4. Sandboxed filesystem

All file operations restricted to a root directory

Path traversal protection enforced

Prevents unsafe file access

5. Isolation from core systems

No modification to planning, execution, memory, or agent loop

Integrations are additive only

How to run
1. Register integrations
from app.integrations.registry import IntegrationRegistry
from app.integrations.filesystem import FilesystemIntegration
from app.integrations.mock_api import MockAPIIntegration

registry = IntegrationRegistry()

registry.register(FilesystemIntegration(root_dir="./data"))
registry.register(MockAPIIntegration())
2. Execute an integration
integration = registry.get("filesystem")

result = integration.execute(
    action="write_file",
    payload={
        "path": "test.txt",
        "content": "hello world"
    }
)

print(result)
3. Example response
{
  "status": "success",
  "data": {
    "path": "test.txt"
  },
  "error": null
}
Validation

Run full test suite:

python -m pytest tests/ -v
Test coverage

The following behaviors are validated:

Integration registry:

Registration

Duplicate prevention

Retrieval errors

Filesystem integration:

File write

File read

Directory listing

Path traversal protection

Mock API integration:

Deterministic GET/POST responses

Response structure validation

Error handling:

Invalid actions

Invalid payloads

Missing integrations

Dependencies

No external dependencies.

Uses only:

Python standard library

Existing project logging system

Notes

This layer introduces external interaction capability but does NOT yet integrate with the execution engine.

Future agents will:

Connect integrations to execution engine

Enable tool usage within task execution


---

## **How to Validate (Strict Checklist)**

Run this sequence **after Copilot generates code**:

---

### 1. Imports must resolve
```bash
python -c "from app.integrations.registry import IntegrationRegistry"
2. Run full tests
python -m pytest tests/ -v

Hard requirement:

All tests pass

No skipped tests

3. Manual integration test (critical)

Open Python shell:

python

Run:

from app.integrations.registry import IntegrationRegistry
from app.integrations.filesystem import FilesystemIntegration

registry = IntegrationRegistry()
registry.register(FilesystemIntegration(root_dir="./tmp"))

fs = registry.get("filesystem")

# write
print(fs.execute("write_file", {"path": "a.txt", "content": "test"}))

# read
print(fs.execute("read_file", {"path": "a.txt"}))

# list
print(fs.execute("list_dir", {}))
4. Security validation (must fail)
print(fs.execute("read_file", {"path": "../outside.txt"}))

Expected:

status = "error"
5. Mock API validation
from app.integrations.mock_api import MockAPIIntegration

api = MockAPIIntegration()

print(api.execute("GET", {"endpoint": "/users"}))
print(api.execute("POST", {"endpoint": "/users", "data": {"id": 1}}))

Must return deterministic responses.

Failure Conditions (Reject PR if any)

Filesystem allows ../ traversal

Registry allows duplicate names

Any randomness or timestamps in output

Tests missing or incomplete

README not appended (not replaced)

Final Gate

Only merge if:

✅ Tests pass

✅ Manual validation passes

✅ README section exists exactly as above

✅ No core modules modified

---

## Agent 07 — Self-Improvement Engine

### What was built

- Deterministic self-improvement engine at `app/agent/self_improvement.py`.
- Structured pipeline: analyze run data, generate insights, and produce optimization suggestions.
- Memory-backed pattern awareness using existing memory interfaces only.
- Light AgentLoop hook that executes self-improvement after execution persistence.

### Architecture decisions

- Read-only analysis model: no code mutation and no automated patching.
- Deterministic outputs: no randomness, fixed confidence values, and sorted result ordering.
- Strict memory compatibility: uses existing `MemoryService` methods (`get_patterns`, `log_decision`).
- Minimal loop integration: self-improvement runs after normal loop behavior so Agent 05 contracts remain intact.

### How to run

Example usage:

```python
from app.agent.self_improvement import SelfImprovementEngine

engine = SelfImprovementEngine()

run_data = {
  "goal": "Ship feature",
  "status": "partial",
  "metrics": {"total": 3, "completed": 2, "failed": 1, "skipped": 0},
  "tasks": [
    {"id": "task-1", "status": "completed", "error": None, "skip_reason": None},
    {"id": "task-2", "status": "completed", "error": None, "skip_reason": None},
    {"id": "task-3", "status": "failed", "error": "boom", "skip_reason": None},
  ],
}

result = engine.process(run_data)
print(result)
```

Run tests:

```bash
python -m pytest tests/ -v
```

### Dependencies

- No additional third-party dependencies.
- Reuses existing project dependencies and shared logger/memory interfaces.

### Input contract

`run_data` must include:

- `goal: str`
- `status: str`
- `metrics`:
  - `total: int`
  - `completed: int`
  - `failed: int`
  - `skipped: int`
- `tasks: list[dict]` with:
  - `id: str`
  - `status: str`
  - `error: Optional[str]`
  - `skip_reason: Optional[str]`

### Failure classification

Failures are categorized deterministically as:

- `execution_error`: task has explicit error content.
- `dependency_failure`: error or skip reason begins with `dependency_failed:`.
- `unknown_failure`: fallback category when neither rule matches.

### Pattern detection strategy

- A pattern is defined as repeated signals in deterministic categories:
  - repeated failure types across runs (from memory patterns)
  - repeated task-level errors in a run
  - repeated inefficiency signals (for example, skipped tasks present)
- Matching is exact string comparison.
- Frequency threshold for repeated historical failure patterns is `>= 2`.

### Confidence model

Confidence is deterministic and rule-based:

  failure_pattern: 0.9
  warning: 0.7
  optimization: 0.6

Confidence does not vary dynamically and is not learned.

### Inefficiency detection

An inefficiency is defined as:

  presence of skipped tasks
  partial completion (completed < total)
  repeated task retries (if retry fields are present in input)

These signals generate warning or optimization insights.

### Suggestion generation rules

- Suggestions are derived only from generated insights.
- No external inference or model-generated side channels are used.
- Each suggestion maps to at least one insight and a defined target layer (`planning`, `execution`, `memory`, or `agent`).

### Output ordering

- Insights are sorted by:
  1. `type` (`failure_pattern` → `warning` → `optimization`)
  2. `message` (alphabetical)
- Suggestions are sorted by:
  1. `priority` (`high` → `medium` → `low`)
  2. `target` (alphabetical)

### Memory usage

- Reads:
  - historical patterns via `get_patterns()`
- Writes (temporary reuse of existing decision interface):
  - summary (`type = self_improvement_summary`)
  - patterns (`type = self_improvement_pattern`)
  - insights (`type = self_improvement_insight`)
- Insight payload structure:

```json
{
  "type": "self_improvement_insight",
  "insights": [...],
  "suggestions": [...]
}
```

### AgentLoop integration

- `SelfImprovementEngine.process()` is called only after:
  - execution completes
  - loop persistence is finished
- Integration is read-only and must not alter execution results.
- Exceptions from self-improvement are caught and logged; no unhandled exception is allowed to break the loop result contract.
