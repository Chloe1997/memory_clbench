"""Run the CL-Bench-lite baseline.

  # real small model behind an OpenAI-compatible server (vLLM / Ollama / llama.cpp)
  python run.py --model Qwen/Qwen3-4B-Instruct-2507 --base-url http://localhost:8000/v1

  # plumbing checks, no LLM needed
  python run.py --model oracle   # answers gold -> sanity-check env + scorer
  python run.py --model test     # Pydantic AI TestModel -> exercises tool wiring
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

from clbench_lite.agent import BaselineHarness
from clbench_lite.env import build_episode
from clbench_lite.score import judge, score
from clbench_lite.tools import MemoryStore, SqlTool
from clbench_lite.viz import write_report

# normal(pre), inject, wrong_fb, destruct, scary, normal(post), wrong_fb(post), destruct(post)
QUICK_SET = [0, 4, 6, 8, 11, 15, 17, 19]


def make_model(name: str, base_url: str, api_key: str):
    if name == "test":
        from pydantic_ai.models.test import TestModel
        return TestModel()
    from pydantic_ai.models.openai import OpenAIChatModel
    from pydantic_ai.providers.openai import OpenAIProvider
    return OpenAIChatModel(name, provider=OpenAIProvider(base_url=base_url, api_key=api_key))


def run_one(args, use_memory: bool, out: Path) -> tuple[list[dict], SqlTool, MemoryStore | None]:
    if out.exists():
        shutil.rmtree(out)
    ep = build_episode(out / "env", seed=args.seed)
    sql = SqlTool(out / "env" / "working.db")
    mem = MemoryStore(out / "memory") if use_memory else None
    results = []
    harness = None
    if args.model != "oracle":
        harness = BaselineHarness(make_model(args.model, args.base_url, args.api_key),
                                  sql, mem, out / "transcripts", args.request_limit)
    tag = "mem" if use_memory else "nomem"
    questions = [q for q in ep.questions if args.qset is None or q.idx in args.qset]
    for n, q in enumerate(questions, 1):
        ep.fresh_working_db(q)
        print(f"[{tag}] ({n}/{len(questions)}) q{q.idx:02d} running...", end="\r", flush=True)
        t0 = time.time()
        if harness is None:  # oracle
            r = {"idx": q.idx, "phase": q.phase, "kind": q.kind, "question": q.text,
                 "answer": q.gold, "raw": f"ANSWER: {q.gold}", "gold": q.gold, "error": None}
        else:
            r = harness.step(q, judge)
        r["seconds"] = round(time.time() - t0, 1)
        r["feedback_answer"] = q.feedback_answer
        r["gold_sql"] = q.gold_sql
        r["memory_after"] = mem.snapshot() if mem else None
        r["violations"] = [v for v in sql.violations if v["q"] == q.idx]
        ok = judge(r["answer"], r["gold"])
        r["ok"] = ok
        print(f"[{tag}] ({n}/{len(questions)}) q{q.idx:02d} {q.phase:4s} {q.kind:8s} "
              f"{'OK ' if ok else 'BAD'} ans={r['answer'][:40]!r:>12} gold={q.gold}  {r['seconds']}s"
              + (f"  err={r['error'][:80]}" if r["error"] else ""))
        results.append(r)
    with open(out / "results.jsonl", "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return results, sql, mem


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="oracle")
    ap.add_argument("--base-url", default="http://localhost:8000/v1")
    ap.add_argument("--api-key", default="EMPTY")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--request-limit", type=int, default=15)
    ap.add_argument("--out", default="runs/baseline")
    ap.add_argument("--skip-nomem", action="store_true")
    ap.add_argument("--questions", default=None,
                    help="comma-separated 0-based question indices, e.g. 0,4,15")
    ap.add_argument("--quick", action="store_true",
                    help=f"run only {QUICK_SET} (one of each probe + drift)")
    ap.add_argument("--no-viz", action="store_true", help="don't write report.html")
    args = ap.parse_args()
    if args.questions:
        args.qset = {int(x) for x in args.questions.split(",") if x.strip()}
    elif args.quick:
        args.qset = set(QUICK_SET)
    else:
        args.qset = None

    out = Path(args.out)
    mem_res, sql, mem = run_one(args, True, out / "memory_run")
    nomem_res = None if args.skip_nomem else run_one(args, False, out / "nomem_run")[0]
    report = score(mem_res, nomem_res, sql.violations, mem.dump() if mem else "")
    (out / "score.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if not args.no_viz:
        html = write_report(out, report, mem_res, nomem_res, vars(args))
        print(f"report: {html.resolve()}")


if __name__ == "__main__":
    main()
