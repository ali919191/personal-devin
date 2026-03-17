# personal-devin
pernonal

## Agent 01 — Task Decomposition Engine

A production-grade system for converting natural language goals into structured execution plans with dependency management.

### What was built

Agent 01 is a task decomposition system that transforms high-level goals into actionable, ordered task lists. It:

- **Decomposes natural language goals** into atomic, executable tasks
- **Builds a Directed Acyclic Graph (DAG)** to represent task dependencies
- **Validates plans** for circular dependencies and consistency
- **Determines execution order** using topological sorting
- **Assigns priorities** to reflect task importance and sequencing
- **Provides structured metadata** for each task

### Architecture

The system is organized into four core modules:

#### Models (`models.py`)

- **Task**: Represents a single unit of work with UUID, name, description, dependencies, status, priority, and metadata
- **Plan**: Collections of ordered tasks with a shared goal and unique identifier
- Built with Pydantic for validation and serialization

#### Task Graph (`task_graph.py`)

- Implements a Directed Acyclic Graph (DAG) without external dependencies
- **add_task()**: Add tasks to the graph
- **add_dependency()**: Establish task relationships
- **validate_no_cycles()**: Detect circular dependencies using DFS
- **topological_sort()**: Kahn's algorithm for deterministic task ordering
- Ensures all dependencies are resolved before execution

#### Decomposer (`task_decomposer.py`)

- Rule-based goal decomposition using pattern matching
- Predefined patterns for common goals (API, database, frontend)
- Generic fallback for unrecognized goals
- Modular design supports future LLM-based decomposition
- Structured logging via JSON format

#### Planner (`planner.py`)

- Orchestrates the complete planning workflow:
	1. Decomposes goal into tasks
	2. Builds DAG representation
	3. Validates for cycles and consistency
	4. Returns ordered execution plan
- Public API for plan creation

#### Logger (`app/core/logger.py`)

- Structured JSON logging with consistent fields
- Timestamps, module names, action types, and custom data
- Reusable across the entire system

### How to run

Install dependencies:
```bash
pip install -r requirements.txt
```

Run tests:
```bash
python -m pytest tests/ -v
```

Run with coverage:
```bash
python -m pytest tests/ --cov=app --cov-report=html
```

### Example usage

```python
from app.planning.planner import create_plan

# Simple API
plan = create_plan("Build REST API")

# Access tasks in execution order
for task in plan.tasks:
		print(f"{task.priority}: {task.name}")
		print(f"  Dependencies: {task.dependencies}")
		print(f"  Description: {task.description}")

# Output:
# 100: Analyze requirements
# 90: Design solution
# 80: Implement solution
# 70: Test solution
# 60: Document solution
```

Advanced usage with planner:
```python
from app.planning.planner import Planner

planner = Planner()

# Create plan for complex goal
plan = planner.create_plan("Build microservices architecture")

print(f"Plan ID: {plan.id}")
print(f"Goal: {plan.goal}")
print(f"Total tasks: {len(plan.tasks)}")

# Iterate through tasks in execution order
for idx, task in enumerate(plan.tasks, 1):
		print(f"\nTask {idx}: {task.name}")
		print(f"  Status: {task.status}")
		print(f"  Priority: {task.priority}")
		print(f"  Depends on: {task.dependencies}")
```

### Dependencies

Core dependencies (in `requirements.txt`):

- **pytest**: Testing framework
- **pydantic**: Data validation and serialization

System design uses no external dependencies for the DAG implementation, ensuring minimal footprint and maximum reliability.

### Testing

Comprehensive test suite includes:

- **Models**: Task and Plan creation and validation
- **DAG**: Cycle detection, topological sorting, dependency management
- **Decomposition**: Pattern matching for common goals, generic fallback
- **Planning**: End-to-end workflow validation
- **Integration**: Full system behavior across multiple scenarios

All tests are deterministic and reproducible.
