"""
NodeRAG Evaluation Script
=========================
Processes the testing dataset through NodeRAG and stores answers, token counts,
and response times for both QA and NO_QA modes.

Usage:
    python evaluate_noderag.py

Edit the CONFIGURATION section below before running.
"""

import sys
import time
import json
import statistics
import pandas as pd
import yaml
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, str(Path(__file__).parent))

from NodeRAG import NodeConfig, NodeSearch


# ============================================================================
# CONFIGURATION — Edit these variables before running
# ============================================================================

# Which mode to run:
#   True  → NodeRAG with QA enabled   → results saved to "QA Answer / QA Tokens / QA Time"
#   False → NodeRAG with QA disabled  → results saved to "NO_QA Answer / NO_QA Tokens / NO_QA Time"
USE_QA: bool = True

# Maximum number of rows to process in this run.
# Set to None to process every unprocessed row in the dataset.
MAX_ROWS: Optional[int] = 1000

# Processing mode:
#   False → sequential (one row at a time)
#   True  → parallel   (PARALLEL_BATCH_SIZE rows at a time, each from a DIFFERENT user)
PARALLEL: bool = False

# Only used when PARALLEL = True.
# Number of rows processed concurrently per batch. Every row in a batch must
# belong to a different USER_ID so that no two threads share the same engine.
PARALLEL_BATCH_SIZE: int = 5

# Save the CSV to disk after every SAVE_INTERVAL successfully processed rows.
SAVE_INTERVAL: int = 50

# Number of times each query is run. Latency is averaged across all runs.
# Answer and token counts are taken from the first run only.
NUM_RUNS: int = 1

# Path to the testing CSV (the one prepared with USER_ID + result columns).
CSV_PATH: Path = Path("Dataset/qa_dataset_testing_20260315_173633.csv")

# Path to the resume → user_id JSON mapping file.
USER_MAPPING_PATH: Path = Path("Dataset/user_resume_mapping_20260204_192033.json")

# ============================================================================
# Derived constants (do not edit)
# ============================================================================

if USE_QA:
    ANSWER_COL = "QA Answer"
    TOKENS_COL = "QA Tokens"
    TIME_COL   = "QA Time"
    DISABLE_QA = False
    MODE_LABEL = "QA"
else:
    ANSWER_COL = "NO_QA Answer"
    TOKENS_COL = "NO_QA Tokens"
    TIME_COL   = "NO_QA Time"
    DISABLE_QA = True
    MODE_LABEL = "NO_QA"


# ============================================================================
# Initialisation helpers
# ============================================================================

def load_user_mapping(path: Path) -> Dict[str, str]:
    """Return {resumeFileName: "user_<userId>"} from the JSON mapping file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        entry["resumeFileName"]: f"user_{entry['userId']}"
        for entry in data["value"]
    }


def initialize_engine(user_id: str) -> NodeSearch:
    """
    Build a NodeSearch instance for *user_id*.

    Looks for a per-user Node_config.yaml first; falls back to the root config
    with the user_id injected.
    """
    user_config_path = (
        Path(__file__).parent
        / "POC_Data" / "documents" / "users" / user_id / "Node_config.yaml"
    )
    root_config_path = Path(__file__).parent / "Node_config.yaml"

    if user_config_path.exists():
        with open(user_config_path, "r") as f:
            config_data = yaml.safe_load(f)
        config = NodeConfig(config_data)
    else:
        with open(root_config_path, "r") as f:
            config_data = yaml.safe_load(f)
        if "config" not in config_data:
            config_data["config"] = {}
        # NodeConfig expects the numeric part only (strips "user_" internally)
        clean_id = user_id[len("user_"):] if user_id.startswith("user_") else user_id
        config_data["config"]["user_id"] = clean_id
        config = NodeConfig(config_data)

    return NodeSearch(config)


def initialize_all_engines(user_ids: List[str]) -> Dict[str, NodeSearch]:
    """Initialize a NodeSearch engine for every user in *user_ids*."""
    print(f"\n🔧 Initialising NodeRAG for {len(user_ids)} user(s)…")
    engines: Dict[str, NodeSearch] = {}

    for uid in sorted(user_ids):
        try:
            print(f"   {uid}…", end=" ", flush=True)
            engines[uid] = initialize_engine(uid)
            node_count = len(engines[uid].G.nodes)
            print(f"✓  ({node_count:,} nodes)")
        except Exception as exc:
            print(f"✗  {exc}")

    print(f"✅ Initialised {len(engines)}/{len(user_ids)} user(s)\n")
    return engines


# ============================================================================
# Core query function
# ============================================================================

def query_noderag(
    engine: NodeSearch,
    question: str,
    job_description: str,
    row_index: int,
) -> Tuple[int, Optional[str], Optional[int], Optional[float], Optional[str]]:
    """
    Run a single NodeRAG query NUM_RUNS times.

    - Answer and token counts are taken from the first successful run.
    - Elapsed time is the average across all NUM_RUNS runs.
    - If the first run fails, the error is returned immediately.

    Returns
    -------
    (row_index, answer, total_tokens, avg_elapsed_seconds, error_message)
    error_message is None on success.
    """
    first_answer: Optional[str] = None
    first_tokens: Optional[int] = None
    elapsed_times: List[float]  = []

    for run in range(NUM_RUNS):
        t0 = time.time()
        try:
            result  = engine.answer(question, job_context=job_description)
            elapsed = time.time() - t0
            elapsed_times.append(elapsed)

            if run == 0:
                retrieval_tokens = getattr(result, "retrieval_tokens", 0) or 0
                response_tokens  = getattr(result, "response_tokens",  0) or 0
                first_tokens     = retrieval_tokens + response_tokens
                first_answer     = result.response

        except Exception as exc:
            elapsed = time.time() - t0
            if run == 0:
                # First run failed — nothing to save
                return row_index, None, None, elapsed, str(exc)
            # Later runs failing: skip their timing but keep run-0 results

    avg_elapsed = sum(elapsed_times) / len(elapsed_times)
    return row_index, first_answer, first_tokens, avg_elapsed, None


# ============================================================================
# DataFrame helpers
# ============================================================================

def apply_result(
    df: pd.DataFrame,
    row_index: int,
    answer: Optional[str],
    tokens: Optional[int],
    elapsed: Optional[float],
) -> None:
    """Write one successful result back into the dataframe in-place."""
    df.at[row_index, ANSWER_COL] = answer  if answer  is not None else ""
    df.at[row_index, TOKENS_COL] = tokens  if tokens  is not None else 0
    df.at[row_index, TIME_COL]   = f"{elapsed:.2f}" if elapsed is not None else "0.00"


def save_csv(df: pd.DataFrame, path: Path) -> None:
    """
    Save the dataframe to *path*.
    On write failure, saves a timestamped backup instead.
    """
    try:
        df.to_csv(path, index=False, encoding="utf-8")
        print(f"  💾 Progress saved → {path.name}")
    except Exception as exc:
        backup = path.parent / f"{path.stem}_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df.to_csv(backup, index=False, encoding="utf-8")
        print(f"  ⚠️  Write failed ({exc}); backup saved → {backup.name}")


def get_unprocessed_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Return rows whose answer column is empty / NaN."""
    mask = df[ANSWER_COL].isna() | (df[ANSWER_COL].astype(str).str.strip() == "")
    return df[mask]


# ============================================================================
# Sequential processing
# ============================================================================

def process_sequential(
    df: pd.DataFrame,
    rows_to_process: pd.DataFrame,
    engines: Dict[str, NodeSearch],
    csv_path: Path,
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """
    Process rows one at a time. Saves every SAVE_INTERVAL successes.

    Returns (success_count, fail_count, results).
    """
    total      = len(rows_to_process)
    success_n  = 0
    fail_n     = 0
    since_save = 0
    results: List[Dict[str, Any]] = []

    for pos, (df_idx, row) in enumerate(rows_to_process.iterrows(), 1):
        uid       = row["USER_ID"]
        question  = row["Question"]
        jd        = row["Job Description"]
        job_title = row.get("Job Title", "")

        if uid not in engines:
            print(f"⚠️  [{pos}/{total}] Skipping — no engine for {uid}")
            fail_n += 1
            results.append({"success": False, "user_id": uid, "job_title": job_title,
                             "question": question, "total_tokens": 0,
                             "elapsed_seconds": 0.0, "answer_length": 0,
                             "error": "Engine not initialised"})
            continue

        print(f"[{pos}/{total}] {uid} | {question[:55]}…", end=" ", flush=True)

        _, answer, tokens, elapsed, err = query_noderag(
            engines[uid], question, jd, df_idx
        )

        if err:
            print(f"✗  {err}")
            fail_n += 1
            results.append({"success": False, "user_id": uid, "job_title": job_title,
                             "question": question, "total_tokens": 0,
                             "elapsed_seconds": elapsed or 0.0, "answer_length": 0,
                             "error": err})
        else:
            apply_result(df, df_idx, answer, tokens, elapsed)
            success_n  += 1
            since_save += 1
            print(f"✓  {elapsed:.1f}s | {tokens} tok")
            results.append({"success": True, "user_id": uid, "job_title": job_title,
                             "question": question, "total_tokens": tokens,
                             "elapsed_seconds": elapsed, "answer_length": len(answer or ""),
                             "error": None})

        if since_save >= SAVE_INTERVAL:
            save_csv(df, csv_path)
            since_save = 0

    # Always save at the end
    save_csv(df, csv_path)
    return success_n, fail_n, results


# ============================================================================
# Parallel processing
# ============================================================================

def build_parallel_batches(
    rows_to_process: pd.DataFrame,
    batch_size: int,
) -> List[List[Tuple[int, pd.Series]]]:
    """
    Organise rows into batches such that:
      - Each batch has at most *batch_size* rows.
      - Every row within a batch belongs to a DIFFERENT USER_ID.

    Strategy: round-robin across per-user queues.
    """
    # Build a queue of (df_index, row) for each user
    user_queues: Dict[str, List[Tuple[int, pd.Series]]] = {}
    for df_idx, row in rows_to_process.iterrows():
        uid = row["USER_ID"]
        user_queues.setdefault(uid, []).append((df_idx, row))

    queues = list(user_queues.values())
    batches: List[List[Tuple[int, pd.Series]]] = []

    while any(queues):
        batch: List[Tuple[int, pd.Series]] = []
        remaining_queues = []

        for q in queues:
            if not q:
                continue
            batch.append(q.pop(0))
            if len(batch) == batch_size:
                batches.append(batch)
                batch = []
            if q:
                remaining_queues.append(q)

        if batch:
            batches.append(batch)

        queues = remaining_queues

    return batches


def process_parallel(
    df: pd.DataFrame,
    rows_to_process: pd.DataFrame,
    engines: Dict[str, NodeSearch],
    csv_path: Path,
) -> Tuple[int, int, List[Dict[str, Any]]]:
    """
    Process rows in parallel batches.
    Each batch contains at most PARALLEL_BATCH_SIZE rows, all from different users.
    Saves every SAVE_INTERVAL successes.

    Returns (success_count, fail_count, results).
    """
    batches    = build_parallel_batches(rows_to_process, PARALLEL_BATCH_SIZE)
    total_rows = len(rows_to_process)
    success_n  = 0
    fail_n     = 0
    since_save = 0
    done_n     = 0
    results: List[Dict[str, Any]] = []

    print(f"   Batches: {len(batches)}  |  "
          f"≤{PARALLEL_BATCH_SIZE} rows/batch, each from a different user")

    for b_idx, batch in enumerate(batches, 1):
        print(f"\n  {'─'*60}")
        print(f"  Batch {b_idx}/{len(batches)}  ({len(batch)} rows in parallel)")

        futures: Dict = {}

        with ThreadPoolExecutor(max_workers=len(batch)) as executor:
            for df_idx, row in batch:
                uid       = row["USER_ID"]
                job_title = row.get("Job Title", "")

                if uid not in engines:
                    print(f"  ⚠️  No engine for {uid} — skipping row {df_idx}")
                    fail_n += 1
                    done_n += 1
                    results.append({"success": False, "user_id": uid, "job_title": job_title,
                                    "question": row["Question"], "total_tokens": 0,
                                    "elapsed_seconds": 0.0, "answer_length": 0,
                                    "error": "Engine not initialised"})
                    continue

                future = executor.submit(
                    query_noderag,
                    engines[uid],
                    row["Question"],
                    row["Job Description"],
                    df_idx,
                )
                futures[future] = (df_idx, uid, job_title, row["Question"])

            for future in as_completed(futures):
                df_idx, uid, job_title, question = futures[future]
                _, answer, tokens, elapsed, err = future.result()
                done_n += 1

                if err:
                    print(f"  ✗  [{done_n}/{total_rows}] {uid} | {err}")
                    fail_n += 1
                    results.append({"success": False, "user_id": uid, "job_title": job_title,
                                    "question": question, "total_tokens": 0,
                                    "elapsed_seconds": elapsed or 0.0, "answer_length": 0,
                                    "error": err})
                else:
                    apply_result(df, df_idx, answer, tokens, elapsed)
                    success_n  += 1
                    since_save += 1
                    print(f"  ✓  [{done_n}/{total_rows}] {uid} | {elapsed:.1f}s | {tokens} tok")
                    results.append({"success": True, "user_id": uid, "job_title": job_title,
                                    "question": question, "total_tokens": tokens,
                                    "elapsed_seconds": elapsed, "answer_length": len(answer or ""),
                                    "error": None})

        if since_save >= SAVE_INTERVAL:
            save_csv(df, csv_path)
            since_save = 0

    # Always save at the end
    save_csv(df, csv_path)
    return success_n, fail_n, results


# ============================================================================
# Statistics
# ============================================================================

def _latency_stats(values: List[float]) -> Dict[str, float]:
    """Return common latency descriptors for a list of second-values."""
    if not values:
        return {"avg": 0, "min": 0, "max": 0, "median": 0, "std_dev": 0}
    return {
        "avg":     round(sum(values) / len(values), 3),
        "min":     round(min(values), 3),
        "max":     round(max(values), 3),
        "median":  round(statistics.median(values), 3),
        "std_dev": round(statistics.pstdev(values), 3),
    }


def calculate_overall_stats(
    results: List[Dict[str, Any]],
    elapsed_total: float,
) -> Dict[str, Any]:
    """Overall statistics across all processed rows."""
    successful = [r for r in results if r["success"]]
    failed     = [r for r in results if not r["success"]]

    latencies = [r["elapsed_seconds"] for r in successful]
    tokens    = [r["total_tokens"]    for r in successful]
    lengths   = [r["answer_length"]   for r in successful]

    return {
        "mode":                MODE_LABEL,
        "total_rows":          len(results),
        "successful":          len(successful),
        "failed":              len(failed),
        "success_rate_pct":    round(len(successful) / len(results) * 100, 2) if results else 0,
        "total_elapsed_s":     round(elapsed_total, 2),
        "latency_s":           _latency_stats(latencies),
        "tokens": {
            "avg":   round(sum(tokens)  / len(tokens),  1) if tokens  else 0,
            "total": sum(tokens),
            "min":   min(tokens)  if tokens  else 0,
            "max":   max(tokens)  if tokens  else 0,
        },
        "avg_answer_length_chars": round(sum(lengths) / len(lengths), 1) if lengths else 0,
    }


def calculate_per_job_title_stats(
    results: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Per-job-title breakdown."""
    groups: Dict[str, List[Dict]] = {}
    for r in results:
        groups.setdefault(r["job_title"], []).append(r)

    out = {}
    for title, rows in sorted(groups.items()):
        successful = [r for r in rows if r["success"]]
        latencies  = [r["elapsed_seconds"] for r in successful]
        tokens     = [r["total_tokens"]    for r in successful]
        out[title] = {
            "total":           len(rows),
            "successful":      len(successful),
            "success_rate_pct": round(len(successful) / len(rows) * 100, 2),
            "latency_s":       _latency_stats(latencies),
            "avg_tokens":      round(sum(tokens) / len(tokens), 1) if tokens else 0,
        }
    return out


def calculate_per_user_stats(
    results: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    """Per-user breakdown."""
    groups: Dict[str, List[Dict]] = {}
    for r in results:
        groups.setdefault(r["user_id"], []).append(r)

    out = {}
    for uid, rows in sorted(groups.items()):
        successful = [r for r in rows if r["success"]]
        latencies  = [r["elapsed_seconds"] for r in successful]
        tokens     = [r["total_tokens"]    for r in successful]
        out[uid] = {
            "total":            len(rows),
            "successful":       len(successful),
            "success_rate_pct": round(len(successful) / len(rows) * 100, 2),
            "latency_s":        _latency_stats(latencies),
            "avg_tokens":       round(sum(tokens) / len(tokens), 1) if tokens else 0,
        }
    return out


def save_statistics_json(
    overall: Dict[str, Any],
    per_job_title: Dict[str, Any],
    per_user: Dict[str, Any],
    output_dir: Path,
) -> Path:
    """Save all statistics to a timestamped JSON file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"eval_statistics_{MODE_LABEL}_{timestamp}.json"

    payload = {
        "generated_at":      datetime.now().isoformat(),
        "overall":           overall,
        "per_job_title":     per_job_title,
        "per_user":          per_user,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    print(f"  📊 Statistics saved → {json_path.name}")
    return json_path


# ============================================================================
# Main
# ============================================================================

def main() -> None:
    print("\n" + "=" * 70)
    print("  NodeRAG Evaluation Script")
    print("=" * 70)

    print(f"\n⚙️  Configuration:")
    print(f"   USE_QA              : {USE_QA}  →  [{ANSWER_COL}] / [{TOKENS_COL}] / [{TIME_COL}]")
    print(f"   MAX_ROWS            : {MAX_ROWS if MAX_ROWS else 'all'}")
    print(f"   NUM_RUNS            : {NUM_RUNS}  (latency averaged; answer/tokens from run 1)")
    print(f"   PARALLEL            : {PARALLEL}")
    if PARALLEL:
        print(f"   PARALLEL_BATCH_SIZE : {PARALLEL_BATCH_SIZE}")
    print(f"   SAVE_INTERVAL       : every {SAVE_INTERVAL} rows")
    print(f"   CSV                 : {CSV_PATH}")

    # ── Validate CSV path ──────────────────────────────────────────────────
    if not CSV_PATH.exists():
        print(f"\n❌ CSV not found: {CSV_PATH}")
        sys.exit(1)

    # ── Load CSV ───────────────────────────────────────────────────────────
    print(f"\n📂 Loading {CSV_PATH.name}…")
    df = pd.read_csv(CSV_PATH, encoding="utf-8", low_memory=False)
    print(f"✅ {len(df):,} rows  |  {df['Resume File Name'].nunique()} resumes")

    # ── Verify required columns ────────────────────────────────────────────
    required = ["USER_ID", "Question", "Job Description",
                "QA Answer", "QA Tokens", "QA Time",
                "NO_QA Answer", "NO_QA Tokens", "NO_QA Time"]
    missing  = [c for c in required if c not in df.columns]
    if missing:
        print(f"\n❌ Missing columns: {missing}")
        print("   Run: python Dataset/prepare_testing_csv.py  first.")
        sys.exit(1)

    # Ensure result columns are object dtype (avoid silent float conversion)
    for col in [ANSWER_COL, TOKENS_COL, TIME_COL]:
        df[col] = df[col].astype(object)

    # ── Identify rows to process ───────────────────────────────────────────
    rows_to_process = get_unprocessed_rows(df)
    if MAX_ROWS:
        rows_to_process = rows_to_process.head(MAX_ROWS)

    already_done = len(df) - len(get_unprocessed_rows(df))
    print(f"\n📊 Status [{MODE_LABEL}]:")
    print(f"   Already processed : {already_done:,}")
    print(f"   To process        : {len(rows_to_process):,}")

    if rows_to_process.empty:
        print("\n✅ All rows already have answers — nothing to do.")
        return

    # ── Initialise engines ─────────────────────────────────────────────────
    unique_user_ids = sorted(rows_to_process["USER_ID"].dropna().unique().tolist())
    engines = initialize_all_engines(unique_user_ids)

    if not engines:
        print("❌ No engines could be initialised — aborting.")
        sys.exit(1)

    # ── Process ────────────────────────────────────────────────────────────
    print(f"\n🚀 Running {MODE_LABEL} evaluation "
          f"({'parallel' if PARALLEL else 'sequential'})…")

    t_start = time.time()

    if PARALLEL:
        success_n, fail_n, results = process_parallel(df, rows_to_process, engines, CSV_PATH)
    else:
        success_n, fail_n, results = process_sequential(df, rows_to_process, engines, CSV_PATH)

    elapsed_total = time.time() - t_start

    # ── Statistics ─────────────────────────────────────────────────────────
    print(f"\n📊 Calculating statistics…")
    overall       = calculate_overall_stats(results, elapsed_total)
    per_job_title = calculate_per_job_title_stats(results)
    per_user      = calculate_per_user_stats(results)
    json_path     = save_statistics_json(overall, per_job_title, per_user, Path("results"))

    # ── Summary ────────────────────────────────────────────────────────────
    print(f"\n{'=' * 70}")
    print("  ✅ Evaluation complete")
    print(f"{'=' * 70}")
    print(f"   Mode             : {MODE_LABEL}")
    print(f"   Successful       : {success_n:,}")
    print(f"   Failed           : {fail_n:,}")
    print(f"   Success rate     : {overall['success_rate_pct']}%")
    print(f"   Avg latency      : {overall['latency_s']['avg']}s")
    print(f"   Avg tokens       : {overall['tokens']['avg']}")
    print(f"   Total tokens     : {overall['tokens']['total']:,}")
    print(f"   Total time       : {elapsed_total:.1f}s  ({elapsed_total / 60:.1f} min)")
    print(f"   Output CSV       : {CSV_PATH.name}")
    print(f"   Statistics JSON  : {json_path.name}")
    print(f"{'=' * 70}\n")


if __name__ == "__main__":
    main()

