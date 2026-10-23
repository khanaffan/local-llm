#!/usr/bin/env python3
"""Summarize eval/results/*.jsonl into a scorecard (stdout + eval/SCORECARD.md)."""
import json, math, os, statistics as st

ROOT = os.path.dirname(os.path.abspath(__file__))
# (tier label, model, results file relative to eval/results)
MODELS = [("fast", "gpt-oss-20b", "fast.jsonl"),
          ("lite", "Nemotron-3.5-Lightning-30B-A3B Q8_0", "lite.jsonl"),
          ("medium", "Gemma-4-26B-A4B UD-Q6_K", "medium.jsonl"),
          ("coder", "Qwen3.8-Flash-Next UD-IQ3_XXS", "coder.jsonl"),
          ("smart", "gpt-oss-120b", "smart.jsonl"),
          ("lite (retired)", "Qwen3-Coder-30B-A3B Q6_K", "archive/lite-qwen3-coder-30b.jsonl"),
          ("medium (retired)", "Qwen3-Coder-Next Q6_K", "archive/medium-qwen3-coder-next.jsonl")]
NOTES = ("lite and medium were measured in the candidate bake-off (`candidates/results/`). "
         "Some of their requests stalled for 15-30 min while producing few tokens (unexplained "
         "host stalls), which lowers their end-to-end tok/s and inflates total minutes; per-request "
         "decode was otherwise ~95 (lite) and ~87 (medium) tok/s. Truncated = hit the 8192-token cap. "
         "Retired rows are the previous lite/medium models, kept for reference.")


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


rows = []
for prof, name, rel in MODELS:
    path = os.path.join(ROOT, "results", rel)
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
    "card sampling settings, 8192 max tokens, hidden unit tests run in a sandbox.\n\n" + out + "\n\n"
    + NOTES + "\n")
