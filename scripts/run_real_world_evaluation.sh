#!/usr/bin/env bash

set -e

echo "========================================"
echo "REAL WORLD EVALUATION RUN"
echo "========================================"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs/evaluation"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

mkdir -p "$LOG_DIR"

RUN_FILE="$LOG_DIR/run_$TIMESTAMP.log"

echo "Log file: $RUN_FILE"

echo "========================================"
echo "STEP 1: Enforce clean main branch"
echo "========================================"

git checkout main > /dev/null
git pull origin main > /dev/null

if [[ -n $(git status --porcelain) ]]; then
  echo "ERROR: Repo not clean"
  exit 1
fi

echo "OK: Repo clean"

echo "========================================"
echo "STEP 2: Activate environment"
echo "========================================"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

pip install -r requirements.txt > /dev/null

echo "OK: Environment ready"

echo "========================================"
echo "STEP 3: Running evaluation scenarios"
echo "========================================"

python <<EOF | tee -a "$RUN_FILE"

from datetime import datetime, UTC
from app.agent.agent_loop import AgentLoop

def fixed_now():
    return datetime.now(UTC)

loop = AgentLoop(now_fn=fixed_now)

scenarios = [
    "Improve system performance",
    "Fix failing tests and ensure stability",
    "Refactor execution engine safely",
    "Handle a task that may partially fail and recover",
    "Optimize memory usage across components",
    "Execute a long chain of dependent operations",
]

print("========================================")
print("EVALUATION START")
print("========================================")

for i, goal in enumerate(scenarios, 1):
    print(f"\n--- Scenario {i} ---")
    print(f"GOAL: {goal}")

    try:
        result = loop.run(goal)

        print("PLAN STEPS:")
        if result.plan:
            for step in result.plan.steps:
                print("-", step.description)

        print("EXECUTION STATUS:", getattr(result.execution, "status", None))

        print("REFLECTION:")
        print(result.reflection)

    except Exception as e:
        print("ERROR:", str(e))

print("\n========================================")
print("EVALUATION COMPLETE")
print("========================================")

EOF

echo "========================================"
echo "STEP 4: Done"
echo "========================================"

echo "Results stored at:"
echo "$RUN_FILE"