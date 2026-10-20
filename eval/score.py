#!/usr/bin/env python3
"""Summarize eval/results/*.jsonl into a scorecard (stdout + eval/SCORECARD.md)."""
import json, math, os, statistics as st

ROOT = os.path.dirname(os.path.abspath(__file__))
MODELS = {"fast": "gpt-oss-20b", "medium": "Qwen3-Coder-30B-A3B", "smart": "gpt-oss-120b"}


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


rows = []
for prof, name in MODELS.items():
    path = os.path.join(ROOT, "results", f"{prof}.jsonl")
    if not os.path.exists(path):
        continue
    rs = [json.loads(l) for l in open(path)]
    n, k = len(rs), sum(r["passed"] for r in rs)
    lo, hi = wilson(k, n)
    secs = [r["secs"] for r in rs if r["secs"]]
    toks = sum(r["completion_tokens"] for r in rs)
    rows.append((prof, name, k, n, lo, hi, st.median(secs), toks / n, toks / sum(secs), sum(secs) / 60,
                 sum(r["finish"] != "stop" for r in rs)))

lines = ["| Tier | Model | HumanEval pass@1 | 95% CI | Median s/problem | Avg tokens | End-to-end tok/s | Total min | Truncated/errors |",
         "|---|---|---|---|---|---|---|---|---|"]
for prof, name, k, n, lo, hi, med, avg, tps, mins, bad in rows:
    lines.append(f"| {prof} | {name} | {k}/{n} = {100*k/n:.1f}% | {100*lo:.0f}–{100*hi:.0f}% | {med:.1f} | {avg:.0f} | {tps:.0f} | {mins:.1f} | {bad} |")
out = "\n".join(lines)
print(out)
open(os.path.join(ROOT, "SCORECARD.md"), "w").write(
    "# Local LLM scorecard\n\nHumanEval (164 problems), pass@1, one sample per problem at each model's "
    "card sampling settings, 8192 max tokens, hidden unit tests run in a sandbox.\n\n" + out + "\n")
