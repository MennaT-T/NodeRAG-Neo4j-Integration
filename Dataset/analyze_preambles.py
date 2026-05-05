"""
Analyze LLM Answer preambles in the balanced dataset.
Finds rows where the answer starts with unnecessary meta-commentary
instead of jumping directly into the answer.
"""

import pandas as pd
import numpy as np
import re
import os
import sys
from collections import Counter
from datetime import datetime

if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FILE = "qa_dataset_balanced_20260315_130715.csv"
INPUT_PATH = os.path.join(SCRIPT_DIR, INPUT_FILE)

# ── Patterns that indicate an unwanted preamble ──────────────────────────────
PREAMBLE_PATTERNS = [
    r"^okay[\s,]",
    r"^ok[\s,]",
    r"^sure[\s,]",
    r"^here'?s\b",
    r"^here is\b",
    r"^based on (the|this|your)\b",
    r"^alright[\s,]",
    r"^certainly[\s,]",
    r"^of course[\s,]",
    r"^great[\s,]",
    r"^as a candidate\b",
    r"^as an applicant\b",
    r"^this is my\b",
    r"^my response\b",
    r"^i'll answer\b",
    r"^i will answer\b",
    r"^in response\b",
    r"^let me\b",
    r"^below is\b",
    r"^the following\b",
    r"^thank you\b",
    r"^as requested\b",
    r"^i'd be happy\b",
    r"^i would be happy\b",
    r"^answering (the|this|your)\b",
    r"^to answer\b",
    r"^in answering\b",
]

COMBINED_PATTERN = re.compile("|".join(PREAMBLE_PATTERNS), re.IGNORECASE)

# ── How to strip the preamble: remove lines that are pure meta-commentary ────
def strip_preamble(text):
    """
    Remove leading lines that are pure meta-commentary (match the preamble
    pattern) and any blank lines that follow them.
    Returns the cleaned text.
    """
    lines = text.split("\n")
    # Walk forward and drop leading preamble lines
    start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            # blank line — skip
            start = i + 1
            continue
        if COMBINED_PATTERN.match(stripped):
            # preamble line — mark as consumed and continue
            start = i + 1
        else:
            # first non-preamble, non-blank line → stop
            break
    cleaned = "\n".join(lines[start:]).strip()
    return cleaned


print("\n" + "=" * 70)
print("🔍  Preamble Analysis")
print("=" * 70)

print(f"\n📂 Loading: {INPUT_FILE}")
df = pd.read_csv(INPUT_PATH, encoding="utf-8", low_memory=False)
print(f"✅ Loaded {len(df):,} rows")

# ── Flag rows ─────────────────────────────────────────────────────────────────
flagged_indices = []
first_lines_all = []

for idx, answer in df["LLM Answer"].items():
    if pd.isna(answer):
        continue
    first_line = str(answer).split("\n")[0].strip()
    first_lines_all.append(first_line)
    if COMBINED_PATTERN.match(first_line):
        flagged_indices.append(idx)

total = len(df)
n_flagged = len(flagged_indices)

print(f"\n{'─'*70}")
print(f"  Total rows:            {total:>8,}")
print(f"  Rows WITH preamble:    {n_flagged:>8,}  ({n_flagged/total*100:.1f}%)")
print(f"  Rows WITHOUT preamble: {total-n_flagged:>8,}  ({(total-n_flagged)/total*100:.1f}%)")
print(f"{'─'*70}")

# ── Variation breakdown ───────────────────────────────────────────────────────
def opening_phrase(line, n_words=6):
    return " ".join(line.lower().split()[:n_words])

flagged_first_lines = [str(df.at[i, "LLM Answer"]).split("\n")[0].strip()
                       for i in flagged_indices]
phrases = [opening_phrase(l) for l in flagged_first_lines]
counter = Counter(phrases)

print(f"\n📋 Top preamble variations ({len(counter)} unique opening phrases):\n")
print(f"  {'Count':>6}   Opening phrase")
print(f"  {'─'*6}   {'─'*55}")
for phrase, count in counter.most_common(40):
    print(f"  {count:>6,}   {phrase}")

# ── Show a few full examples ──────────────────────────────────────────────────
print(f"\n📝 Sample preamble lines (first 5):")
for i, line in enumerate(flagged_first_lines[:5], 1):
    print(f"  [{i}] {line[:120]}")

# ── Preview cleaning ──────────────────────────────────────────────────────────
print(f"\n🧹 Cleaning preview (first 3 flagged rows):")
for idx in flagged_indices[:3]:
    original = str(df.at[idx, "LLM Answer"])
    cleaned  = strip_preamble(original)
    print(f"\n  Row {idx}:")
    print(f"    BEFORE: {original[:150].strip()!r}")
    print(f"    AFTER:  {cleaned[:150].strip()!r}")

print(f"\n{'='*70}")
print("Run with --clean flag to generate the cleaned CSV:")
print("  python Dataset/analyze_preambles.py --clean")
print(f"{'='*70}\n")

# ── Optional: generate cleaned CSV ───────────────────────────────────────────
if "--clean" in sys.argv:
    print("\n🧹 Generating cleaned CSV...")
    df["LLM Answer"] = df["LLM Answer"].apply(
        lambda x: strip_preamble(str(x)) if pd.notna(x) else x
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_file = f"qa_dataset_balanced_clean_{timestamp}.csv"
    out_path = os.path.join(SCRIPT_DIR, out_file)
    df.to_csv(out_path, index=False, encoding="utf-8")
    size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"✅ Saved: {out_file}  ({size_mb:.2f} MB,  {len(df):,} rows)")

