"""Comprehensive tests for the task decomposition system."""

import pytest
from uuid import UUID

from app.planning.models import Plan, Task
from app.planning.task_decomposer import TaskDecomposer
from app.planning.task_graph import TaskGraph
from app.planning.planner import Planner


class TestModels:
    """Test data models."""

    def test_task_creation(self) -> None:
        """Test creating a task."""
        task = Task(name="Test Task", description="Test Description", priority=50)
        assert task.name == "Test Task"
        assert task.description == "Test Description"
        assert task.priority == 50
        assert task.status == "pending"
        assert isinstance(task.id, UUID)

    def test_task_with_dependencies(self) -> None:
        """Test task with dependencies."""
        task_id_1 = str(UUID(int=1))
        task_id_2 = str(UUID(int=2))
        task = Task(
            name="Dependent Task",
            description="Task with dependencies",
            dependencies=[task_id_1, task_id_2],
        )
        assert len(task.dependencies) == 2
        assert task_id_1 in task.dependencies

    def test_plan_creation(self) -> None:
        """Test creating a plan."""
        plan = Plan(goal="Build a REST API")
        assert plan.goal == "Build a REST API"
        assert isinstance(plan.id, UUID)
        assert len(plan.tasks) == 0

    def test_plan_add_tasks(self) -> None:
        """Test adding tasks to a plan."""
        plan = Plan(goal="Build a REST API")
        task1 = Task(name="Task 1", description="First task")
        task2 = Task(name="Task 2", description="Second task")
        plan.tasks.append(task1)
        plan.tasks.append(task2)
        assert len(plan.tasks) == 2

    def test_plan_get_task_by_id(self) -> None:
        """Test retrieving task by ID."""
        task = Task(name="Target Task", description="Find me")
        plan = Plan(goal="Test Plan", tasks=[task])
        retrieved = plan.get_task_by_id(str(task.id))
        assert retrieved is not None
        assert retrieved.name == "Target Task"


class TestTaskGraph:
    """Test DAG implementation."""

    def test_graph_creation(self) -> None:
        """Test creating a task graph."""
        graph = TaskGraph()
        assert len(graph.tasks) == 0
        assert len(graph.adjacency) == 0

    def test_add_task(self) -> None:
        """Test adding tasks to graph."""
        graph = TaskGraph()
        task1 = Task(name="Task 1", description="First")
        task2 = Task(name="Task 2", description="Second")

        graph.add_task(task1)
        graph.add_task(task2)

        assert len(graph.tasks) == 2
        assert str(task1.id) in graph.tasks

    def test_add_dependency(self) -> None:
        """Test adding dependencies."""
        graph = TaskGraph()
        task1 = Task(name="Task 1", description="First")
        task2 = Task(name="Task 2", description="Second")

        graph.add_task(task1)
        graph.add_task(task2)

        graph.add_dependency(str(task2.id), str(task1.id))

        assert str(task2.id) in graph.adjacency[str(task1.id)]
        assert str(task1.id) in graph.tasks[str(task2.id)].dependencies

    def test_add_dependency_invalid_task(self) -> None:
        """Test adding dependency with invalid task."""
        graph = TaskGraph()
        task1 = Task(name="Task 1", description="First")
        graph.add_task(task1)

        with pytest.raises(ValueError):
            graph.add_dependency("invalid_id", str(task1.id))

    def test_topological_sort_linear(self) -> None:
        """Test topological sort with linear dependencies."""
        graph = TaskGraph()
        task1 = Task(name="Task 1", description="First")
        task2 = Task(name="Task 2", description="Second")
        task3 = Task(name="Task 3", description="Third")

        graph.add_task(task1)
        graph.add_task(task2)
        graph.add_task(task3)

        graph.add_dependency(str(task2.id), str(task1.id))
        graph.add_dependency(str(task3.id), str(task2.id))

        sorted_ids = graph.topological_sort()

        assert len(sorted_ids) == 3
        assert sorted_ids.index(str(task1.id)) < sorted_ids.index(str(task2.id))
        assert sorted_ids.index(str(task2.id)) < sorted_ids.index(str(task3.id))

    def test_topological_sort_diamond(self) -> None:
        """Test topological sort with diamond dependency."""
        graph = TaskGraph()
        task1 = Task(name="Task 1", description="Top")
        task2 = Task(name="Task 2", description="Left")
        task3 = Task(name="Task 3", description="Right")
        task4 = Task(name="Task 4", description="Bottom")

        graph.add_task(task1)
        graph.add_task(task2)
        graph.add_task(task3)
        graph.add_task(task4)

        graph.add_dependency(str(task2.id), str(task1.id))
        graph.add_dependency(str(task3.id), str(task1.id))
        graph.add_dependency(str(task4.id), str(task2.id))
        graph.add_dependency(str(task4.id), str(task3.id))

        sorted_ids = graph.topological_sort()

        assert len(sorted_ids) == 4
        assert sorted_ids.index(str(task1.id)) < sorted_ids.index(str(task2.id))
        assert sorted_ids.index(str(task1.id)) < sorted_ids.index(str(task3.id))
        assert sorted_ids.index(str(task2.id)) < sorted_ids.index(str(task4.id))
        assert sorted_ids.index(str(task3.id)) < sorted_ids.index(str(task4.id))

    def test_cycle_detection_simple(self) -> None:
        """Test cycle detection with simple cycle."""
        graph = TaskGraph()
        task1 = Task(name="Task 1", description="First")
        task2 = Task(name="Task 2", description="Second")

        graph.add_task(task1)
        graph.add_task(task2)

        graph.add_dependency(str(task2.id), str(task1.id))
        graph.add_dependency(str(task1.id), str(task2.id))

        assert not graph.validate_no_cycles()

    def test_cycle_detection_self_loop(self) -> None:
        """Test cycle detection with self-loop."""
        graph = TaskGraph()
        task1 = Task(name="Task 1", description="First")

        graph.add_task(task1)

        graph.add_dependency(str(task1.id), str(task1.id))

        assert not graph.validate_no_cycles()

    def test_cycle_detection_complex(self) -> None:
        """Test cycle detection with complex cycle."""
        graph = TaskGraph()
        task1 = Task(name="Task 1", description="First")
        task2 = Task(name="Task 2", description="Second")
        task3 = Task(name="Task 3", description="Third")

        graph.add_task(task1)
        graph.add_task(task2)
        graph.add_task(task3)

        graph.add_dependency(str(task2.id), str(task1.id))
        graph.add_dependency(str(task3.id), str(task2.id))
        graph.add_dependency(str(task1.id), str(task3.id))

        assert not graph.validate_no_cycles()

    def test_get_execution_order(self) -> None:
        """Test getting task execution order."""
        graph = TaskGraph()
        task1 = Task(name="Task 1", description="First", priority=100)
        task2 = Task(name="Task 2", description="Second", priority=90)
        task3 = Task(name="Task 3", description="Third", priority=80)

        graph.add_task(task1)
        graph.add_task(task2)
        graph.add_task(task3)

        graph.add_dependency(str(task2.id), str(task1.id))
        graph.add_dependency(str(task3.id), str(task2.id))

        execution_order = graph.get_execution_order()

        assert len(execution_order) == 3
        assert execution_order[0].name == "Task 1"
        assert execution_order[1].name == "Task 2"
        assert execution_order[2].name == "Task 3"


class TestTaskDecomposer:
    """Test task decomposition."""

    def test_decomposer_creation(self) -> None:
        """Test creating a decomposer."""
        decomposer = TaskDecomposer()
        assert decomposer is not None
        assert len(decomposer.GOAL_PATTERNS) > 0

    def test_decompose_api_goal(self) -> None:
        """Test decomposing an API goal."""
        decomposer = TaskDecomposer()
        plan = decomposer.decompose("Build REST API")

        assert plan.goal == "Build REST API"
        assert len(plan.tasks) > 0
        assert plan.tasks[0].name == "Design API specification"

    def test_decompose_database_goal(self) -> None:
        """Test decomposing a database goal."""
        decomposer = TaskDecomposer()
        plan = decomposer.decompose("Set up PostgreSQL database")

        assert len(plan.tasks) > 0
        assert any("database" in task.name.lower() for task in plan.tasks)

    def test_decompose_frontend_goal(self) -> None:
        """Test decomposing a frontend goal."""
        decomposer = TaskDecomposer()
        plan = decomposer.decompose("Build React frontend")

        assert len(plan.tasks) > 0
        assert any("component" in task.name.lower() or "ui" in task.description.lower() for task in plan.tasks)

    def test_decompose_generic_goal(self) -> None:
        """Test decomposing a generic goal."""
        decomposer = TaskDecomposer()
        plan = decomposer.decompose("Create a random feature")

        assert plan.goal == "Create a random feature"
        assert len(plan.tasks) == 5  # Generic plan has 5 stages

    def test_decomposed_plan_has_dependencies(self) -> None:
        """Test that decomposed plan has proper dependencies."""
        decomposer = TaskDecomposer()
        plan = decomposer.decompose("Build REST API")

        has_dependencies = any(len(task.dependencies) > 0 for task in plan.tasks)
        assert has_dependencies


class TestPlanner:
    """Test the main planner."""

    def test_planner_creation(self) -> None:
        """Test creating a planner."""
        planner = Planner()
        assert planner is not None
        assert planner.decomposer is not None

    def test_create_plan_simple(self) -> None:
        """Test creating a simple plan."""
        planner = Planner()
        plan = planner.create_plan("Build REST API")

        assert isinstance(plan, Plan)
        assert plan.goal == "Build REST API"
        assert len(plan.tasks) > 0

    def test_create_plan_validates_no_cycles(self) -> None:
        """Test that planner creates valid plans with no cycles."""
        planner = Planner()
        plan = planner.create_plan("Build database")

        # Verify no cycles by checking topological sort succeeds
        graph = TaskGraph()
        for task in plan.tasks:
            graph.add_task(task)
        for task in plan.tasks:
            for dep_id in task.dependencies:
                graph.add_dependency(str(task.id), dep_id)

        sorted_ids = graph.topological_sort()
        assert len(sorted_ids) == len(plan.tasks)

    def test_create_plan_execution_order(self) -> None:
        """Test that plan tasks are in execution order."""
        planner = Planner()
        plan = planner.create_plan("Build REST API")

        # Verify dependencies are satisfied in order
        for idx, task in enumerate(plan.tasks):
            for dep_id in task.dependencies:
                dep_task_idx = next(
                    (i for i, t in enumerate(plan.tasks) if str(t.id) == dep_id),
                    None
                )
                assert dep_task_idx is not None
                assert dep_task_idx < idx  # Dependency must come before

    def test_create_plan_tasks_have_priorities(self) -> None:
        """Test that all tasks have priority."""
        planner = Planner()
        plan = planner.create_plan("Build frontend")

        for task in plan.tasks:
            assert 0 <= task.priority <= 100

    def test_plan_consistency_multiple_calls(self) -> None:
        """Test that the same goal produces consistent plans."""
        planner = Planner()
        plan1 = planner.create_plan("Build API server")
        plan2 = planner.create_plan("Build API server")

        assert len(plan1.tasks) == len(plan2.tasks)
        assert plan1.tasks[0].name == plan2.tasks[0].name


class TestIntegration:
    """Integration tests for the complete system."""

    def test_full_planning_workflow(self) -> None:
        """Test complete workflow from goal to execution plan."""
        planner = Planner()
        plan = planner.create_plan("Build REST API with database")

        assert plan.goal == "Build REST API with database"
        assert len(plan.tasks) > 0

        for task in plan.tasks:
            assert task.id is not None
            assert task.name
            assert task.description
            assert task.priority >= 0
            assert isinstance(task.dependencies, list)
            assert task.status == "pending"

    def test_plan_execution_order_respected(self) -> None:
        """Test that execution order respects all dependencies."""
        planner = Planner()
        plan = planner.create_plan("Build a web application")

        executed: set[str] = set()
        for task in plan.tasks:
            for dep_id in task.dependencies:
                assert dep_id in executed, f"Dependency {dep_id} not in executed set"
            executed.add(str(task.id))

    def test_complex_goal_decomposition(self) -> None:
        """Test decomposition of complex goals."""
        goals = [
            "Build REST API",
            "Create database",
            "Build React UI",
            "Write email service",
            "Implement caching layer",
        ]

        planner = Planner()
        for goal in goals:
            plan = planner.create_plan(goal)
            assert len(plan.tasks) > 0
            assert all(task.priority >= 0 for task in plan.tasks)
