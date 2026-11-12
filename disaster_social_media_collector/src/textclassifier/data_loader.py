"""
run_classifier.py
=================
Pipeline: Tumblr + Twitter data -> classifier -> one output file per class.

Usage (from src/textclassifier):
    python run_classifier.py                      # rules only
    python run_classifier.py --golden golden.csv  # rules + trained ML model
    python run_classifier.py --limit 1000         # quick test run
"""

import argparse
import json
from collections import Counter
from pathlib import Path

from data_loader import DATA_DIR, load_records
from run_classifier import (
    IRRELEVANT, DECISION, LOCATION, INDIRECT,
    classify, rule_classify, train,
)

OUT_DIR = DATA_DIR / "classified"
KEEP = (DECISION, LOCATION, INDIRECT)  # classes that stay in the pool


def predict(text, model):
    """Use the full hybrid if a model exists, otherwise rules only."""
    if model is not None:
        return classify(text, model)
    label = rule_classify(text)
    return (label or IRRELEVANT), 1.0, "rule"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--golden", help="labeled CSV (text,label) to train the ML layer")
    ap.add_argument("--platforms", nargs="+", default=["tumblr", "twitter"])
    ap.add_argument("--raw", action="store_true", help="read the *_raw files")
    ap.add_argument("--limit", type=int, help="max records per platform")
    args = ap.parse_args()

    model = train(args.golden) if args.golden else None
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # One output file per class, written as we stream (handles big files)
    handles = {lbl: open(OUT_DIR / f"{lbl}.jsonl", "w", encoding="utf-8")
               for lbl in (IRRELEVANT, *KEEP)}
    counts = Counter()

    try:
        for rec in load_records(args.platforms, raw=args.raw, limit=args.limit):
            label, conf, src = predict(rec.text, model)
            counts[(rec.platform, label)] += 1
            handles[label].write(json.dumps({
                "id": rec.id,
                "platform": rec.platform,
                "label": label,
                "confidence": round(conf, 3),
                "decided_by": src,
                "created_at": rec.created_at,
                "text": rec.text,
            }, ensure_ascii=False) + "\n")
    finally:
        for h in handles.values():
            h.close()

    print("\nplatform / class counts")
    for (platform, label), n in sorted(counts.items()):
        print(f"  {platform:<8} {label:<18} {n}")
    kept = sum(n for (_, lbl), n in counts.items() if lbl in KEEP)
    print(f"\nkept in pool: {kept} | outputs in {OUT_DIR}")


if __name__ == "__main__":
    main()