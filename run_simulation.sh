#!/bin/bash

set -e  # stop on error

echo "=============================="
echo "STEP 0: Switching to main branch"
echo "=============================="

git checkout main || true
git pull origin main || true

echo "=============================="
echo "STEP 1: Checking clean repo state"
echo "=============================="

if [[ -n $(git status --porcelain) ]]; then
  echo "❌ Repo is not clean. Commit or stash changes first."
  exit 1
fi

echo "✅ Repo clean"

echo "=============================="
echo "STEP 2: Running full test suite"
echo "=============================="

pytest -q

echo "✅ All tests passed"

echo "=============================="
echo "STEP 3: Creating simulation script"
echo "=============================="

mkdir -p scripts/simulations

cat << 'EOF' > scripts/simulations/run_improvement_simulation.py
from app.agent.loop_controller import build_default_loop_controller
from app.memory.memory_store import MemoryStore


def run_simulation(cycles: int = 30):
    memory = MemoryStore()
    controller = build_default_loop_controller(self_improvement_enabled=True)

    results = []

    for i in range(cycles):
        controller.run("test_task")

        record = memory.get_latest("improvement_record")

        if record:
            results.append({
                "cycle": i,
                "impact_score": record.impact_score,
                "accepted": record.accepted,
                "rollback": getattr(record, "rollback_executed", False),
                "version": record.version,
            })
        else:
            results.append({
                "cycle": i,
                "impact_score": None,
                "accepted": None,
                "rollback": None,
                "version": None,
            })

    return results


if __name__ == "__main__":
    results = run_simulation(30)

    print("\n===== SIMULATION RESULTS =====\n")

    for r in results:
        print(
            f"Cycle {r['cycle']:02d} | "
            f"impact={r['impact_score']} | "
            f"accepted={r['accepted']} | "
            f"rollback={r['rollback']} | "
            f"version={r['version']}"
        )
EOF

echo "✅ Simulation script created"

echo "=============================="
echo "STEP 4: Running simulation"
echo "=============================="

python scripts/simulations/run_improvement_simulation.py

echo "=============================="
echo "DONE"
echo "=============================="