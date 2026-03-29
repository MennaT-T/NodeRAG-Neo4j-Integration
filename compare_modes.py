"""
LLM vs QA vs NO_QA Comparison
==============================
Compares the three answer modes across the rows where all three are filled.

Metrics
-------
Operational  : answer length (chars), token count, latency (s)
Content      : Jaccard similarity and bigram overlap between every pair of modes
               (no external NLP library required)

Output
------
  results/comparison_<timestamp>.json   — full statistics
  Printed summary table to stdout

Usage
-----
    python compare_modes.py
"""

import json
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

# ── Configuration ──────────────────────────────────────────────────────────────

CSV_PATH = Path("Dataset/qa_dataset_testing_20260315_173633.csv")
OUTPUT_DIR = Path("results")

# ── Text helpers ───────────────────────────────────────────────────────────────

def tokenise(text: str) -> List[str]:
    """Lowercase word tokens — no extra library needed."""
    return re.findall(r"[a-z']+", text.lower())


def bigrams(tokens: List[str]) -> List[Tuple[str, str]]:
    return list(zip(tokens, tokens[1:]))


def jaccard(a: List, b: List) -> float:
    sa, sb = set(a), set(b)
    if not sa and not sb:
        return 1.0
    union = sa | sb
    return len(sa & sb) / len(union) if union else 0.0


def overlap_ratio(a: List, b: List) -> float:
    """|a ∩ b| / max(|a|, |b|) — asymmetric overlap."""
    sa, sb = set(a), set(b)
    denom = max(len(sa), len(sb))
    return len(sa & sb) / denom if denom else 0.0


def similarity_metrics(text_a: str, text_b: str) -> Dict[str, float]:
    ta, tb = tokenise(text_a), tokenise(text_b)
    ba, bb = bigrams(ta), bigrams(tb)
    return {
        "unigram_jaccard":  round(jaccard(ta, tb), 4),
        "bigram_jaccard":   round(jaccard(ba, bb), 4),
        "unigram_overlap":  round(overlap_ratio(ta, tb), 4),
    }

# ── Stat helpers ───────────────────────────────────────────────────────────────

def num_stats(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"n": 0, "avg": 0, "min": 0, "max": 0, "median": 0, "std_dev": 0}
    return {
        "n":       len(values),
        "avg":     round(statistics.mean(values),   2),
        "min":     round(min(values),               2),
        "max":     round(max(values),               2),
        "median":  round(statistics.median(values), 2),
        "std_dev": round(statistics.pstdev(values), 2),
    }


def sim_stats(pairs: List[Dict[str, float]]) -> Dict[str, Dict[str, float]]:
    if not pairs:
        return {}
    keys = pairs[0].keys()
    return {k: num_stats([p[k] for p in pairs]) for k in keys}

# ── Column definitions ─────────────────────────────────────────────────────────

MODES = {
    "LLM":   {"answer": "LLM Answer",   "tokens": "Tokens",      "time": "Time"},
    "QA":    {"answer": "QA Answer",    "tokens": "QA Tokens",   "time": "QA Time"},
    "NO_QA": {"answer": "NO_QA Answer", "tokens": "NO_QA Tokens","time": "NO_QA Time"},
}

PAIRS = [
    ("QA",    "LLM"),
    ("NO_QA", "LLM"),
    ("QA",    "NO_QA"),
]

# ── Core analysis ──────────────────────────────────────────────────────────────

def analyse(df: pd.DataFrame) -> Dict:
    """
    Run the full comparison on *df* (assumed: all three answer columns filled).
    Returns a nested dict ready for JSON serialisation.
    """

    def safe_float(v) -> Optional[float]:
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    # ── Per-mode operational stats ─────────────────────────────────────────
    mode_stats: Dict[str, Dict] = {}
    for mode, cols in MODES.items():
        lengths = [len(str(v)) for v in df[cols["answer"]] if pd.notna(v)]
        tokens  = [x for v in df[cols["tokens"]] if (x := safe_float(v)) is not None]
        times   = [x for v in df[cols["time"]]   if (x := safe_float(v)) is not None]
        mode_stats[mode] = {
            "answer_length_chars": num_stats(lengths),
            "tokens":              num_stats(tokens),
            "latency_s":           num_stats(times),
        }

    # ── Per-pair similarity ────────────────────────────────────────────────
    pair_stats: Dict[str, Dict] = {}
    for m1, m2 in PAIRS:
        key   = f"{m1}_vs_{m2}"
        sims  = []
        col1  = MODES[m1]["answer"]
        col2  = MODES[m2]["answer"]
        for a, b in zip(df[col1], df[col2]):
            if pd.notna(a) and pd.notna(b):
                sims.append(similarity_metrics(str(a), str(b)))
        pair_stats[key] = sim_stats(sims)

    # ── Per-job-title breakdown ────────────────────────────────────────────
    per_job: Dict[str, Dict] = {}
    for title, grp in df.groupby("Job Title"):
        per_job[str(title)] = {
            "n": len(grp),
            "modes": {},
            "similarity": {},
        }
        for mode, cols in MODES.items():
            lengths = [len(str(v)) for v in grp[cols["answer"]] if pd.notna(v)]
            tokens  = [x for v in grp[cols["tokens"]] if (x := safe_float(v)) is not None]
            per_job[str(title)]["modes"][mode] = {
                "avg_length_chars": round(statistics.mean(lengths), 1) if lengths else 0,
                "avg_tokens":       round(statistics.mean(tokens),  1) if tokens  else 0,
            }
        for m1, m2 in PAIRS:
            key  = f"{m1}_vs_{m2}"
            sims = []
            for a, b in zip(grp[MODES[m1]["answer"]], grp[MODES[m2]["answer"]]):
                if pd.notna(a) and pd.notna(b):
                    sims.append(similarity_metrics(str(a), str(b)))
            per_job[str(title)]["similarity"][key] = {
                k: round(statistics.mean([s[k] for s in sims]), 4) if sims else 0
                for k in (sims[0].keys() if sims else [])
            }

    # ── Per-user breakdown (operational only for brevity) ─────────────────
    per_user: Dict[str, Dict] = {}
    for uid, grp in df.groupby("USER_ID"):
        per_user[str(uid)] = {"n": len(grp), "modes": {}}
        for mode, cols in MODES.items():
            lengths = [len(str(v)) for v in grp[cols["answer"]] if pd.notna(v)]
            tokens  = [x for v in grp[cols["tokens"]] if (x := safe_float(v)) is not None]
            times   = [x for v in grp[cols["time"]]   if (x := safe_float(v)) is not None]
            per_user[str(uid)]["modes"][mode] = {
                "avg_length_chars": round(statistics.mean(lengths), 1) if lengths else 0,
                "avg_tokens":       round(statistics.mean(tokens),  1) if tokens  else 0,
                "avg_latency_s":    round(statistics.mean(times),   2) if times   else 0,
            }

    return {
        "generated_at":    datetime.now().isoformat(),
        "rows_compared":   len(df),
        "unique_users":    df["USER_ID"].nunique(),
        "unique_jobs":     df["Job Title"].nunique(),
        "job_title_counts": df["Job Title"].value_counts().to_dict(),
        "overall": {
            "mode_stats":  mode_stats,
            "pair_similarity": pair_stats,
        },
        "per_job_title": per_job,
        "per_user":      per_user,
    }

# ── Pretty printer ─────────────────────────────────────────────────────────────

def W(n: int = 70) -> str:
    return "─" * n

def print_report(data: Dict) -> None:
    ov   = data["overall"]
    ms   = ov["mode_stats"]
    ps   = ov["pair_similarity"]

    print(f"\n{'═'*70}")
    print("  LLM  vs  QA  vs  NO_QA  —  Comparison Report")
    print(f"{'═'*70}")
    print(f"  Rows compared  : {data['rows_compared']:,}")
    print(f"  Unique users   : {data['unique_users']}")
    print(f"  Job titles     : {data['unique_jobs']}")
    for title, cnt in sorted(data['job_title_counts'].items()):
        print(f"    ├─ {title}: {cnt:,}")

    # ── Operational ───────────────────────────────────────────────────────
    print(f"\n{W()}")
    print("  OPERATIONAL METRICS  (on overlap rows)")
    print(W())

    hdr = f"{'Metric':<30}{'LLM':>12}{'QA':>12}{'NO_QA':>12}  {'QA vs LLM':>12}  {'NO_QA vs LLM':>14}"
    print(hdr)
    print("─" * len(hdr))

    def diff(qa_v, llm_v, pct=False) -> str:
        if pct:
            d = (qa_v - llm_v) / llm_v * 100 if llm_v else 0
            return f"{d:+.1f}%"
        return f"{qa_v - llm_v:+.1f}"

    for label, key, sub in [
        ("Avg length (chars)",  "answer_length_chars", "avg"),
        ("Avg tokens",          "tokens",              "avg"),
        ("Avg latency (s)",     "latency_s",           "avg"),
        ("Std latency (s)",     "latency_s",           "std_dev"),
        ("Min latency (s)",     "latency_s",           "min"),
        ("Max latency (s)",     "latency_s",           "max"),
    ]:
        llm_v   = ms["LLM"][key][sub]
        qa_v    = ms["QA"][key][sub]
        noqa_v  = ms["NO_QA"][key][sub]
        print(
            f"  {label:<28}{llm_v:>12.1f}{qa_v:>12.1f}{noqa_v:>12.1f}"
            f"  {diff(qa_v, llm_v):>12}  {diff(noqa_v, llm_v):>14}"
        )

    # ── Content similarity ─────────────────────────────────────────────────
    print(f"\n{W()}")
    print("  CONTENT SIMILARITY  (word-level, avg over all overlap rows)")
    print(W())
    print(f"  Note: 1.0 = identical  |  0.0 = no shared words\n")

    sim_labels = {
        "unigram_jaccard": "Unigram Jaccard",
        "bigram_jaccard":  "Bigram Jaccard",
        "unigram_overlap": "Unigram Overlap",
    }
    pair_display = {
        "QA_vs_LLM":    "QA  ↔  LLM",
        "NO_QA_vs_LLM": "NO_QA  ↔  LLM",
        "QA_vs_NO_QA":  "QA  ↔  NO_QA",
    }

    hdr2 = f"  {'Metric':<22}" + "".join(f"{v:>18}" for v in pair_display.values())
    print(hdr2)
    print("  " + "─" * (len(hdr2) - 2))

    for sim_key, sim_label in sim_labels.items():
        row = f"  {sim_label:<22}"
        for pair_key in pair_display:
            val = ps[pair_key][sim_key]["avg"]
            row += f"{val:>18.4f}"
        print(row)

    # ── Per job title ──────────────────────────────────────────────────────
    print(f"\n{W()}")
    print("  PER JOB TITLE  —  avg length (chars)  |  unigram Jaccard vs LLM")
    print(W())
    print(f"  {'Job Title':<26}{'N':>5}  {'LLM':>8}  {'QA':>8}  {'NO_QA':>8}  {'QA↔LLM':>10}  {'NOQ↔LLM':>10}")
    print("  " + "─" * 68)

    for title, jd in sorted(data["per_job_title"].items()):
        n      = jd["n"]
        llm_l  = jd["modes"]["LLM"]["avg_length_chars"]
        qa_l   = jd["modes"]["QA"]["avg_length_chars"]
        noqa_l = jd["modes"]["NO_QA"]["avg_length_chars"]
        qa_j   = jd["similarity"].get("QA_vs_LLM",    {}).get("unigram_jaccard", 0)
        noqa_j = jd["similarity"].get("NO_QA_vs_LLM", {}).get("unigram_jaccard", 0)
        print(f"  {title:<26}{n:>5}  {llm_l:>8.0f}  {qa_l:>8.0f}  {noqa_l:>8.0f}  {qa_j:>10.4f}  {noqa_j:>10.4f}")

    print(f"\n{'═'*70}\n")

# ── Main ───────────────────────────────────────────────────────────────────────

def main() -> None:
    if not CSV_PATH.exists():
        print(f"❌ CSV not found: {CSV_PATH}")
        sys.exit(1)

    print(f"📂 Loading {CSV_PATH.name}…")
    df = pd.read_csv(CSV_PATH, encoding="utf-8", low_memory=False)

    # Keep only rows where all three answers are filled
    mask = (
        df["LLM Answer"].notna()   & (df["LLM Answer"].astype(str).str.strip()   != "") &
        df["QA Answer"].notna()    & (df["QA Answer"].astype(str).str.strip()    != "") &
        df["NO_QA Answer"].notna() & (df["NO_QA Answer"].astype(str).str.strip() != "")
    )
    overlap = df[mask].copy()
    print(f"✅ {len(overlap):,} rows with all three answers filled  (out of {len(df):,} total)\n")

    if overlap.empty:
        print("❌ No overlapping rows — nothing to compare.")
        sys.exit(0)

    print("⚙️  Computing metrics…")
    data = analyse(overlap)

    # Save JSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = OUTPUT_DIR / f"comparison_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"💾 Full results saved → {json_path.name}\n")

    print_report(data)


if __name__ == "__main__":
    main()
