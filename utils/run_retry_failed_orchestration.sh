#!/usr/bin/env bash
set -euo pipefail
REPO_DIR="/opt/NodeRAG-Neo4j-Integration"
cd "$REPO_DIR"

if [[ $# -ne 1 ]]; then
  echo "Usage: bash utils/run_retry_failed_orchestration.sh <run_ts>"
  exit 1
fi
RUN_TS="$1"

set -a
source "$REPO_DIR/.batch_secrets.env"
set +a

LOG_DIR="$REPO_DIR/POC_Data/logs/retry_assets/$RUN_TS"
mkdir -p "$LOG_DIR"
MASTER_LOG="$LOG_DIR/retry_orchestrator_$RUN_TS.log"
exec > >(tee -a "$MASTER_LOG") 2>&1

for i in 1 2 3 4 5 6; do
  MAP="$REPO_DIR/POC_Data/documents/mappings/user_resume_mapping.retry_failed.batch${i}.${RUN_TS}.csv"
  if [[ ! -f "$MAP" ]]; then
    echo "[WARN] missing retry batch file: $MAP"
    continue
  fi

  ROWS=$(python3 - "$MAP" <<'PY'
import csv,sys
rows=list(csv.DictReader(open(sys.argv[1],'r',encoding='utf-8',newline='')))
print(len(rows))
PY
)
  if [[ "$ROWS" == "0" ]]; then
    echo "[INFO] batch$i has 0 rows, skipping"
    continue
  fi

  KEY_VAR="GEMINI_API_KEY_${i}"
  CUR_KEY="${!KEY_VAR}"

  python3 - "$CUR_KEY" <<'PY'
from pathlib import Path
import sys, os
key=sys.argv[1]
env=Path('/opt/NodeRAG-Neo4j-Integration/.env')
lines=env.read_text(encoding='utf-8').splitlines() if env.exists() else []
kv={}
for ln in lines:
    if '=' in ln and not ln.strip().startswith('#'):
        k,v=ln.split('=',1); kv[k]=v
kv['GOOGLE_API_KEY']=key
kv['BACKEND_AUTH_TOKEN']=os.environ.get('BACKEND_AUTH_TOKEN','')
env.write_text('\n'.join(f"{k}={v}" for k,v in kv.items())+'\n', encoding='utf-8')
print('[INFO] .env updated for retry batch key/token (masked)')
PY

  docker compose up -d --force-recreate --no-deps api
  for t in {1..30}; do
    if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then break; fi
    sleep 2
  done

  REPORT="$LOG_DIR/retry_batch${i}_report_${RUN_TS}.json"
  . venv/bin/activate
  set -a; . ./.env; set +a
  python utils/batch_build_graphs.py --mapping-csv "$MAP" --continue-on-error --poll-interval 10 --build-timeout-min 30 --http-timeout 600 --report-json "$REPORT"
done

echo "[INFO] Retry orchestration finished for run_ts=$RUN_TS"
