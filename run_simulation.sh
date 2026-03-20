#!/usr/bin/env bash

set -e

echo "=============================="
echo "STEP 0: Switching to main branch"
echo "=============================="
git checkout main
git pull origin main

echo "=============================="
echo "STEP 1: Checking clean repo state"
echo "=============================="
if [[ -n $(git status --porcelain) ]]; then
  echo "❌ Repo is not clean. Commit or stash changes."
  exit 1
fi
echo "✅ Repo clean"

echo "=============================="
echo "STEP 2: Setting up virtual environment"
echo "=============================="

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

pip install --upgrade pip > /dev/null
pip install -r requirements.txt > /dev/null

echo "✅ Environment ready"

echo "=============================="
echo "STEP 3: Running full test suite"
echo "=============================="

pytest -q

echo "=============================="
echo "STEP 4: Simulation Complete"
echo "=============================="
echo "✅ All tests passed"