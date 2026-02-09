#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -n "${PYTHON_BIN:-}" ]]; then
  :
elif command -v python3.12 >/dev/null 2>&1; then
  PYTHON_BIN="python3.12"
else
  PYTHON_BIN="python3"
fi
VENV_DIR="${VENV_DIR:-.tdd_venv}"
LOG_DIR="${LOG_DIR:-temp/tdd}"
PYTEST_TARGET="${PYTEST_TARGET:-tests/test_worker_pipeline.py}"
RUNS="${RUNS:-20}"

if [[ ! -d "$VENV_DIR" ]]; then
  echo "[tdd] creating venv: $VENV_DIR"
  "$PYTHON_BIN" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install -U pip setuptools wheel >/dev/null
  "$VENV_DIR/bin/python" -m pip install -r requirements-dev.txt >/dev/null
fi

mkdir -p "$LOG_DIR"
RUN_ID="$("$VENV_DIR/bin/python" - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
PY
)"

LOG_FILE="$LOG_DIR/tdd_${RUNS}_${RUN_ID}.log"
JSONL_FILE="$LOG_DIR/tdd_${RUNS}_${RUN_ID}.jsonl"

echo "[tdd] run_id=$RUN_ID runs=$RUNS target=$PYTEST_TARGET" | tee -a "$LOG_FILE"
echo "[tdd] log=$LOG_FILE" | tee -a "$LOG_FILE"
echo "[tdd] jsonl=$JSONL_FILE" | tee -a "$LOG_FILE"

failures=0

for i in $(seq 1 "$RUNS"); do
  start_ts="$("$VENV_DIR/bin/python" - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).isoformat().replace("+00:00","Z"))
PY
)"
  echo "[tdd] iter=$i start=$start_ts" | tee -a "$LOG_FILE"

  set +e
  "$VENV_DIR/bin/python" -m pytest -q "$PYTEST_TARGET" >>"$LOG_FILE" 2>&1
  code=$?
  set -e

  end_ts="$("$VENV_DIR/bin/python" - <<'PY'
from datetime import datetime, timezone
print(datetime.now(timezone.utc).isoformat().replace("+00:00","Z"))
PY
)"
  status="pass"
  if [[ "$code" -ne 0 ]]; then
    status="fail"
    failures=$((failures + 1))
  fi

  echo "[tdd] iter=$i status=$status exit_code=$code end=$end_ts" | tee -a "$LOG_FILE"
  "$VENV_DIR/bin/python" - <<PY >>"$JSONL_FILE"
import json
row = {
  "run_id": "$RUN_ID",
  "iter": $i,
  "status": "$status",
  "exit_code": $code,
  "started_at": "$start_ts",
  "ended_at": "$end_ts",
  "target": "$PYTEST_TARGET",
}
print(json.dumps(row, ensure_ascii=True))
PY
done

echo "[tdd] done failures=$failures" | tee -a "$LOG_FILE"

if [[ "$failures" -ne 0 ]]; then
  exit 1
fi
