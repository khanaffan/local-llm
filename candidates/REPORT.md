# Local candidate model report

Measured on this machine only. Blank results mean **not measured**, not zero.
Weights are decimal GB; RAM also includes KV cache, runtime and macOS. Full-run logs
live in `candidates/results/<id>/`; pinned sources and licenses are in `manifest.json`.

| Candidate | Wave | Weights GB | Context tokens | Gate | Decode tok/s | Speed tier | HumanEval (95% CI) | Median task s | Trunc/errors | Smoke | Fixtures | Cold/warm recall | Peak RSS GiB | Swap growth MiB | Decision |
|---|---:|---:|---:|---|---:|---|---|---:|---|---|---|---|---:|---:|---|
| cand-qwen36-35b | 1 | 29.3 | 131072 | PASS | 103.2 | Fast | 154/164 = 93.9% (89-97%) | 23.9 | 6/0 | 6/6 | 5/6 | 3/3 @ 100,125, 3/3 @ 100,125 | 39.9 | 0.0 | Reject (agent qualification) |
| cand-qwen38-27b | 1 | 22.0 | 131072 | PASS | 22.7 | Deep | 163/164 = 99.4% (97-100%) | 25.6 | 0/0 | 5/6 | 6/6 | 3/3 @ 100,125, 3/3 @ 100,125 | 39.4 | 0.0 | Keep as alternate |
| cand-gemma4-26b | 1 | 23.2 | 131072 | PASS | 98.8 | Balanced | 160/164 = 97.6% (94-99%) | 22.1 | 4/0 | 5/6 | 6/6 | 3/3 @ 100,126, 3/3 @ 100,126 | 37.6 | 0.0 | Keep as alternate |
| cand-glm47-flash | 1 | 24.7 | 131072 | PASS | 92.6 | Balanced | 150/164 = 91.5% (86-95%) | 20.1 | 3/0 | 5/6 | 6/6 | 3/3 @ 100,125, 3/3 @ 100,125 | 40.1 | 0.0 | Keep as alternate |
| cand-nemo35-light | 1 | 33.6 | 131072 | PASS | 106.1 | Fast | 149/164 = 90.9% (85-94%) | 17.6 | 10/0 | 6/6 | 6/6 | 3/3 @ 100,128, 3/3 @ 100,128 | 41.5 | 0.0 | Keep as alternate |
| cand-devstral-s2 | 1 | 19.3 | 131072 | PASS | 26.9 | Deep | 143/164 = 87.2% (81-91%) | 6.5 | 0/0 | 3/6 | 6/6 | 3/3 @ 100,125, 3/3 @ 100,125 | 45.8 | 0.0 | Reject (agent qualification) |
| cand-ds-coder-lite | 1 | 14.1 | 131072 | FAIL | - | unmeasured | - | - | - | - | - | - | 47.0 | 0.0 | Reject (chat/tool integration) |
| cand-ds-r1-32b | 1 | 26.9 | 131072 | FAIL | - | unmeasured | - | - | - | - | - | - | 57.3 | 0.0 | Reject (chat/tool integration) |
| cand-nemo35-super | 2 | 71.9 | 131072 | PASS | 36.8 | Deep | 161/164 = 98.2% (95-99%) | 24.9 | 3/0 | 6/6 | 6/6 | 3/3 @ 100,128, 3/3 @ 100,128 | 78.8 | 0.0 | Keep as alternate |
| cand-devstral-2 | 2 | 74.9 | 32768 | PASS | - | unmeasured | - | - | - | - | - | - | - | - | Pending |
| cand-qwen38fn-gsq | 2 | 83.6 | 131072 | PASS | 47.0 | Deep | 163/164 = 99.4% (97-100%) | 11.3 | 0/0 | 6/6 | 6/6 | 3/3 @ 100,125, 3/3 @ 100,125 | 71.0 | 0.0 | Keep as alternate |
| cand-glm45-air | 2 | 67.7 | 131072 | - | - | unmeasured | - | - | - | - | - | - | - | - | Opt-in (not run) |
| cand-ds-v4-flash | 3 | 90.9 | 32768 | - | - | unmeasured | - | - | - | - | - | - | - | - | Opt-in (not run) |

## Evidence and interpretation

Fast >=100 tok/s; Balanced >=50 and <100; Deep <50. Decode is three-repeat
`llama-bench` tg128 at empty context, not end-to-end agent speed.

HumanEval is one sample per problem and often saturated. Truncations and request
errors remain visible; no reasoning-quality or fill-in-the-middle autocomplete
claim is inferred from it. Debugging labels only reflect these small repair fixtures.
100k recall is a needle test, not a demonstration of codebase understanding.

Agentic coding requires >=5/6 smoke passes and all six OpenCode/Copilot fixtures.
Quick edits additionally require >=90% HumanEval, <=5s median per task and no
thinking mode. Memory qualification requires normal pressure and no swap growth
throughout measured stages. Blocked infrastructure runs are not model rejections.

- **cand-qwen36-35b** (Qwen3.6-35B-A3B, UD-Q6_K): 100k recall. Needs 5/6 smoke passes and all 6 fixture passes. Failed smoke: none; failed fixtures: repair/copilot (timeout).
- **cand-qwen38-27b** (Qwen3.8-27B, UD-Q6_K): agentic coding, debugging, 100k recall. Promotion requires a matched incumbent run; no automatic profile changes.
- **cand-gemma4-26b** (Gemma-4-26B-A4B-it, UD-Q6_K): agentic coding, debugging, 100k recall. Promotion requires a matched incumbent run; no automatic profile changes.
- **cand-glm47-flash** (GLM-4.7-Flash, Q6_K): agentic coding, 100k recall. Promotion requires a matched incumbent run; no automatic profile changes.
- **cand-nemo35-light** (Nemotron-3.5-Lightning-30B-A3B, Q8_0): agentic coding, 100k recall. Promotion requires a matched incumbent run; no automatic profile changes.
- **cand-devstral-s2** (Devstral-Small-2-24B-Instruct-2512, Q6_K): 100k recall. Needs 5/6 smoke passes and all 6 fixture passes. Failed smoke: claude, codex, qwen; failed fixtures: none.
- **cand-ds-coder-lite** (DeepSeek-Coder-V2-Lite-Instruct, Q6_K): no qualified use-case label yet. incomplete streaming response or expected one tool call.
- **cand-ds-r1-32b** (DeepSeek-R1-Distill-Qwen-32B, Q6_K): no qualified use-case label yet. incomplete streaming response or expected one tool call.
- **cand-nemo35-super** (Nemotron-3.5-Super-VL-120B-A12B, Q4_0): agentic coding, debugging, 100k recall. Promotion requires a matched incumbent run; no automatic profile changes.
- **cand-devstral-2** (Devstral-2-123B-Instruct-2512, Q4_K_M): no qualified use-case label yet. Full pipeline not completed.
- **cand-qwen38fn-gsq** (Qwen3.8-Flash-Next (GSQ-RCO), IQ3_S): agentic coding, debugging, 100k recall. Promotion requires a matched incumbent run; no automatic profile changes.
- **cand-glm45-air** (GLM-4.5-Air, UD-Q4_K_XL): no qualified use-case label yet. Optional candidate.
- **cand-ds-v4-flash** (DeepSeek-V4-Flash-0731, UD-IQ2_XXS): no qualified use-case label yet. Experimental.

## Historical incumbents (not matched candidate runs)

Existing scores below are preserved for reference. Their original speed tests,
agent settings and memory monitoring differ; do not infer a winner from tiny
score differences or compare different quantizers as a pure bits-per-weight effect.

| Profile | HumanEval | 95% CI | Median seconds/problem |
|---|---|---|---:|
| fast | 159/164 | 93-99% | 3.6 |
| lite (retired Qwen3-Coder-30B) | 152/164 | 88-96% | 1.5 |
| medium (retired Qwen3-Coder-Next) | 154/164 | 89-97% | 2.4 |
| coder | 162/164 | 96-100% | 10.7 |
| smart | 161/164 | 95-99% | 4.2 |
