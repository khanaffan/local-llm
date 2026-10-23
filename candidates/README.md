# Local candidate bake-off

Candidates are experiments, not new production tiers. `profiles/*.env`, the root
manifest, and existing model files are left intact. The shared resolver accepts
`cand-*` IDs, so the same local agent wrappers work with candidates.

## Run

```bash
python3 candidates/run.py --list
bash candidates/run_candidate.sh cand-devstral-s2
bash candidates/run_candidate.sh --wave 1
bash candidates/run_candidate.sh --wave 2
python3 candidates/score.py
```

The runner downloads and verifies pinned GGUF files, then measures candidates
**sequentially**. It takes an exclusive candidate-run lock, refuses to interrupt
an active server request, stops each candidate on exit, and restores a previously
resident profile. Do not run other model clients or GPU-heavy jobs during a bake-off.
Weights are preserved; nothing is automatically deleted or promoted.

`--include-optional` adds GLM-4.5-Air. DeepSeek-V4-Flash is an **oversized, very-low-bit
experiment**, excluded by default. Explicitly request
`cand-ds-v4-flash --experimental` to try it. The runner never changes macOS GPU
limits, installs dependencies, falls back to a hosted API, or reduces context
silently. Out-of-memory/runtime failures are reported as blocked, not as low quality.

**Devstral 2 on this 128 GB Mac:** the original 131072-context run exhausted Metal
memory. It is preserved under `results/archive/`. The retry explicitly uses
`CTX=32768` in `candidates/profiles/cand-devstral-2.local.env` (Git-ignored).
To reproduce it on this machine, create that override before running. The report
lists effective context per run; this shorter-context experiment cannot earn a
100k-recall label. It uses the same weights, f16 KV and 8192 output-token budget.

You can run a subset with `--stages gate,bench` and resume later with the full
command. `--no-download` requires verified size/hash stamps already on disk.
Completed stage files are reused only when the run fingerprint matches (pinned
weights, profile plus local override, template, runner/eval/fixture/wrapper sources,
agent package lock and llama.cpp build). To rerun changed inputs, move the old
`candidates/results/<id>` directory to an archive first; the runner will not overwrite
incompatible evidence. A timeout is retried on the next invocation; partial
HumanEval results resume by task ID.

## Measurements and results

Each `candidates/results/<id>/` contains:

| Artifact | Meaning |
|---|---|
| `run.json` | Pinned model, effective settings, source hashes and runtime fingerprint |
| `gate.json`, `gate.responses.json` | Chat, streaming function arguments and tool-result recovery |
| `bench.raw.json`, `bench.md`, `bench.summary.json` | Three repetitions of pp512/8192/30000 and tg128 |
| `humaneval.jsonl` | One attempt at each of 164 tasks, 8192 output-token cap, sandboxed tests |
| `smoke.json`, `smoke-*.log` | Same small fix through all six local coding agents |
| `fixtures.json`, `fixture-*.log` | Bug-fix, multi-file and LRU repair through OpenCode and Copilot |
| `long.json` | Token-calibrated ~100k prompt, actual tokens, cold/warm recall and server timings |
| `memory.json` | Sampled peak RSS, swap baseline/growth, pressure, monitoring errors |
| `summary.json`, `blocked.json` | Completed stages and explicit infrastructure failures |

All requests use `127.0.0.1:8080`. Benchmarking stops the server first, avoiding two
resident copies of a model. Long-context testing restarts it for a genuinely cold
first prompt. Context is 131072 by default, with f16 KV and full GPU offload; the
stretch DeepSeek profile uses 32768. A smaller context is reported honestly and
cannot qualify for the 100k label. For an explicit 256k experiment, set a candidate
local override (see below) and adjust the test target in a separate, archived run;
the default suite deliberately measures one common 100k workload.

Agent fixtures are copied to scratch and receive deterministic bugs. The runner
asserts that they fail *before* the agent runs, then requires a successful agent
exit, passing tests, and byte-identical test files. Original fixtures are never edited.
Agents and their test subprocesses run under macOS `sandbox-exec`, with writes
confined to scratch and outbound networking limited to the local inference port.
Homes, caches and generated agent settings are isolated. Timeouts terminate child
process groups. Missing/broken agent tooling is visible in logs; no install or
cloud fallback is attempted.

`REPORT.md` separates unmeasured, blocked, integration-rejected and qualified
models. Speed thresholds: Fast >=100 tok/s; Balanced >=50; Deep <50. Agentic coding
requires >=5/6 agent smoke passes and all six fixtures. Memory qualification requires
normal pressure and no swap growth. HumanEval request failures, missing/duplicate
tasks, and incomplete agent matrices cannot earn a recommendation.

Quick-edit labels are not autocomplete/FIM measurements; repair labels are not a
general reasoning benchmark. Needle recall is not long-codebase comprehension.
Historical incumbent HumanEval scores are included **as reference only**, not as
matched head-to-head runs. No automatic "winner" is declared from a one-problem
difference. GSQ-RCO versus Unsloth changes quantization method as well as effective
precision, so it does not isolate the effect of bits per weight.

## Candidate selection and provenance

`catalog.json` lists the chosen models, quantization, sampling and wave.
`manifest.json` pins every shard's revision, size and SHA-256. These are fetched
explicitly, never refreshed as a side effect of a run:

```bash
python3 candidates/pin.py cand-devstral-s2  # review changed pins/profiles before running
```

Pinning rejects missing hashes, ambiguous files, incomplete shard sets, duplicate
quants and non-experimental weights above 90 decimal GB. Projectors and speculative
drafts are not mistaken for main-model weights. Profiles use model-card sampling:
Qwen3.6's precise-coding mode; Qwen3.8 medium reasoning effort to match the existing
`coder` budget; GLM's SWE settings; Gemma's recommended defaults; Devstral's 0.15
temperature. For newer Nemotron releases, sampling is an explicit experimental
setting, not a claim to reproduce their vendor benchmark.

Licenses are recorded from the pinned publisher metadata; read the upstream license
before redistribution/commercial use. Text-only evaluation does not qualify vision,
audio, million-token context or speculative decoding.

Optional tuning in `candidates/profiles/<id>.local.env` is ignored by Git and included
in the run fingerprint, e.g. `CTX=65536`. Model filename and alias must still match
the pinned manifest. Template overrides must be explicit and included in the fingerprint.

Families screened out of this default bake-off: full GLM-5.3/MiniMax-M3/Kimi/Ling and
DeepSeek-V4.1 exceed the weight budget at useful precision; MiniMax-H3 is video, not
text; Inkling is not supported by the installed llama.cpp build. This is a shortlist,
not a claim that no other release or aggressively quantized variant could fit.

## Validate the harness without downloads

```bash
python3 -m unittest discover -s candidates -p 'test_*.py' -v
bash -n profile.sh llm.sh download.sh bin/_common.sh candidates/run_candidate.sh
```
