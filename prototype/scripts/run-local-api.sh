#!/usr/bin/env bash
# AX ERP FastAPI를 현재 머신의 독립 가상환경에서 기동한다.
set -euo pipefail

project_dir="$(cd "$(dirname "$0")/.." && pwd)"
venv_dir="$project_dir/.venv-codex"

if [ ! -x "$venv_dir/bin/uvicorn" ]; then
  python3 -m venv "$venv_dir"
  "$venv_dir/bin/pip" install -r "$project_dir/requirements.txt"
fi

cd "$project_dir"
exec "$venv_dir/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000
