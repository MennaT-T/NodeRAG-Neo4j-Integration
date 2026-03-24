#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/NodeRAG-Neo4j-Integration"
cd "$REPO_DIR"

MAP_IN="${1:-$REPO_DIR/POC_Data/documents/mappings/user_resume_mapping.vps.csv}"
MAP_OUT="$REPO_DIR/POC_Data/documents/mappings/user_resume_mapping.remaining.csv"
SUMMARY_OUT="$REPO_DIR/POC_Data/logs/graceful_stop_summary.json"

LATEST_PID_FILE="$(ls -1t $REPO_DIR/POC_Data/logs/batch_build_*.pid 2>/dev/null | head -n 1 || true)"
LATEST_LOG_FILE="$(ls -1t $REPO_DIR/POC_Data/logs/batch_build_*.log 2>/dev/null | head -n 1 || true)"

if [[ -z "$LATEST_PID_FILE" || -z "$LATEST_LOG_FILE" ]]; then
  echo "No active batch artifacts found in POC_Data/logs"
  exit 1
fi

PID="$(cat "$LATEST_PID_FILE")"
echo "Using PID file: $LATEST_PID_FILE"
echo "Using LOG file: $LATEST_LOG_FILE"
echo "Target PID: $PID"

if ps -p "$PID" >/dev/null 2>&1; then
  CURRENT_USER="$(grep -E '^\[[0-9]+/[0-9]+\] Processing user_id=' "$LATEST_LOG_FILE" | tail -n 1 | sed -E 's/.*user_id=([A-Za-z0-9_-]+).*/\1/' || true)"
  if [[ -n "$CURRENT_USER" ]]; then
    STATE_FILE="$REPO_DIR/POC_Data/documents/users/user_${CURRENT_USER}/info/state.json"
    echo "Waiting for current user to finish: $CURRENT_USER"
    for _ in $(seq 1 360); do
      if ! ps -p "$PID" >/dev/null 2>&1; then
        echo "Batch process already exited while waiting"
        break
      fi
      if [[ -f "$STATE_FILE" ]]; then
        DONE="$(python3 - "$STATE_FILE" <<'PY'
import json, sys
p=sys.argv[1]
try:
    d=json.load(open(p,'r',encoding='utf-8'))
    st=d.get('Current_state','')
    err=d.get('Error_type','')
    if st=='FINISHED' or (err and err!='NO_ERROR'):
        print('yes')
    else:
        print('no')
except Exception:
    print('no')
PY
)"
        if [[ "$DONE" == "yes" ]]; then
          echo "Current user completed/errored, proceeding to stop"
          break
        fi
      fi
      sleep 5
    done
  fi

  if ps -p "$PID" >/dev/null 2>&1; then
    echo "Sending SIGTERM to batch PID $PID"
    kill -TERM "$PID" || true
    for _ in $(seq 1 24); do
      if ! ps -p "$PID" >/dev/null 2>&1; then
        break
      fi
      sleep 2
    done
  fi

  if ps -p "$PID" >/dev/null 2>&1; then
    echo "PID still running, sending SIGKILL"
    kill -KILL "$PID" || true
  fi
else
  echo "PID is not running; generating remaining mapping only"
fi

python3 - "$MAP_IN" "$MAP_OUT" "$SUMMARY_OUT" <<'PY'
import csv, json, sys
from pathlib import Path

map_in = Path(sys.argv[1])
map_out = Path(sys.argv[2])
summary_out = Path(sys.argv[3])
users_root = Path('/opt/NodeRAG-Neo4j-Integration/POC_Data/documents/users')

if not map_in.exists():
    raise SystemExit(f"Mapping not found: {map_in}")

finished = set()
if users_root.exists():
    for p in users_root.glob('user_*/info/state.json'):
        try:
            d = json.loads(p.read_text(encoding='utf-8'))
            if d.get('Current_state') == 'FINISHED' and d.get('Error_type') == 'NO_ERROR':
                finished.add(p.parts[-3].replace('user_','',1))
        except Exception:
            pass

rows = []
with map_in.open('r', encoding='utf-8-sig', newline='') as f:
    r = csv.DictReader(f)
    fields = r.fieldnames or ['user_id','resume_path','document_type','filename']
    for row in r:
        uid = (row.get('user_id') or '').strip()
        if uid and uid not in finished:
            rows.append(row)

map_out.parent.mkdir(parents=True, exist_ok=True)
with map_out.open('w', encoding='utf-8', newline='') as f:
    w = csv.DictWriter(f, fieldnames=['user_id','resume_path','document_type','filename'])
    w.writeheader()
    for row in rows:
        w.writerow({
            'user_id': row.get('user_id',''),
            'resume_path': row.get('resume_path',''),
            'document_type': row.get('document_type','resume') or 'resume',
            'filename': row.get('filename','')
        })

summary = {
    'source_mapping': str(map_in),
    'remaining_mapping': str(map_out),
    'finished_count': len(finished),
    'remaining_count': len(rows),
    'finished_users_sample': sorted(list(finished))[:20],
}
summary_out.parent.mkdir(parents=True, exist_ok=True)
summary_out.write_text(json.dumps(summary, indent=2), encoding='utf-8')
print(json.dumps(summary, indent=2))
PY

echo "Next run command:"
echo "cd /opt/NodeRAG-Neo4j-Integration && . venv/bin/activate && set -a && . ./.env && set +a && python utils/batch_build_graphs.py --mapping-csv /opt/NodeRAG-Neo4j-Integration/POC_Data/documents/mappings/user_resume_mapping.remaining.csv --continue-on-error --poll-interval 10 --build-timeout-min 30 --http-timeout 600"
