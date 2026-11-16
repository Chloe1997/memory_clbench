"""Download a subset of tencent/CL-bench (https://huggingface.co/datasets/tencent/CL-bench).

Streams CL-bench.jsonl line by line and stops as soon as enough rows are
collected, so you don't need the full 90 MB file. Standard library only.

  python download_clbench.py                       # first 20 tasks
  python download_clbench.py -n 50 --category "Rule System Application"
  python download_clbench.py -n 30 --per-category 5 --max-chars 60000
  python download_clbench.py --list-categories -n 200   # peek at categories

Row format: {"messages": [{role, content}, ...], "rubrics": [str, ...],
             "metadata": {task_id, context_id, context_category, sub_category}}

NOTE: CL-bench is under an evaluation-only license (no training / fine-tuning /
any parameter updates). Keep the data out of git.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from collections import Counter
from pathlib import Path

URL = "https://huggingface.co/datasets/tencent/CL-bench/resolve/main/CL-bench.jsonl"


def stream_rows(url: str):
    headers = {"User-Agent": "clbench-subset-downloader/1.0"}
    if os.environ.get("HF_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['HF_TOKEN']}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=60) as resp:
        for raw in resp:
            line = raw.decode("utf-8").strip()
            if line:
                yield json.loads(line)


def row_chars(row: dict) -> int:
    return sum(len(m.get("content") or "") for m in row.get("messages", []))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-n", type=int, default=20, help="number of tasks to keep (default 20)")
    ap.add_argument("--category", help="keep only this context_category (exact match)")
    ap.add_argument("--sub-category", help="keep only this sub_category (exact match)")
    ap.add_argument("--per-category", type=int, default=0,
                    help="cap tasks per context_category (0 = no cap) for a balanced sample")
    ap.add_argument("--max-chars", type=int, default=0,
                    help="skip tasks whose total message length exceeds this (small models have short context)")
    ap.add_argument("--out", default="data/clbench_subset.jsonl")
    ap.add_argument("--list-categories", action="store_true",
                    help="just count categories over the first -n rows, don't save")
    args = ap.parse_args()

    if args.list_categories:
        cats = Counter()
        for i, row in enumerate(stream_rows(URL)):
            if i >= args.n:
                break
            md = row.get("metadata", {})
            cats[(md.get("context_category"), md.get("sub_category"))] += 1
        for (c, s), k in sorted(cats.items()):
            print(f"{k:4d}  {c} / {s}")
        return

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    kept, seen, per_cat = [], 0, Counter()
    for row in stream_rows(URL):
        seen += 1
        md = row.get("metadata", {})
        cat = md.get("context_category")
        if args.category and cat != args.category:
            continue
        if args.sub_category and md.get("sub_category") != args.sub_category:
            continue
        if args.per_category and per_cat[cat] >= args.per_category:
            continue
        if args.max_chars and row_chars(row) > args.max_chars:
            continue
        kept.append(row)
        per_cat[cat] += 1
        print(f"\rscanned {seen}, kept {len(kept)}/{args.n}", end="", flush=True, file=sys.stderr)
        if len(kept) >= args.n:
            break
    print(file=sys.stderr)

    with open(out, "w", encoding="utf-8") as f:
        for row in kept:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    chars = [row_chars(r) for r in kept]
    print(f"saved {len(kept)} tasks -> {out.resolve()}")
    if kept:
        print(f"context length (chars): min {min(chars)}, median {sorted(chars)[len(chars) // 2]}, max {max(chars)}"
              f"  (~{max(chars) // 4} tokens max)")
        print(f"rubrics per task: {sum(len(r.get('rubrics', [])) for r in kept) / len(kept):.1f} avg")
        for c, k in per_cat.most_common():
            print(f"  {k:3d}  {c}")


if __name__ == "__main__":
    main()
