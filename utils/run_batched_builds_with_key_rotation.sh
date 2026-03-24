#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/opt/NodeRAG-Neo4j-Integration"
cd "$REPO_DIR"

LOG_DIR="$REPO_DIR/POC_Data/logs"
mkdir -p "$LOG_DIR"
RUN_TS="$(date +%Y%m%d_%H%M%S)"
MASTER_LOG="$LOG_DIR/batch_orchestrator_${RUN_TS}.log"
SUMMARY_JSON="$LOG_DIR/batch_orchestrator_summary_${RUN_TS}.json"

exec > >(tee -a "$MASTER_LOG") 2>&1

echo "[INFO] run_ts=$RUN_TS"

set -a
source "$REPO_DIR/.batch_secrets.env"
set +a

# Ensure BACKEND_AUTH_TOKEN persisted in .env (without printing token)
python3 - <<'PY'
from pathlib import Path
env = Path('/opt/NodeRAG-Neo4j-Integration/.env')
lines = env.read_text(encoding='utf-8').splitlines() if env.exists() else []
kv = {}
for ln in lines:
    if '=' in ln and not ln.strip().startswith('#'):
        k,v=ln.split('=',1); kv[k]=v
import os
kv['BACKEND_AUTH_TOKEN']=os.environ['BACKEND_AUTH_TOKEN']
out='\n'.join([f"{k}={v}" for k,v in kv.items()])+"\n"
env.write_text(out, encoding='utf-8')
print('[INFO] .env updated for BACKEND_AUTH_TOKEN (masked)')
PY

# batch files and keys
BATCH_FILES=(
"$REPO_DIR/POC_Data/documents/mappings/user_resume_mapping.batch1.csv"
"$REPO_DIR/POC_Data/documents/mappings/user_resume_mapping.batch2.csv"
"$REPO_DIR/POC_Data/documents/mappings/user_resume_mapping.batch3.csv"
"$REPO_DIR/POC_Data/documents/mappings/user_resume_mapping.batch4.csv"
"$REPO_DIR/POC_Data/documents/mappings/user_resume_mapping.batch5.csv"
"$REPO_DIR/POC_Data/documents/mappings/user_resume_mapping.batch6.csv"
)
KEYS=(
"$GEMINI_API_KEY_1" "$GEMINI_API_KEY_2" "$GEMINI_API_KEY_3" "$GEMINI_API_KEY_4" "$GEMINI_API_KEY_5" "$GEMINI_API_KEY_6"
)

python3 - <<'PY'
import csv,glob
from pathlib import Path
files=sorted(glob.glob('/opt/NodeRAG-Neo4j-Integration/POC_Data/documents/mappings/user_resume_mapping.batch*.csv'))
allf=[]
for f in files:
    rows=list(csv.DictReader(open(f,'r',encoding='utf-8-sig',newline='')))
    print(f"[VERIFY] {Path(f).name} rows={len(rows)}")
    allf.extend([r['filename'] for r in rows])
print(f"[VERIFY] total_rows={len(allf)} unique={len(set(allf))}")
if len(allf)!=73 or len(set(allf))!=73:
    raise SystemExit('Batch integrity check failed before execution')
PY

# helper: update .env with current GOOGLE key and token
set_current_env() {
  local key="$1"
  python3 - "$key" <<'PY'
from pathlib import Path
import os,sys
key=sys.argv[1]
env=Path('/opt/NodeRAG-Neo4j-Integration/.env')
lines=env.read_text(encoding='utf-8').splitlines() if env.exists() else []
kv={}
for ln in lines:
    if '=' in ln and not ln.strip().startswith('#'):
        k,v=ln.split('=',1); kv[k]=v
kv['GOOGLE_API_KEY']=key
kv['BACKEND_AUTH_TOKEN']=os.environ['BACKEND_AUTH_TOKEN']
env.write_text('\n'.join(f"{k}={v}" for k,v in kv.items())+'\n', encoding='utf-8')
print('[INFO] Updated .env with current batch key (masked) and BACKEND_AUTH_TOKEN')
PY
}

# helper: verify backend auth endpoint with pilot user id
verify_qa_auth() {
  local user_id="$1"
  local code
  code=$(curl -s -o "$LOG_DIR/qa_auth_${RUN_TS}.json" -w "%{http_code}" -H "Authorization: Bearer $BACKEND_AUTH_TOKEN" "https://gp-backend-2.onrender.com/api/questions/user/${user_id}" || true)
  echo "[VERIFY] QA auth HTTP=$code for user_id=$user_id"
  if [[ "$code" != "200" ]]; then
    echo "[WARN] QA auth returned HTTP $code"
    return 1
  fi
  python3 - <<'PY'
import json
from pathlib import Path
p=Path('/opt/NodeRAG-Neo4j-Integration/POC_Data/logs/qa_auth_' + __import__('os').environ.get('RUN_TS','') + '.json')
if not p.exists():
    print('[WARN] QA auth body file missing')
else:
    txt=p.read_text(encoding='utf-8', errors='ignore').strip()
    try:
        payload=json.loads(txt)
        if isinstance(payload,list):
            print(f"[VERIFY] QA payload list_len={len(payload)}")
        elif isinstance(payload,dict):
            vals=payload.get('value') or payload.get('data') or payload.get('items') or payload.get('results') or []
            print(f"[VERIFY] QA payload envelope_len={len(vals) if isinstance(vals,list) else 0}")
        else:
            print('[WARN] QA payload unexpected type')
    except Exception:
        print('[WARN] QA payload not json')
PY
  return 0
}

export RUN_TS

# run batches
python3 - <<'PY'
import json
from pathlib import Path
Path('/opt/NodeRAG-Neo4j-Integration/POC_Data/logs').mkdir(parents=True,exist_ok=True)
PY

for i in {1..6}; do
  batch_idx=$((i-1))
  batch_file="${BATCH_FILES[$batch_idx]}"
  key="${KEYS[$batch_idx]}"
  echo "[INFO] ===== Batch $i start ====="
  echo "[INFO] mapping=$batch_file"

  # set env + recreate api
  set_current_env "$key"
  docker compose up -d --force-recreate --no-deps api

  # health check
  for t in {1..30}; do
    if curl -fsS http://localhost:8000/health >/tmp/health_batch.json 2>/dev/null; then break; fi
    sleep 2
  done
  echo "[VERIFY] API health: $(cat /tmp/health_batch.json | tr -d '\n' | cut -c1-220)"

  # pick pilot user from first row
  pilot_user="$(python3 - "$batch_file" <<'PY'
import csv,sys
rows=list(csv.DictReader(open(sys.argv[1],'r',encoding='utf-8-sig',newline='')))
print(rows[0]['user_id'])
PY
)"

  verify_qa_auth "$pilot_user" || true

  # pilot csv (exactly one user)
  pilot_csv="$LOG_DIR/batch${i}_pilot_${RUN_TS}.csv"
  python3 - "$batch_file" "$pilot_csv" <<'PY'
import csv,sys
rows=list(csv.DictReader(open(sys.argv[1],'r',encoding='utf-8-sig',newline='')))
with open(sys.argv[2],'w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['user_id','resume_path','document_type','filename'])
    w.writeheader(); w.writerow(rows[0])
PY

  pilot_report="$LOG_DIR/batch${i}_pilot_report_${RUN_TS}.json"
  set +e
  . venv/bin/activate
  set -a; . ./.env; set +a
  python utils/batch_build_graphs.py --mapping-csv "$pilot_csv" --continue-on-error --poll-interval 10 --build-timeout-min 30 --http-timeout 600 --report-json "$pilot_report"
  pilot_rc=$?
  set -e
  if [[ $pilot_rc -ne 0 ]]; then
    echo "[ERROR] Pilot failed for batch $i, collecting diagnostics"
    docker logs noderag-api --tail 200 > "$LOG_DIR/batch${i}_pilot_api_errors_${RUN_TS}.log" 2>&1 || true
    # retry pilot once after api recreate
    docker compose up -d --force-recreate --no-deps api
    for t in {1..30}; do
      if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then break; fi
      sleep 2
    done
    set +e
    . venv/bin/activate
    set -a; . ./.env; set +a
    python utils/batch_build_graphs.py --mapping-csv "$pilot_csv" --continue-on-error --poll-interval 10 --build-timeout-min 30 --http-timeout 600 --report-json "$pilot_report"
    pilot_rc=$?
    set -e
    if [[ $pilot_rc -ne 0 ]]; then
      echo "[ERROR] Pilot retry failed for batch $i; stopping orchestrator"
      exit 20
    fi
  fi
  echo "[VERIFY] Pilot succeeded for batch $i"

  # full batch excluding pilot row to avoid reprocessing completed user
  full_csv="$LOG_DIR/batch${i}_full_${RUN_TS}.csv"
  python3 - "$batch_file" "$full_csv" <<'PY'
import csv,sys
rows=list(csv.DictReader(open(sys.argv[1],'r',encoding='utf-8-sig',newline='')))
with open(sys.argv[2],'w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['user_id','resume_path','document_type','filename'])
    w.writeheader(); w.writerows(rows[1:])
print(len(rows)-1)
PY

  batch_report="$LOG_DIR/batch${i}_report_${RUN_TS}.json"
  set +e
  . venv/bin/activate
  set -a; . ./.env; set +a
  python utils/batch_build_graphs.py --mapping-csv "$full_csv" --continue-on-error --poll-interval 10 --build-timeout-min 30 --http-timeout 600 --report-json "$batch_report"
  batch_rc=$?
  set -e

  # handle failed users only rerun
  python3 - "$batch_report" "$full_csv" "$LOG_DIR/batch${i}_failed_${RUN_TS}.csv" <<'PY'
import json,csv,sys
rep=json.load(open(sys.argv[1],'r',encoding='utf-8'))
failed=[r['user_id'] for r in rep.get('results',[]) if not r.get('success')]
rows=list(csv.DictReader(open(sys.argv[2],'r',encoding='utf-8',newline='')))
with open(sys.argv[3],'w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=['user_id','resume_path','document_type','filename'])
    w.writeheader()
    for r in rows:
      if r['user_id'] in failed:
        w.writerow(r)
print(len(failed))
PY

  failed_count=$(python3 - "$LOG_DIR/batch${i}_failed_${RUN_TS}.csv" <<'PY'
import csv,sys
rows=list(csv.DictReader(open(sys.argv[1],'r',encoding='utf-8',newline='')))
print(len(rows))
PY
)

  if [[ "$failed_count" != "0" ]]; then
    echo "[WARN] batch $i failed_count=$failed_count; collecting diagnostics and retrying failed only"
    docker logs noderag-api --tail 250 > "$LOG_DIR/batch${i}_api_errors_${RUN_TS}.log" 2>&1 || true
    failed_report="$LOG_DIR/batch${i}_failed_report_${RUN_TS}.json"
    set +e
    . venv/bin/activate
    set -a; . ./.env; set +a
    python utils/batch_build_graphs.py --mapping-csv "$LOG_DIR/batch${i}_failed_${RUN_TS}.csv" --continue-on-error --poll-interval 10 --build-timeout-min 30 --http-timeout 600 --report-json "$failed_report"
    set -e
  fi

  echo "[INFO] ===== Batch $i done ====="
done

# Build summary json
python3 - "$RUN_TS" "$SUMMARY_JSON" <<'PY'
import json,glob,sys
from pathlib import Path
run_ts=sys.argv[1]
out=Path(sys.argv[2])
logs=Path('/opt/NodeRAG-Neo4j-Integration/POC_Data/logs')
summary={'run_ts':run_ts,'batches':[]}
for i in range(1,7):
    item={'batch':i}
    for kind in ['pilot_report','report','failed_report']:
        p=logs / f'batch{i}_{kind}_{run_ts}.json'
        if p.exists():
            d=json.loads(p.read_text(encoding='utf-8'))
            item[kind]={
                'total_users':d.get('total_users'),
                'success_count':d.get('success_count'),
                'failure_count':d.get('failure_count')
            }
    summary['batches'].append(item)
out.write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))
PY

echo "[INFO] Summary file: $SUMMARY_JSON"
