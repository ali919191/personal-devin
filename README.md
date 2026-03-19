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
- Explicit orchestration control: full-system runs are governed by a validated state machine and deterministic recovery policy.

## System Architecture

Personal Devin is layered as a deterministic control stack:

- Planning produces a validated execution plan from task dictionaries.
- Execution runs the ordered plan and returns a typed execution report.
- Memory persists execution, task, failure, and decision records.
- Self-improvement analyzes memory history and emits approved adaptations.
- Orchestration & Control coordinates the full lifecycle through explicit states, recovery rules, and trace logging.

Current control-layer files:
- `app/core/logger.py`
- `app/core/state.py`
- `app/core/recovery.py`
- `app/core/orchestrator.py`

## System Execution Flow

System execution now follows a strict orchestrated pipeline:
1. Initialize run context and trace ID.
2. Transition to `PLANNING` and build the execution plan.
3. Transition to `EXECUTING` and run the plan through the execution engine.
4. Transition to `VALIDATING` and verify execution report consistency.
5. Transition to `REFLECTING` and persist deterministic memory records.
6. Transition to `IMPROVING` and run the self-improvement loop from memory.
7. Transition to `COMPLETED` or `FAILED` through the state machine.

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
│   │   ├── logger.py
│   │   ├── orchestrator.py
│   │   ├── recovery.py
│   │   └── state.py
│   └── planning/
│       ├── models.py
│       ├── planner.py
│       ├── task_decomposer.py
│       └── task_graph.py
├── tests/
│   ├── core/
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

## Agent 28 — Deployment Context Injection

### What was built
- Deployment context injection layer
- Immutable deployment context object
- Strict separation between resolution and execution

### Architecture decisions
- Introduced context boundary to prevent mutation
- Enforced deterministic execution inputs
- Removed direct config access from execution layer

### How to run
- Context is built before execution
- Passed explicitly into ExecutionRunner
- Context can be serialized to stable JSON and replayed exactly
- Context fingerprint is the deterministic debugging and replay anchor
- Serialization uses canonical JSON with sorted keys and compact separators for byte-stable hashing
- Execution start and failure logs include the context fingerprint for replay correlation

### Dependencies
- environment_resolver
- execution runner

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

## Agent 17 — Agent Loop Optimization

### What was built
- Deterministic loop execution
- Structured logging
- Retry system with failure classification

### Architecture decisions
- Separation of loop state, logging, retry logic
- Determinism enforced at iteration level

### How to run
- pytest tests/test_agent_loop.py

### Dependencies
- Standard library only

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

## Agent 29 — Execution Isolation / Sandboxing

### What was built
- ExecutionSandbox for safe callable execution
- Builtin restriction layer
- Import control via custom __import__
- Full routing of execution through sandbox

### Architecture decisions
- Callable-based sandbox (no exec/eval)
- In-process isolation via builtins patching guarded by a re-entrant lock
- Deterministic and stateless execution model
- No handler global rewriting; sandboxing stays at the execution boundary only

### How to run
pytest tests/execution/test_sandbox.py

### Dependencies
- None

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
from app.integrations.registry import ToolRegistry
from app.integrations.filesystem import FilesystemTool
from app.integrations.mock_api import MockAPITool

registry = ToolRegistry()

registry.register(FilesystemTool(root_dir="./data"))
registry.register(MockAPITool())
2. Execute an integration
integration = registry.get("filesystem")

result = integration.execute(
  input={
    "action": "write_file",
        "path": "test.txt",
        "content": "hello world"
  },
  context={}
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
python -c "from app.integrations.registry import ToolRegistry"
2. Run full tests
python -m pytest tests/ -v

Hard requirement:

All tests pass

No skipped tests

3. Manual integration test (critical)

Open Python shell:

python

Run:

from app.integrations.registry import ToolRegistry
from app.integrations.filesystem import FilesystemTool

registry = ToolRegistry()
registry.register(FilesystemTool(root_dir="./tmp"))

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
from app.integrations.mock_api import MockAPITool

api = MockAPITool()

print(api.execute("GET", {"endpoint": "/users"}))

---

## Agent 18 — Memory Feedback Loop

### What was built

- Added a unified execution feedback model: `ExecutionRecord`.
- Extended existing memory storage/service layers to persist and retrieve normalized execution outcomes.
- Added a lightweight `FeedbackEngine` in memory that reuses the existing analysis `PatternDetector`.
- Integrated feedback context into agent planning so historical failures and successful strategies influence task planning deterministically.
- Kept the existing memory APIs intact (`log_execution`, `log_task`, `log_failure`, `log_decision`) for backward compatibility.

### How memory now integrates with planning

1. Before planning, the agent loop calls `MemoryService.get_feedback_context(task_id)`.
2. `MemoryService` loads recent execution history via existing repository/store layers.
3. `FeedbackEngine.build_context(...)` detects repeated failures and success strategies using `PatternDetector`.
4. Planner entrypoint `plan(task, context=None)` deterministically injects context-derived metadata into the task.
5. After execution, `MemoryService.record_execution(...)` persists unified execution outcomes.

### Deterministic guarantees

- No randomness introduced in context generation, sorting, or task adjustment.
- Context outputs are generated from deterministic counters and stable sorting.
- Planner behavior remains unchanged when `context` is `None`.
- Existing planning and memory contracts remain backward compatible.

### How to run tests

Run all tests:

```bash
python -m pytest tests/ -v
```

Run Agent 18 specific tests:

```bash
python -m pytest tests/memory/test_feedback_engine.py tests/memory/test_memory_feedback_integration.py -v
```
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
- Agent 07.5 execution quality analyzer signals for successful and partial runs:
  - structural metrics (depth, width, branching factor, dependency chains)
  - execution metrics (parallelism potential vs actual, completion efficiency, skip propagation depth)
  - deterministic derived signals for structure and efficiency quality.

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
  - `actual_parallelism: int` (optional; defaults to sequential execution)
- `tasks: list[dict]` with:
  - `id: str`
  - `status: str`
  - `error: Optional[str]`
  - `skip_reason: Optional[str]`
  - `dependencies: list[str]` (optional)

### Structural and execution metrics

- Structural metrics:
  - `depth`
  - `width`
  - `branching_factor`
  - `dependency_chains`
- Execution metrics:
  - `parallelism_potential`
  - `actual_parallelism`
  - `parallelism_utilization`
  - `completion_efficiency`
  - `skip_propagation_depth`

### Efficiency classification rules

Completion efficiency is categorized deterministically:

- high: completed / total >= 0.9
- medium: 0.5 <= completed / total < 0.9
- low: completed / total < 0.5

### Parallelism metrics

- Parallelism potential:
  Maximum number of tasks that can run concurrently based on dependency graph levels.

- Actual parallelism:
  Number of tasks executed concurrently (provided by execution layer or default = 1).

- Parallelism utilization:
  actual_parallelism / parallelism_potential

### Derived signals

- Example deterministic derived signals:
  - `Graph depth = 5 (linear chain)`
  - `No parallel execution opportunities utilized`
  - `Wide graph executed sequentially`
  - `Execution efficiency: high but non-parallel`
  - `High dependency chain depth increases fragility`

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
  structure_signal: 0.8
  efficiency_signal: 0.75
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
  1. `type` (`failure_pattern` → `structure_signal` → `efficiency_signal` → `warning` → `optimization`)
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

### Memory semantics

Memory is append-only and non-idempotent by design.

Repeated executions of the same input may produce duplicate self-improvement entries.

Pattern detection logic must account for this by evaluating signal frequency carefully rather than relying on raw entry counts.

### AgentLoop integration

- `SelfImprovementEngine.process()` is called only after:
  - execution completes
  - loop persistence is finished
- Integration is read-only and must not alter execution results.
- Exceptions from self-improvement are caught and logged; no unhandled exception is allowed to break the loop result contract.

## Agent 08 — Self-Improvement Engine

### What was built

A deterministic improvement engine that converts reflection signals into predefined system actions.

This agent does NOT generate intelligence.

It strictly consumes signals from Agent 07 and maps them to controlled, auditable system responses.

### Architecture decisions

- No signal generation allowed
- No signal transformation allowed
- No metric interpretation
- No aggregation or normalization
- No heuristics or scoring logic
- Static registry-based mapping only
- Deterministic execution only

### How to run

```bash
pytest tests/test_improvement_engine.py
```

### Dependencies

Relies on:

- Agent 07 signal contract

## Agent 09 — Orchestration Engine

### What was built

- Central orchestration layer coordinating all system components
- End-to-end pipeline: PLAN → EXECUTE → STORE → REFLECT → IMPROVE

### Architecture decisions

- Deterministic pipeline execution
- Explicit dependency wiring via registry
- No hidden state
- Canonical run trace ledger in `RunContext.trace` using typed `TraceEntry`

### Execution semantics

- Planning failure → pipeline aborts immediately (no execution, memory, or improvement)
- Execution failure → captured as failure result, pipeline continues to:
  - memory storage
  - reflection (Agent Loop)
  - improvement

### Determinism guarantees

- No randomness (no uuid/random usage)
- Stable execution ordering
- Deterministic trace generation
- Same input → same output (including trace)

### Run trace

Each run produces a deterministic trace stored in `RunContext.trace`.

Each entry includes:
- stage: one of [planning, execution, memory_store, reflection, improvement]
- status: start | completed | error
- step: deterministic sequence counter
- metadata: stage-specific data (including error details when applicable)

This enables:
- replayability
- debugging
- deterministic comparisons
- input for self-improvement

### Observability

All stages emit structured logs with:
- stage
- status
- run_id
- metadata

Logs are machine-readable and aligned with trace entries.

### How to run

Example usage:

```python
from app.orchestration import Orchestrator, OrchestrationRequest

orchestrator = Orchestrator()
result = orchestrator.run(
  OrchestrationRequest(
    run_id="run-001",
    goal="Ship feature",
  )
)

print(result.status)
```

Dependencies

Planning, Execution, Memory, Agent Loop, Improvement Engine

## Agent 10 — Integration Control Layer

### What was built

- Tool abstraction layer (Tool interface)
- Controlled execution wrapper for all integrations
- Structured ToolResult contract
- Trace-integrated external execution
- Tool registry enforcing controlled access

### Architecture decisions

- All integrations must implement Tool
- No raw side effects allowed
- Registry is single source of truth
- Execution must be observable (trace)

### How to run

pytest tests/test_integrations_control.py

### Dependencies

None

## Agent 11 — Observability & Analysis Engine

### What was built

- New analysis module at app/analysis with a deterministic, read-only analysis pipeline.
- Structured report models:
  - AnalysisReport
  - ExecutionTraceSummary
  - FailurePattern
  - Recommendation
- Analyzer orchestration layer that consumes execution logs and memory records and emits AnalysisReport.
- Pattern detector for recurring failures, inefficiencies, and retry loops.
- Recommendation engine that maps patterns to prioritized, actionable suggestions.
- Pluggable analysis registry for detector and recommendation component registration.

### Architecture decisions

- Read-only behavior guarantee:
  - No modifications to execution, agent, or planning runtime behavior.
  - Analyzer only reads supplied logs and memory records.
- Deterministic output:
  - Stable sorting for patterns and recommendations.
  - Rule-based confidence scoring.
  - No randomness or time-based branching in analysis logic.
- Pluggable composition:
  - Registry supports custom detector/recommendation functions.
  - Default registry wires built-in detector and recommendation engine.
- Structured observability:
  - analysis_run_start and analysis_run_end structured logs emitted with execution_id and summary metrics.

### How to run

Run focused analysis tests:

```bash
pytest tests/test_analysis_engine.py -q
```

Run full suite:

```bash
pytest -q
```

### Dependencies

- No new third-party dependencies.
- Reuses existing project modules:
  - app/core/logger
  - app/memory models/contracts

## Agent 12 — Adaptive Execution Layer

### What was built

- New policy-driven adaptation module at `app/adaptation`.
- Core adaptation model: `Adaptation` (`id`, `source`, `type`, `payload`, `confidence`).
- Adaptation policies with strict validation and explicit application:
  - `RetryLimitPolicy`
  - `TimeoutPolicy`
  - `PreferredToolPolicy`
- Pluggable adaptation registry for mapping adaptation types to policies.
- `AdaptationEngine` with deterministic lifecycle:
  - `generate(improvement_output) -> list[Adaptation]`
  - `filter_valid(adaptations) -> list[Adaptation]`
  - `apply(adaptations, execution_context) -> dict`
- Deterministic execution modifiers output for downstream execution context.

### Architecture decisions

- Strict no-mutation behavior:
  - Adaptation engine returns modifiers only.
  - It does not execute tasks and does not change execution/planning internals.
- Policy gate is mandatory:
  - Every adaptation type must have a registered policy.
  - Validation and application are fully explicit and auditable.
- Deterministic adaptation mapping:
  - Static action-to-adaptation mapping.
  - Stable adaptation IDs from input order.
- Structured observability:
  - `adaptation_generated`
  - `adaptation_generation_skipped`
  - `adaptation_validation`
  - `adaptation_applied`
  - `adaptation_rejected`

### How to run

Run adaptation tests:

```bash
pytest tests/test_adaptation_engine.py -q
```

Run full suite:

```bash
pytest -q
```

### Dependencies

- No new third-party dependencies.
- Reuses project logger and dataclass-based contracts.

## Agent 13 — Conflict Resolution Engine

### What was built

- Deterministic conflict resolution layer between planning and execution.
- New policy model and defaults in `app/planning/policy.py`.
- New resolver in `app/planning/conflict_resolver.py`:
  - `ConflictResolver.resolve(adaptations) -> list[Adaptation]`
- Extended planning models with `Adaptation` contract fields:
  - `id`, `target`, `action`, `confidence`, `policy`, `priority`, `created_at`
- Full planning-scoped tests in `tests/planning/test_conflict_resolver.py`.

### Architecture decisions

- Strict resolution ordering:
  1. Policy precedence
  2. Confidence filtering
  3. Confidence tie-break
  4. Deterministic fallback ordering
- Policy-first gate:
  - Adaptations with unknown policy are dropped.
  - Policy confidence thresholds are enforced before selection.
- Deterministic fallback ordering key:
  - `(-policy_priority, -confidence, created_at, id)`
- Structured observability:
  - Each resolve call logs a `conflict_resolution` event with counts, selected IDs, dropped IDs, and reasoning.

### How to run

- `pytest tests/planning/test_conflict_resolver.py`
- `pytest -q`

### Dependencies

- None (pure internal logic)

## Agent 14 — Self-Improvement System

### What was built

- Deterministic self-improvement subsystem under `app/self_improvement/`.
- Evaluation pipeline that extracts execution quality signals from memory history.
- Optimization generator that proposes typed improvement actions from evaluated patterns.
- Policy gate that filters low-confidence or conflicting actions before approval.
- Agent loop integration that runs self-improvement only after execution and persistence complete.

### Architecture

- `app/self_improvement/models.py`
  - Dataclass contracts for `EvaluationResult`, `ImprovementAction`, and `OptimizationReport`.
- `app/self_improvement/evaluator.py`
  - Computes stable metrics and pattern summaries from memory records.
- `app/self_improvement/optimizer.py`
  - Maps evaluation findings into deterministic improvement proposals.
- `app/self_improvement/policy.py`
  - Applies confidence thresholds and deterministic de-duplication by target.
- `app/self_improvement/engine.py`
  - Orchestrates evaluate -> optimize -> policy approval and logs structured events.
- `app/agent/agent_loop.py`
  - Invokes self-improvement after persistence and logs approved improvement counts.

### How to run

Run self-improvement tests:

```bash
pytest tests/test_self_improvement.py -q
```

Run full suite:

```bash
pytest -q
```

### Dependencies

- `pydantic` — required by planning, memory, and execution layers (added in prior agent builds, not new to Agent 14).
- No new third-party packages introduced by this module.

## Agent 15 — Self-Improvement Loop

### What was built

- Full self-improvement feedback loop under `app/self_improvement/`.
- `Analyzer` that loads execution and failure records from any duck-typed memory store.
- `PatternDetector` that identifies recurring failure signals, high-latency operations, and low-success-rate tasks using deterministic thresholds.
- `AdaptationEngine` that translates detected patterns into typed `SelfImprovementAdaptation` candidates.
- `AdaptationPolicy` that validates, confidence-gates, and deduplicates adaptation candidates before approval.
- `SelfImprovementLoop` orchestrator (and `run_self_improvement_loop()` functional entry point) that wires the full pipeline end-to-end.
- 48 new deterministic unit tests across `tests/self_improvement/`.

### Architecture

- `app/self_improvement/models.py` *(extended)*
  - Agent 15 models: `ExecutionRecord`, `FailureRecord`, `Pattern`, `SelfImprovementAdaptation`, `AdaptationResult`.
  - `ExecutionRecord` exposes a computed `success_rate` property (successes / total_runs).
- `app/self_improvement/analyzer.py`
  - `Analyzer` class with `load_executions()` and `load_failures()`.
  - Handles both `MemoryRecord` objects and plain `dict` entries via duck-typed helpers.
  - Normalises timestamps to UTC-aware datetimes.
- `app/self_improvement/pattern_detector.py`
  - `PatternDetector` with three deterministic detection rules:
    - `_repeated_failures` — groups failure records by `error_type`; emits a pattern per type that appears >= FAILURE_REPEAT_THRESHOLD (2) times.
    - `_high_latency` — emits a pattern for every execution record whose `avg_latency > HIGH_LATENCY_THRESHOLD` (3.0 s).
    - `_low_success_rate` — emits a pattern for every execution record whose `success_rate < LOW_SUCCESS_RATE_THRESHOLD` (0.7).
  - Output is deterministically sorted by `(kind, signal_value, pattern_id)`.
- `app/self_improvement/adaptation_engine.py`
  - `AdaptationEngine.generate(patterns)` maps each pattern kind to one or more `SelfImprovementAdaptation` candidates.
  - Per-kind rules:
    - `repeated_failure` => `retry_with_backoff` (confidence x 0.95) + `escalate_on_failure` (confidence x 0.85).
    - `high_latency` => `optimize_execution_path` (confidence x 0.9).
    - `low_success_rate` => `adjust_strategy` (confidence x 0.9) + `lower_confidence_threshold` (confidence x 0.8).
  - Output is deterministically sorted by `(-confidence_score, adaptation_id)`.
- `app/self_improvement/policy.py` *(extended)*
  - `AdaptationPolicy` with configurable `confidence_threshold` (default 0.6) and `forbidden_targets` list.
  - `validate(adaptations)` returns `(approved, rejected)` tuple; deduplicates by `(action_type, target)` key.
- `app/self_improvement/loop.py`
  - `SelfImprovementLoop(analyzer, detector, engine, policy)` orchestrates the full pipeline.
  - `run()` method: load records => detect patterns => generate adaptations => validate => return `AdaptationResult`.
  - `run_self_improvement_loop(memory_store, policy)` functional entry point for external callers.
- `app/self_improvement/logger.py` *(extended)*
  - 7 new structured-log event constants: `LOOP_STARTED`, `ANALYSIS_COMPLETED`, `PATTERNS_DETECTED`, `ADAPTATIONS_GENERATED`, `POLICY_VALIDATED`, `ADAPTATIONS_APPROVED`, `LOOP_COMPLETED`.
- `app/self_improvement/__init__.py` *(extended)*
  - All Agent 15 symbols exported from the package.

### How to run

Run Agent 15 self-improvement loop tests:

```bash
pytest tests/self_improvement/ -q
```

Run full suite:

```bash
pytest -q
```

### Dependencies

- None (pure internal logic using Python standard library only: `dataclasses`, `enum`, `datetime`, `collections`, `uuid`).

## Agent 16 — Orchestration & Control Layer

### What was built

- Deterministic `OrchestrationController` in `app/core/orchestrator.py` as the new full-system entry point.
- Explicit state machine in `app/core/state.py` with validated transitions across `INITIALIZED`, `PLANNING`, `EXECUTING`, `VALIDATING`, `REFLECTING`, `IMPROVING`, `COMPLETED`, and `FAILED`.
- Deterministic failure recovery manager in `app/core/recovery.py` with explicit failure categories and bounded retry policy.
- Phase-level trace logging with one trace ID per run and duration metrics for each orchestration stage.
- End-to-end tests covering state transitions, retry behavior, validation failures, and full orchestration flow under `tests/core/`.

### Architecture decisions

- Public-interface-only orchestration:
  - planning via `app.planning.build_execution_plan`
  - execution via `app.execution.run_plan`
  - memory via `app.memory.MemoryService`
  - self-improvement via `app.self_improvement.run_self_improvement_loop`
- Canonical orchestrator ownership moved to `app/core/orchestrator.py` and exposed as `app.core.Orchestrator`.
- `app/orchestration/orchestrator.py` is retained only as a deprecated compatibility layer.
- State transitions are explicit and validated rather than inferred from stage names or partial side effects.
- Recovery is phase-scoped and deterministic:
  - transient failures may retry within `RetryPolicy`
  - deterministic failures do not retry
  - policy violations do not retry
- Validation is separated from execution so report integrity failures are surfaced before reflection and improvement proceed.
- Reflection persists execution/task/failure memory and records a deterministic reflection snapshot before self-improvement runs.

### New constraints introduced

- No phase may skip the state machine.
- No retries for deterministic failures or policy violations.
- No direct internal access to planning, execution, memory, or self-improvement internals from the controller.
- Terminal states are final; no transitions are allowed out of `COMPLETED` or `FAILED`.
- Reproducibility depends on explicit inputs, ordered transitions, and bounded retry policy only.

### Deprecation Notice

Legacy orchestration module will be removed in Agent 18.
All imports must migrate to `app.core.Orchestrator`.

### How to run

Run Agent 16 tests:

```bash
pytest tests/core/ -q
```

Run full validation:

```bash
pytest -q
flake8 .
```

### Dependencies

- `flake8` (added for deterministic linting and required pre-push validation).
- No runtime dependencies beyond the repository's existing Python stack.

---

## Agent 19 — Evaluation Engine

### What was built

- Deterministic evaluation system for execution outputs.
- `Evaluator` — pure function evaluation with three deterministic tiers: exact match (1.0), partial string match (0.5), and failure (0.0).
- `EvaluationService` — orchestration layer that calls the evaluator and persists structured results into the memory system via `MemoryService.log_decision`.
- Structured logging at every stage: `evaluation_started`, `evaluation_completed`, `evaluation_service_started`, `evaluation_service_completed`.

### Architecture decisions

- **Pure evaluator** — `Evaluator.evaluate` is a side-effect-free, deterministic function: no randomness, no timestamps, no I/O.
- **Service layer for orchestration** — `EvaluationService` owns the evaluate-then-store lifecycle and accepts memory injection for testability.
- **Memory integration via `log_decision`** — reuses the existing `MemoryService` interface without modifying memory internals.
- **Frozen dataclasses** — `EvaluationInput` and `EvaluationResult` are immutable by design.

### How to run

```bash
pytest tests/evaluation -v
```

### Dependencies

- None external. All dependencies are part of the existing repository stack.

---

## Agent 20 — Feedback Loop Engine

### What was built

- Feedback system connecting execution and evaluation to adaptation.
- New deterministic feedback package:
  - `app/feedback/models.py` with `FeedbackSignal` and `FeedbackBatch`
  - `app/feedback/engine.py` with deterministic feedback generation and batching
- Agent loop integration that generates feedback after evaluation, then routes
  structured feedback into adaptation inputs through memory decisions/failures.

### Architecture decisions

- Deterministic mapping from evaluation output to feedback signal.
- Structured signals for downstream learning:
  - execution ID
  - normalized score
  - success/failure classification
  - stable improvement suggestions
  - deterministic confidence and timestamp via injected clock
- Feedback routing is explicit in the agent loop (no hidden side channels):
  - `feedback_signal` decision record
  - failure record when a classified failure exists

### How to run

```bash
pytest tests/feedback
```

### Dependencies

- Evaluation engine outputs (`app.evaluation.models.EvaluationResult`)
- Execution records (`app.execution.models.ExecutionReport`)

---

## Agent 21 — Integrations Layer

### What was built

- A production-grade integrations framework under `app/integrations/` with typed request/response models, controlled exceptions, a provider registry, and an execution manager.
- Three built-in providers under `app/integrations/providers/`:
  - `shell.py` for explicit local command execution with captured stdout/stderr and timeout controls.
  - `http.py` for deterministic HTTP requests with explicit transport settings and no implicit retries.
  - `mock.py` for repeatable offline/test executions with stable outputs for identical requests.
- A full test suite under `tests/integrations/` covering registry behavior, manager orchestration, provider behavior, failure paths, and deterministic mock output validation.

### Architecture decisions

- Deterministic contract first:
  - every provider accepts `IntegrationRequest` and returns `IntegrationResponse`
  - no hidden retries and no implicit randomness
  - provider-specific inputs live only in `payload` and `metadata`
- Clean provider abstraction:
  - all integrations implement `BaseIntegration`
  - `IntegrationRegistry` resolves providers by name with no hardcoded dispatch
- Observability:
  - `IntegrationManager` emits structured lifecycle logs for request, resolution, response, and errors
- Failure safety:
  - missing providers raise `IntegrationNotFoundError`
  - provider failures raise `IntegrationExecutionError`
  - no silent failure paths are allowed
- Future execution-engine compatibility:
  - the manager and providers are isolated from planning, memory, and agent-loop internals
  - future execution components can call the manager using the typed request/response contract

### How to run

Example usage:

```python
from datetime import UTC, datetime

from app.integrations.manager import IntegrationManager
from app.integrations.models import IntegrationRequest
from app.integrations.providers.mock import MockIntegration
from app.integrations.registry import IntegrationRegistry

registry = IntegrationRegistry()
registry.register(MockIntegration())

manager = IntegrationManager(registry)

request = IntegrationRequest(
    id="demo-1",
    integration="mock",
    payload={"operation": "status"},
    metadata={"source": "readme"},
    timestamp=datetime.now(UTC),
)

response = manager.execute(request)
print(response.model_dump())
```

Run the test suite:

```bash
pytest -q
```

### Dependencies

- No new third-party dependencies were added.
- Uses the Python standard library for shell and HTTP execution.
- Reuses the existing project dependencies listed in `requirements.txt`, including Pydantic for typed models.

## Agent 22 — Environment & Context Engine

### What was built
- Universal environment context system
- Provider-agnostic schema
- Deterministic validation layer

### Architecture decisions
- Capability-based modeling instead of vendor coupling
- Adapter pattern for future extensibility
- Strict validation (fail-fast)

### How to run
- Define environment config
- Load via context service
- Run planning/execution with context injected

### Dependencies
- Pydantic (for validation)

## Agent 24 — Deployment Orchestrator

### What was built
- Added a strict deployment input contract in [app/core/deployment_context.py](app/core/deployment_context.py) using an immutable dataclass (`frozen=True`) with deterministic normalization.
- Added typed deployment planning models in [app/deployment/models.py](app/deployment/models.py): `DeploymentStep` and `DeploymentPlan`.
- Added a pure deployment planner in [app/deployment/orchestrator.py](app/deployment/orchestrator.py) that converts execution-derived context into explicit simulation steps.
- Added deployment package exports in [app/deployment/__init__.py](app/deployment/__init__.py).
- Added unit tests in [tests/deployment/test_orchestrator.py](tests/deployment/test_orchestrator.py).

### Architecture decisions
- Deterministic-first design:
  - Services are normalized and sorted in `DeploymentContext`.
  - Nested dictionaries/lists are canonicalized for stable ordering.
  - Step IDs and indexes are deterministic (`step-001`, `step-002`, ...).
- Strict structure enforcement:
  - `DeploymentOrchestrator.generate_plan(...)` only accepts `DeploymentContext`.
  - Raw dictionaries are rejected with explicit `TypeError`.
- Simulation-only behavior:
  - No provider SDK usage.
  - No external API/network calls.
  - No real deployment side effects.
- Structured observability:
  - Logs input context, generated plan, and step count using project structured logger.

### How to run
Run deployment tests only:

```bash
pytest tests/deployment/test_orchestrator.py -q
```

Run full suite:

```bash
pytest
```

### Dependencies
- No new third-party dependencies added.
- Reuses existing project dependencies and shared logging utilities.

## Agent 25 — Infrastructure Abstraction Layer

### What was built
- Added a provider abstraction contract at `app/infrastructure/base.py` via `InfrastructureProvider` with typed `deploy`, `destroy`, and `status` methods.
- Added deterministic provider resolution at `app/infrastructure/factory.py` with `get_provider(env: str)`.
- Added pluggable infrastructure providers in `app/infrastructure/providers/`:
  - `local.py`: local execution simulation, no external dependencies.
  - `aks.py`: AKS behavior simulation stub only (no Azure SDK usage).
  - `mock.py`: fully static deterministic responses for unit tests.
- Refactored execution integration in `app/execution/runner.py` to resolve infrastructure providers through the factory and call `provider.deploy(context)` when an infrastructure context is supplied.
- Added infrastructure tests in `tests/infrastructure/test_factory.py` and `tests/infrastructure/test_providers.py`.

### Architecture decisions
- Provider pattern with an abstract contract keeps execution layer environment-agnostic.
- Deterministic factory map avoids dynamic imports and runtime side effects.
- Provider outputs are typed and deterministic (`InfrastructureResult`), enabling predictable tests.
- Environment-specific selection is centralized in the factory; no environment branching in execution.

### How to run
- Run full test suite:
  - `python -m pytest`
- Run only infrastructure tests:
  - `python -m pytest tests/infrastructure/test_factory.py tests/infrastructure/test_providers.py`

### Dependencies
- No new external infrastructure SDK dependencies added.
- Uses existing project dependencies from `requirements.txt` (`pytest`, `pydantic`).

## Agent 26 — Deployment Orchestrator

### What was built
Deployment orchestration layer that translates execution outputs into structured deployment actions.

New files added:
- `app/deployment/models.py` — extended with `DeploymentRequest` and `DeploymentResult` frozen dataclasses.
- `app/deployment/providers/base.py` — abstract `DeploymentProvider` interface.
- `app/deployment/providers/local_provider.py` — `LocalDeploymentProvider` (in-process simulation, no external side effects).
- `app/deployment/orchestrator.py` — extended `DeploymentOrchestrator` with `run(request)` method and optional provider injection.
- `tests/deployment/test_orchestrator.py` — provider-based orchestrator test suite.

### Architecture decisions
- Provider pattern with an abstract contract keeps the orchestrator environment-agnostic.
- Dry-run first design: `DeploymentRequest.dry_run` defaults to `True`; steps are returned immediately without touching any provider.
- Deterministic execution: same `DeploymentRequest` input always produces the same `DeploymentResult` output.
- Backward compatible: existing `generate_plan()` / `DeploymentContext` path is unchanged; `provider` is an optional constructor argument defaulting to `LocalDeploymentProvider`.
- Provider exceptions are caught and surfaced as `DeploymentResult(success=False, errors=[...])` — the orchestrator never propagates provider failures to callers.

### How to run
```
pytest tests/deployment
```

### Dependencies
None — reuses existing project dependencies (`pytest`, standard-library `abc`, `dataclasses`).

## Agent 30 — Execution Policy & Audit Layer

### What was built
- Declarative execution policy model for deterministic request governance.
- Deterministic policy validator with explicit failure codes.
- Structured execution audit record model.
- Append-only JSONL audit logger with deterministic default path.
- Execution hook wrapper that enforces: `validate -> execute -> record`.

### Architecture decisions
- Wrapped execution externally instead of modifying the execution engine.
- Kept policy representation declarative and immutable (`dataclass(frozen=True)`).
- Used explicit exception types (`PolicyValidationError`) to make behavior testable.
- Used file-based append-only audit logging (`logs/execution_audit.jsonl`) with no mutation of prior lines.
- Injected clock and record ID factory into hooks to make deterministic tests straightforward.

### How execution governance works
1. `execute_with_policy(...)` snapshots request data.
2. `PolicyValidator.validate_or_raise(...)` enforces policy constraints.
3. Existing execution engine callable runs unchanged.
4. `AuditLogger.write_record(...)` appends a structured `ExecutionRecord`.
5. Hook returns output on success or re-raises error after logging failure.

### File structure
```text
app/execution/
├── policy/
│   ├── execution_policy.py
│   └── policy_validator.py
├── audit/
│   ├── audit_models.py
│   └── audit_logger.py
└── hooks/
  └── execution_hooks.py

tests/execution/
├── test_execution_policy.py
├── test_audit_logger.py
└── test_execution_hooks.py
```

### How to run tests
Run full test suite:

```bash
pytest -q
```
