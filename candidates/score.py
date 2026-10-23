#!/usr/bin/env python3
"""Generate an evidence-only report. Missing, failed and historical runs stay distinct."""
import json
import math
from pathlib import Path
import statistics

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
AGENTS = {"copilot", "opencode", "claude", "codex", "qwen", "aider"}


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def speed_tier(rate):
    if rate is None:
        return "unmeasured"
    return "Fast" if rate >= 100 else "Balanced" if rate >= 50 else "Deep"


def interval(k, n):
    if not n:
        return "n/a"
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return f"{100 * (c - h):.0f}-{100 * (c + h):.0f}%"


def human_rows(rows):
    expected = {f"HumanEval/{i}" for i in range(164)}
    seen = [row["task_id"] for row in rows]
    valid = len(seen) == len(set(seen)) and set(seen) == expected
    passed = sum(row["passed"] is True for row in rows)
    errors = sum(row["finish"] == "error" for row in rows)
    return {"complete": valid and not errors, "passed": passed, "total": len(rows),
            "errors": errors, "truncated": sum(row["finish"] == "length" for row in rows),
            "percent": 100 * passed / len(rows) if rows else 0,
            "ci": interval(passed, len(rows)),
            "median_secs": statistics.median(row["secs"] for row in rows) if rows else None}


def categorize(entry, data):
    """Qualification is about this harness, not a claim of general intelligence."""
    gate = data.get("gate")
    if not data and entry.get("optional"):
        return [], "Opt-in (not run)", "Experimental" if entry.get("experimental") else "Optional candidate"
    if gate and not gate["passed"]:
        return [], "Reject (chat/tool integration)", gate.get("error", "")
    if data.get("blocked"):
        return [], "Blocked", data["blocked"].get("diagnosis", data["blocked"]["error"])
    required = ("gate", "bench", "humaneval", "smoke", "fixtures", "long", "memory")
    if any(not data.get(key) for key in required):
        return [], "Pending", "Full pipeline not completed"
    human = data["humaneval"]
    if not human["complete"]:
        return [], "Incomplete", "HumanEval missing tasks, duplicate IDs or request errors"
    smoke = data["smoke"]
    fixtures = data["fixtures"]
    if (len(smoke["results"]) != 6 or {row["agent"] for row in smoke["results"]} != AGENTS
            or len(fixtures["results"]) != 6
            or {(row["agent"], row["fixture"]) for row in fixtures["results"]} != {
                (agent, kind) for agent in ("opencode", "copilot") for kind in ("bugfix", "multi", "repair")}):
        return [], "Incomplete", "Missing expected agent/fixture combinations"
    if not data["memory"]["qualified"]:
        return [], "Reject (memory qualification)", "Swap growth, elevated pressure or missing memory samples"
    labels = []
    if (speed_tier(data["bench"]["decode_tps"]) == "Fast" and human["percent"] >= 90
            and human["median_secs"] <= 5 and not entry["thinking"]):
        labels.append("quick edits")
    agentic = sum(row["passed"] for row in smoke["results"]) >= 5 and all(row["passed"] for row in fixtures["results"])
    if agentic:
        labels.append("agentic coding")
    if human["percent"] >= 96 and all(row["passed"] for row in fixtures["results"] if row["fixture"] == "repair"):
        labels.append("debugging")
    runs = data["long"]["runs"]
    if (len(runs) == 2 and all(row["recall"] == 3 and row["finish"] == "stop"
                              and row["prompt_tokens"] >= 100000 for row in runs)):
        labels.append("100k recall")
    if not agentic:
        failed_agents = [row["agent"] + (" (timeout)" if row.get("timeout") else "")
                         for row in smoke["results"] if not row["passed"]]
        failed_fixtures = [row["fixture"] + "/" + row["agent"]
                           + (" (timeout)" if row.get("timeout") else "")
                           for row in fixtures["results"] if not row["passed"]]
        reason = ("Needs 5/6 smoke passes and all 6 fixture passes. "
                  f"Failed smoke: {', '.join(failed_agents) or 'none'}; "
                  f"failed fixtures: {', '.join(failed_fixtures) or 'none'}")
        return labels, "Reject (agent qualification)", reason
    return labels, "Keep as alternate", "Promotion requires a matched incumbent run; no automatic profile changes"


def evidence(directory):
    result = {}
    for key in ("gate", "bench", "smoke", "fixtures", "long", "memory", "blocked"):
        path = directory / (key + (".summary.json" if key == "bench" else ".json"))
        value = read(path)
        if value is not None:
            result[key] = value
    path = directory / "humaneval.jsonl"
    if path.exists():
        result["humaneval"] = human_rows([json.loads(line) for line in path.read_text().splitlines()])
    return result


def cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def render(entries):
    lines = [
        "# Local candidate model report", "",
        "Measured on this machine only. Blank results mean **not measured**, not zero.",
        "Weights are decimal GB; RAM also includes KV cache, runtime and macOS. Full-run logs",
        "live in `candidates/results/<id>/`; pinned sources and licenses are in `manifest.json`.", "",
        "| Candidate | Wave | Weights GB | Context tokens | Gate | Decode tok/s | Speed tier | HumanEval (95% CI) | Median task s | Trunc/errors | Smoke | Fixtures | Cold/warm recall | Peak RSS GiB | Swap growth MiB | Decision |",
        "|---|---:|---:|---:|---|---:|---|---|---:|---|---|---|---|---:|---:|---|",
    ]
    details = []
    for name, entry in entries.items():
        directory = HERE / "results" / name
        data = evidence(directory)
        run = read(directory / "run.json")
        context = run["profile"]["context"] if run else entry.get("context", 131072)
        labels, decision, why = categorize(entry, data)
        gate = data.get("gate")
        rate = data.get("bench", {}).get("decode_tps")
        human = data.get("humaneval")
        htext = (f"{human['passed']}/{human['total']} = {human['percent']:.1f}% ({human['ci']})"
                 + ("" if human["complete"] else " partial/errors")) if human else "-"
        counts = [f"{data[k]['passed']}/{data[k]['total']}" if k in data else "-" for k in ("smoke", "fixtures")]
        long = data.get("long", {}).get("runs", [])
        recall = ", ".join(f"{r['recall']}/3 @ {r['prompt_tokens']:,}" for r in long) or "-"
        memory = data.get("memory")
        values = [name, entry["wave"], f"{entry['bytes']/1e9:.1f}", context,
                  "PASS" if gate and gate["passed"] else "FAIL" if gate else "-",
                  f"{rate:.1f}" if rate is not None else "-", speed_tier(rate), htext,
                  f"{human['median_secs']:.1f}" if human and human["median_secs"] is not None else "-",
                  f"{human['truncated']}/{human['errors']}" if human else "-",
                  *counts, recall,
                  f"{memory['peak']['rss_mib']/1024:.1f}" if memory else "-",
                  f"{memory['swap_growth_mib']:.1f}" if memory else "-", decision]
        lines.append("| " + " | ".join(map(cell, values)) + " |")
        details.append(f"- **{name}** ({entry['model']}, {entry['quant']}): "
                       f"{', '.join(labels) if labels else 'no qualified use-case label yet'}. {cell(why)}.")
    lines += ["", "## Evidence and interpretation", "",
              "Fast >=100 tok/s; Balanced >=50 and <100; Deep <50. Decode is three-repeat",
              "`llama-bench` tg128 at empty context, not end-to-end agent speed.", "",
              "HumanEval is one sample per problem and often saturated. Truncations and request",
              "errors remain visible; no reasoning-quality or fill-in-the-middle autocomplete",
              "claim is inferred from it. Debugging labels only reflect these small repair fixtures.",
              "100k recall is a needle test, not a demonstration of codebase understanding.", "",
              "Agentic coding requires >=5/6 smoke passes and all six OpenCode/Copilot fixtures.",
              "Quick edits additionally require >=90% HumanEval, <=5s median per task and no",
              "thinking mode. Memory qualification requires normal pressure and no swap growth",
              "throughout measured stages. Blocked infrastructure runs are not model rejections.", "",
              *details, "", "## Historical incumbents (not matched candidate runs)", "",
              "Existing scores below are preserved for reference. Their original speed tests,",
              "agent settings and memory monitoring differ; do not infer a winner from tiny",
              "score differences or compare different quantizers as a pure bits-per-weight effect.", "",
              "| Profile | HumanEval | 95% CI | Median seconds/problem |",
              "|---|---|---|---:|"]
    # lite/medium were replaced by cand-nemo35-light/cand-gemma4-26b; keep the previous models here.
    for name, rel in (("fast", "fast.jsonl"), ("lite (retired Qwen3-Coder-30B)", "archive/lite-qwen3-coder-30b.jsonl"),
                      ("medium (retired Qwen3-Coder-Next)", "archive/medium-qwen3-coder-next.jsonl"),
                      ("coder", "coder.jsonl"), ("smart", "smart.jsonl")):
        path = ROOT / "eval/results" / rel
        if path.exists():
            value = human_rows([json.loads(line) for line in path.read_text().splitlines()])
            lines.append(f"| {name} | {value['passed']}/{value['total']} | {value['ci']} | {value['median_secs']:.1f} |")
    return "\n".join(lines) + "\n"


def main():
    entries = json.loads((HERE / "manifest.json").read_text())
    report = HERE / "REPORT.md"
    report.write_text(render(entries))
    print(f"Wrote {report.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
