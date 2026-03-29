"""
Multi-Tenant Scalability Benchmark
====================================
Measures NodeRAG QA system throughput and latency under concurrent user load.
Designed for research paper evaluation of multi-tenancy and scalability.

Methodology
-----------
1. Pre-initialise one NodeSearch engine per user (eliminates init overhead).
2. Fix a workload of ROWS_PER_USER rows per user (same rows at every level).
3. For each concurrency level C in CONCURRENCY_LEVELS:
     - Sample one row per user for each of NUM_ROUNDS rounds.
     - Launch exactly C threads simultaneously (one per unique user).
     - Measure: batch wall-clock time, per-request latency.
     - Collect p50 / p95 / p99 across all rounds.
4. Report throughput (req/s) and latency percentiles per concurrency level.

Constraints
-----------
- Max concurrency = number of available users (73 in this dataset).
- Each thread uses its own isolated engine → true multi-tenant isolation.
- USE_QA controls whether QA pipeline is active (same flag as evaluate_noderag.py).

Usage
-----
    python scalability_test.py

Edit the CONFIGURATION section below before running.
"""

import json
import random
import re
import statistics
import sys
import time
import yaml
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from NodeRAG import NodeConfig, NodeSearch


# ============================================================================
# CONFIGURATION
# ============================================================================

# Whether to use the QA pipeline during search (mirrors evaluate_noderag.py flag)
USE_QA: bool = True

# Concurrency levels to test (must be <= number of available users = 73)
CONCURRENCY_LEVELS: List[int] = [5, 10, 20, 50, 73]

# Number of distinct rows selected per user for the fixed workload pool.
# Total workload = ROWS_PER_USER × number_of_users.
# Each round draws one row per user from this pool.
ROWS_PER_USER: int = 5

# Number of rounds at each concurrency level.
# Higher = more stable statistics. Each round fires C requests simultaneously.
# Rounds are separated by INTER_ROUND_SLEEP seconds.
NUM_ROUNDS: int = 10

# Seconds to sleep between rounds (applies at every concurrency level).
# Must be > 60s + max backoff time (30s) to clear both the rolling RPM window
# AND any leftover retry calls from backoff that fall inside the next round's
# 60s TPM window.  120s gives a comfortable margin (60s window + 30s max_time
# backoff + 30s buffer).
INTER_ROUND_SLEEP: int = 60

# Random seed for reproducible workload selection.
RANDOM_SEED: int = 42

# API keys — one per "key slot".
# Engines are assigned to keys round-robin (engine i → API_KEYS[i % len(API_KEYS)]).
# With 5 keys and 73 users at C=73: each key handles ~15 engines × 2 LLM calls
# = ~30 LLM calls per round → stays at the 30 RPM free-tier limit per key.
# Set to a single-element list to use one key for everything (lower concurrency only).
API_KEYS: List[str] = [
]

# Path to the dataset CSV.
CSV_PATH: Path = Path("Dataset/qa_dataset_testing_20260315_173633.csv")

# Where to write the results JSON.
OUTPUT_DIR: Path = Path("results")

# ============================================================================
# Engine initialisation  (same logic as evaluate_noderag.py)
# ============================================================================

def initialize_engine(user_id: str, api_key: str) -> NodeSearch:
    """
    Build a NodeSearch for *user_id*, injecting *api_key* into both
    model_config and embedding_config in-memory — no files are written.
    """
    user_config_path = (
        Path(__file__).parent
        / "POC_Data" / "documents" / "users" / user_id / "Node_config.yaml"
    )
    root_config_path = Path(__file__).parent / "Node_config.yaml"

    if user_config_path.exists():
        with open(user_config_path) as f:
            config_data = yaml.safe_load(f)
    else:
        with open(root_config_path) as f:
            config_data = yaml.safe_load(f)
        if "config" not in config_data:
            config_data["config"] = {}
        clean_id = user_id[len("user_"):] if user_id.startswith("user_") else user_id
        config_data["config"]["user_id"] = clean_id

    # Inject the assigned API key for both LLM and embedding clients.
    # This overwrites the key from the yaml in-memory only — the file is untouched.
    config_data["model_config"]["api_keys"]     = api_key
    config_data["embedding_config"]["api_keys"] = api_key


    # NodeConfig is a Singleton — without this reset every NodeConfig(...)
    # call returns the SAME instance, so all 73 engines end up sharing one
    # config object that holds the LAST key written.  Resetting _instance
    # before each call forces a fresh object per engine.  The previously
    # created engines keep their own NodeConfig reference alive via
    # NodeSearch.config, so they are unaffected by the reset.
    NodeConfig._instance = None
    return NodeSearch(NodeConfig(config_data))


def initialize_all_engines(user_ids: List[str]) -> Dict[str, NodeSearch]:
    """
    Initialise one engine per user, assigning API keys round-robin so that
    each key covers at most ceil(N / len(API_KEYS)) engines.

    At C=73 with 5 keys: ~15 engines/key × 2 LLM calls = ~30 LLM calls/key
    per round — right at the 30 RPM free-tier limit per key.
    """
    sorted_ids = sorted(user_ids)
    n_keys     = len(API_KEYS)

    print(f"\n🔧 Pre-initialising {len(sorted_ids)} engines across {n_keys} API key(s)…")
    for ki, key in enumerate(API_KEYS):
        assigned = [uid for i, uid in enumerate(sorted_ids) if i % n_keys == ki]
        print(f"   Key {ki+1} ({key[:12]}…): {len(assigned)} engines")

    engines: Dict[str, NodeSearch] = {}
    for i, uid in enumerate(sorted_ids):
        key = API_KEYS[i % n_keys]
        try:
            print(f"   [{i+1}/{len(sorted_ids)}] {uid} → key {i % n_keys + 1}…",
                  end=" ", flush=True)
            engines[uid] = initialize_engine(uid, api_key=key)
            print(f"✓  ({len(engines[uid].G.nodes):,} nodes)")
        except Exception as exc:
            print(f"✗  {exc}")

    print(f"✅ Ready: {len(engines)}/{len(sorted_ids)} engines\n")
    return engines


# ============================================================================
# Single-request worker
# ============================================================================

def _is_error_response(text: str) -> bool:
    """
    Detect responses that are actually API error strings silently returned
    by @error_handler (which does `return str(e)`) instead of raising.

    Detection is based on the FORMAT of API error strings, not keywords,
    to avoid false positives on legitimate answers that mention words like
    'error', 'failed', 'quota', etc.

    API errors from the Google/Gemini client always look like:
        "429 RESOURCE_EXHAUSTED. {'error': {'code': 429, ..."
        "500 Internal Server Error ..."
        "503 Service Unavailable ..."
    i.e. they start with a 3-digit HTTP status code followed by a space.

    A real job-application answer never starts with a 3-digit number.
    """
    if not text:
        return True
    # HTTP status code at the start → definitely an API error string
    stripped = text.strip()
    if re.match(r'^\d{3}\s', stripped):
        return True
    # Google API error JSON embedded in the string (secondary check)
    if "'error': {'code':" in stripped or '"error": {"code":' in stripped:
        return True
    return False


def run_request(
    engine: NodeSearch,
    question: str,
    job_description: str,
    use_qa: bool,
    user_id: str = "",
    key_index: int = -1,
) -> Dict[str, Any]:
    """Execute one answer() call and return timing + outcome."""
    t0 = time.perf_counter()
    try:
        result  = engine.answer(question, job_context=job_description, use_qa=use_qa)
        elapsed = time.perf_counter() - t0
        response_text = result.response or ""

        # Detect silently-swallowed API errors (e.g. 429 returned as a string
        # by @error_handler instead of raising). Mark these as failures so they
        # are not counted as successful requests in the benchmark stats.
        if _is_error_response(response_text):
            preview = response_text[:120].replace("\n", " ")
            key_label = f"key {key_index + 1}" if key_index >= 0 else "unknown key"
            print(f"      ⚠️  [{user_id} / {key_label}] Degraded response → \"{preview}\"")
            return {
                "success":    False,
                "elapsed_s":  elapsed,
                "answer_length": 0,
                "tokens":     0,
                "user_id":    user_id,
                "key_index":  key_index,
                "error":      f"Degraded response: {preview}",
            }

        return {
            "success":       True,
            "elapsed_s":     elapsed,
            "answer_length": len(response_text),
            "tokens":        (getattr(result, "retrieval_tokens", 0) or 0)
                           + (getattr(result, "response_tokens",  0) or 0),
            "user_id":       user_id,
            "key_index":     key_index,
            "error":         None,
        }
    except Exception as exc:
        print(f"      ⚠️  [{user_id} / key {key_index + 1}] Exception → {str(exc)[:80]}")
        return {
            "success":    False,
            "elapsed_s":  time.perf_counter() - t0,
            "answer_length": 0,
            "tokens":     0,
            "user_id":    user_id,
            "key_index":  key_index,
            "error":      str(exc),
        }


# ============================================================================
# Workload builder
# ============================================================================

def build_workload(
    df: pd.DataFrame,
    user_ids: List[str],
    rows_per_user: int,
    seed: int,
) -> Dict[str, List[Dict]]:
    """
    For each user, sample *rows_per_user* rows from the dataset.
    Returns {user_id: [ {question, job_description}, ... ]}
    """
    rng = random.Random(seed)
    workload: Dict[str, List[Dict]] = {}
    for uid in user_ids:
        user_rows = df[df["USER_ID"] == uid]
        sample    = user_rows.sample(
            n=min(rows_per_user, len(user_rows)),
            random_state=seed,
        )
        workload[uid] = [
            {"question": row["Question"], "job_description": row["Job Description"]}
            for _, row in sample.iterrows()
        ]
    return workload


# ============================================================================
# Concurrency level runner
# ============================================================================

def run_concurrency_level(
    concurrency:  int,
    engines:      Dict[str, NodeSearch],
    workload:     Dict[str, List[Dict]],
    num_rounds:   int,
    use_qa:       bool,
) -> Dict[str, Any]:
    """
    Run *num_rounds* rounds at *concurrency* simultaneous users.

    Each round:
      - Selects *concurrency* users (rotating so every user gets coverage).
      - Picks the next unused row from their workload pool (round-robin).
      - Fires all requests simultaneously and measures wall-clock time.

    Returns aggregated statistics for this concurrency level.
    """
    available_users = [u for u in sorted(workload.keys()) if u in engines]
    if len(available_users) < concurrency:
        print(f"   ⚠️  Only {len(available_users)} engines available — "
              f"capping concurrency at {len(available_users)}")
        concurrency = len(available_users)

    # Build user → key index lookup (same round-robin formula used at init)
    sorted_all  = sorted(engines.keys())
    user_to_key = {uid: i % len(API_KEYS) for i, uid in enumerate(sorted_all)}

    # Cursor into each user's workload list (round-robin across rounds)
    cursors: Dict[str, int] = {u: 0 for u in available_users}

    all_request_latencies: List[float] = []
    batch_wall_times:      List[float] = []
    success_count = 0
    fail_count    = 0

    print(f"\n   C={concurrency:>3}  ({num_rounds} rounds × {concurrency} simultaneous users)")

    for round_idx in range(1, num_rounds + 1):
        # Pick C users for this round (rotate)
        offset   = (round_idx - 1) * concurrency
        selected = [available_users[i % len(available_users)]
                    for i in range(offset, offset + concurrency)]
        # Deduplicate while preserving order (shouldn't happen but safety net)
        seen: set = set()
        selected  = [u for u in selected if not (u in seen or seen.add(u))]  # type: ignore[func-returns-value]

        tasks: List[Tuple[str, str, str]] = []
        for uid in selected:
            pool = workload[uid]
            row  = pool[cursors[uid] % len(pool)]
            cursors[uid] += 1
            tasks.append((uid, row["question"], row["job_description"]))

        # Fire all C requests simultaneously
        t_batch_start = time.perf_counter()
        futures = {}
        with ThreadPoolExecutor(max_workers=len(tasks)) as executor:
            for uid, question, jd in tasks:
                ki = user_to_key.get(uid, -1)
                f  = executor.submit(run_request, engines[uid], question, jd,
                                     use_qa, uid, ki)
                futures[f] = uid

            round_results = []
            for f in as_completed(futures):
                round_results.append(f.result())

        batch_wall = time.perf_counter() - t_batch_start
        batch_wall_times.append(batch_wall)

        r_success = [r for r in round_results if r["success"]]
        r_fail    = [r for r in round_results if not r["success"]]
        success_count += len(r_success)
        fail_count    += len(r_fail)
        all_request_latencies.extend(r["elapsed_s"] for r in r_success)

        avg_lat = statistics.mean(r["elapsed_s"] for r in r_success) if r_success else 0
        print(f"      round {round_idx:>2}/{num_rounds}  "
              f"wall={batch_wall:.1f}s  "
              f"avg_lat={avg_lat:.1f}s  "
              f"✓{len(r_success)} ✗{len(r_fail)}")

        # If there were failures, show a per-key breakdown so you can tell
        # immediately which key(s) are exhausted.
        if r_fail:
            key_fail_counts = Counter(
                f"key {r['key_index'] + 1}" for r in r_fail if r.get("key_index", -1) >= 0
            )
            print(f"         Failed by key: " +
                  "  ".join(f"{k}: {v}✗" for k, v in sorted(key_fail_counts.items())))

        # Wait between rounds so the next burst doesn't start within the same
        # minute — guarantees at most C Gemini calls per INTER_ROUND_SLEEP window.
        if round_idx < num_rounds:
            print(f"      ⏳ sleeping {INTER_ROUND_SLEEP}s before next round…")
            time.sleep(INTER_ROUND_SLEEP)

    # ── Aggregate ──────────────────────────────────────────────────────────
    total_requests = success_count + fail_count
    total_wall     = sum(batch_wall_times)
    throughput     = success_count / total_wall if total_wall > 0 else 0

    def pct(values: List[float], p: float) -> float:
        if not values:
            return 0.0
        sorted_v = sorted(values)
        idx = int(len(sorted_v) * p / 100)
        return round(sorted_v[min(idx, len(sorted_v) - 1)], 3)

    lat = all_request_latencies
    return {
        "concurrency":       concurrency,
        "num_rounds":        num_rounds,
        "total_requests":    total_requests,
        "successful":        success_count,
        "failed":            fail_count,
        "success_rate_pct":  round(success_count / total_requests * 100, 2) if total_requests else 0,
        "throughput_req_s":  round(throughput, 4),
        "total_wall_s":      round(total_wall, 2),
        "latency_s": {
            "avg":    round(statistics.mean(lat),   3) if lat else 0,
            "median": round(statistics.median(lat), 3) if lat else 0,
            "std":    round(statistics.pstdev(lat), 3) if lat else 0,
            "min":    round(min(lat),               3) if lat else 0,
            "max":    round(max(lat),               3) if lat else 0,
            "p95":    pct(lat, 95),
            "p99":    pct(lat, 99),
        },
        "batch_wall_s": {
            "avg":    round(statistics.mean(batch_wall_times),   2),
            "median": round(statistics.median(batch_wall_times), 2),
            "min":    round(min(batch_wall_times),               2),
            "max":    round(max(batch_wall_times),               2),
        },
    }


# ============================================================================
# Pretty report
# ============================================================================

def print_report(results: List[Dict], baseline_throughput: float) -> None:
    print(f"\n{'═'*80}")
    print("  SCALABILITY BENCHMARK RESULTS")
    print(f"{'═'*80}")
    print(f"  {'C':>5}  {'Throughput':>12}  {'Efficiency':>10}  "
          f"{'Avg lat':>9}  {'p50':>7}  {'p95':>7}  {'p99':>7}  "
          f"{'Batch avg':>10}  {'Success':>8}")
    print(f"  {'(users)':>5}  {'(req/s)':>12}  {'(%)':>10}  "
          f"{'(s)':>9}  {'(s)':>7}  {'(s)':>7}  {'(s)':>7}  "
          f"{'wall (s)':>10}  {'rate':>8}")
    print("  " + "─" * 78)

    for r in results:
        c          = r["concurrency"]
        tput       = r["throughput_req_s"]
        efficiency = (tput / (c * baseline_throughput) * 100) if baseline_throughput > 0 else 0
        lat        = r["latency_s"]
        bw         = r["batch_wall_s"]
        print(
            f"  {c:>5}  {tput:>12.4f}  {efficiency:>9.1f}%  "
            f"  {lat['avg']:>7.2f}  {lat['median']:>7.2f}  "
            f"{lat['p95']:>7.2f}  {lat['p99']:>7.2f}  "
            f"{bw['avg']:>10.2f}  {r['success_rate_pct']:>7.1f}%"
        )

    print(f"\n  Efficiency = throughput(C) / (C × throughput(1 user equivalent))")
    print(f"  100% = perfect linear scaling")
    print(f"{'═'*80}\n")


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    print("\n" + "=" * 70)
    print("  NodeRAG — Multi-Tenant Scalability Benchmark")
    print("=" * 70)
    print(f"\n⚙️  Configuration:")
    print(f"   USE_QA             : {USE_QA}")
    print(f"   CONCURRENCY_LEVELS : {CONCURRENCY_LEVELS}")
    print(f"   NUM_ROUNDS         : {NUM_ROUNDS}")
    print(f"   INTER_ROUND_SLEEP  : {INTER_ROUND_SLEEP}s")
    print(f"   API_KEYS           : {len(API_KEYS)} key(s)  "
          f"(~{max(CONCURRENCY_LEVELS) // len(API_KEYS) * 2} LLM calls/key at C={max(CONCURRENCY_LEVELS)})")
    print(f"   ROWS_PER_USER      : {ROWS_PER_USER}")
    print(f"   RANDOM_SEED        : {RANDOM_SEED}")
    print(f"   CSV                : {CSV_PATH}")

    if not CSV_PATH.exists():
        print(f"\n❌ CSV not found: {CSV_PATH}")
        sys.exit(1)

    # ── Load dataset ───────────────────────────────────────────────────────
    print(f"\n📂 Loading dataset…")
    df = pd.read_csv(CSV_PATH, encoding="utf-8", low_memory=False)
    all_users = sorted(df["USER_ID"].dropna().unique().tolist())
    max_c     = max(CONCURRENCY_LEVELS)

    print(f"✅ {len(df):,} rows  |  {len(all_users)} users")
    if len(all_users) < max_c:
        print(f"⚠️  Max concurrency capped at {len(all_users)} (dataset has {len(all_users)} users)")

    # ── Build fixed workload ───────────────────────────────────────────────
    print(f"\n🗂  Building fixed workload ({ROWS_PER_USER} rows/user)…")
    workload = build_workload(df, all_users, ROWS_PER_USER, RANDOM_SEED)
    total_workload = sum(len(v) for v in workload.values())
    print(f"   {total_workload} total rows across {len(workload)} users")

    # ── Pre-initialise all engines ─────────────────────────────────────────
    engines = initialize_all_engines(all_users)
    if not engines:
        print("❌ No engines initialised — aborting.")
        sys.exit(1)

    # ── Run each concurrency level ─────────────────────────────────────────
    print(f"\n🚀 Running benchmark…")
    level_results: List[Dict] = []

    for level_idx, c in enumerate(CONCURRENCY_LEVELS):
        if c > len(engines):
            print(f"\n   ⚠️  Skipping C={c} — only {len(engines)} engines available")
            continue

        # Cool-down between concurrency levels so the previous level's API
        # calls don't bleed into this level's rate-limit window.
        if level_idx > 0:
            print(f"\n   ⏳ Cooling down {INTER_ROUND_SLEEP}s before C={c}…")
            time.sleep(INTER_ROUND_SLEEP)

        result = run_concurrency_level(c, engines, workload, NUM_ROUNDS, USE_QA)
        level_results.append(result)

    if not level_results:
        print("❌ No results collected.")
        sys.exit(1)

    # Baseline throughput = throughput at lowest concurrency level
    baseline_throughput = level_results[0]["throughput_req_s"] / level_results[0]["concurrency"]

    # ── Print report ───────────────────────────────────────────────────────
    print_report(level_results, baseline_throughput)

    # ── Save JSON ──────────────────────────────────────────────────────────
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    mode      = "QA" if USE_QA else "NO_QA"
    json_path = OUTPUT_DIR / f"scalability_{mode}_{ts}.json"

    payload = {
        "generated_at":      datetime.now().isoformat(),
        "config": {
            "use_qa":             USE_QA,
            "concurrency_levels": CONCURRENCY_LEVELS,
            "num_rounds":         NUM_ROUNDS,
            "rows_per_user":      ROWS_PER_USER,
            "random_seed":        RANDOM_SEED,
            "total_users":        len(engines),
        },
        "results": level_results,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"💾 Results saved → {json_path.name}\n")


if __name__ == "__main__":
    main()
