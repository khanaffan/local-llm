# Local LLM benchmark report

**Snapshot: October 23, 2026, 14:21 EDT.**

This report records actual local measurements on the Mac below, not vendor benchmark
claims. It includes completed results, unsuccessful integrations, and an unfinished
smaller-context retry. **The bake-off is not yet fully complete.**

## 1. Executive summary

| Default candidate status | Count |
|---|---:|
| Full suite completed | 8 |
| Stopped at native tool-call compatibility gate | 2 |
| Devstral 2 smaller-context retry in progress | 1 |
| Not yet attempted | 0 |
| Total default candidates | 11 |
| Additional optional experiments, not run | 2 |

The eight completed models are Qwen3.6-35B-A3B, Qwen3.8-27B, Gemma 4 26B-A4B,
GLM-4.7-Flash, Nemotron Lightning, Devstral Small 2, Nemotron Super, and
Qwen3.8-Flash-Next GSQ-RCO.

Main observations:

- **Fastest empty-context generation:** Nemotron Lightning, **106.1 tokens/s**.
- **Promising speed/score balance:** Gemma 4, **98.8 tokens/s and 160/164 HumanEval**.
- **Highest observed HumanEval count:** Qwen3.8-27B and Qwen3.8-Flash-Next GSQ-RCO,
  both **163/164 (99.4%)**. GSQ-RCO also passed all six agents and all six fixtures.
- **Fully measured 4-bit option:** Nemotron Super Q4_0, **36.8 tokens/s,
  161/164 (98.2%)**, with all six agents and all six fixtures passing.
- **Devstral 2:** ran out of Metal GPU memory at 131072 context. Its explicitly
  reduced 32768-context retry passed the compatibility gate but has no final score
  in this snapshot.

These are observations from a small local evaluation, not proof of general model
superiority. Differences of one or a few HumanEval problems are within considerable
statistical uncertainty.

**Update (October 23, 2026, after this snapshot):** at the user's request, `lite` is now
Nemotron Lightning and `medium` is Gemma 4. `long` keeps Qwen3-Coder-Next (the previous
`medium`). This was an explicit decision without a matched incumbent re-run; see section 12.

## 2. Test machine and runtime

| Component | Configuration |
|---|---|
| Machine | Apple M5 Max Mac |
| CPU | 18 cores |
| GPU | 40 cores, Metal backend |
| Memory | 128 GB unified memory |
| OS | macOS 27.0.1 |
| Inference engine | llama.cpp 0.7.0, build 11669, commit `620d2225c` |
| Compiler | AppleClang 21.0.0.21000334, Darwin arm64 |
| GPU offload | All model layers |
| KV cache | f16 keys and values |
| Flash attention | Enabled |
| Server concurrency | One slot; one resident model at a time |
| Completed-candidate context allocation | 131072 tokens |
| Devstral 2 retry allocation | 32768 tokens |
| Benchmark CPU threads | 6 |
| Benchmark repetitions | 3 per test |
| Maximum answer length | 8192 tokens in HumanEval and the chat/tool gate |
| Transport | Authenticated local server on `127.0.0.1:8080` |
| Neural Engine | Not used; inference runs through Metal |

Power state, thermal state, and unrelated system activity were not comprehensively
controlled or logged. Treat the timings as observations on this setup, not
guarantees on another Mac or under different operating conditions.

## 3. Evaluation methodology

### Compatibility gate

Each candidate first loads and must:

1. Answer a simple chat request.
2. Produce a native streaming function call with the expected function, call ID,
   and JSON arguments.
3. Consume the tool result and produce a subsequent assistant answer.

Failure stops the remaining pipeline for that candidate. Therefore, an integration
rejection is **not** a zero coding score or a general reasoning-quality judgment.
In particular, the two DeepSeek models were not given HumanEval scores.

### Speed measurements

`llama-bench` measures:

- `pp512`: prompt processing for 512 tokens.
- `pp8192`: prompt processing for 8192 tokens.
- `pp30000`: prompt processing for 30000 tokens.
- `tg128`: generation of 128 tokens at empty context.

The reported generation rate is the mean of three `tg128` repetitions. The server
is stopped first so the benchmark does not load a second resident copy of the model.
These are throughput measurements, **not end-to-end coding-agent speed**.

### HumanEval

- All **164** Python problems, one sampled answer per problem: pass@1.
- Up to **8192 output tokens**, including the model's output/reasoning budget.
- Sampling settings are recorded in candidate profiles and run fingerprints.
- Generated completions run against tests in a macOS sandbox, with networking and
  writes outside the test scratch directory denied.
- Truncations remain visible and are not replaced with hand-picked successful answers.
- Transport errors are recorded separately; request-error retries do not retry
  ordinary wrong answers.

The intervals below are approximate **95% Wilson confidence intervals**. All eight
completed suites have 164 task records and **zero recorded request errors**.

### Agent compatibility and repair fixtures

The same small repair task is tried through six clients:
Copilot CLI, OpenCode, Claude Code, Codex, Qwen Code, and Aider.

Three fixture types are additionally tested through **both OpenCode and Copilot**:
arithmetic bug fix, multi-file currency/receipt repair, and LRU-cache repair.
That produces six fixture runs per model.

The original repository fixtures already contained fixes. The harness therefore
copies them to scratch, introduces deterministic bugs, and verifies an assertion
failure before starting the agent. A pass requires a successful agent exit, passing
tests, and byte-identical test files.

Agent homes, caches, and generated settings are isolated. The outer OS sandbox
restricts writes to scratch and outbound networking to the local inference port.
Agent attempts have a 600-second timeout.

### Long-context and memory tests

The long-context test hides three facts at approximately 10%, 50%, and 90% depth.
The rendered prompt is token-calibrated rather than estimated from character count.
It runs once after a server restart, then again with the same prefix cached.

Memory monitoring samples server RSS, swap usage, and macOS memory-pressure level.
Qualification requires normal pressure and **no swap growth during that run**.
Existing swap is a baseline, not automatically attributed to a new candidate.

## 4. Completed generation and coding results

All eight models below completed the full suite at **131072 allocated context**.
Rows are ordered by empty-context generation throughput, not by overall quality.

| Model | Quantization | Decode tok/s | HumanEval pass@1 | 95% CI | Median task s | Truncated |
|---|---|---:|---|---|---:|---:|
| Nemotron 3.5 Lightning 30B-A3B | Q8_0 | 106.1 | 149/164 = 90.9% | 85-94% | 17.55 | 10 |
| Qwen3.6-35B-A3B | UD-Q6_K | 103.2 | 154/164 = 93.9% | 89-97% | 23.91 | 6 |
| Gemma 4 26B-A4B | UD-Q6_K | 98.8 | 160/164 = 97.6% | 94-99% | 22.08 | 4 |
| GLM-4.7-Flash | Q6_K | 92.6 | 150/164 = 91.5% | 86-95% | 20.13 | 3 |
| Qwen3.8-Flash-Next GSQ-RCO | IQ3_S | 47.0 | 163/164 = 99.4% | 97-100% | 11.34 | 0 |
| Nemotron 3.5 Super 120B-A12B | Q4_0 | 36.8 | 161/164 = 98.2% | 95-99% | 24.86 | 3 |
| Devstral Small 2 24B | Q6_K | 26.9 | 143/164 = 87.2% | 81-91% | 6.55 | 0 |
| Qwen3.8-27B | UD-Q6_K | 22.7 | 163/164 = 99.4% | 97-100% | 25.64 | 0 |

Median task time is inference-request wall-clock latency, including generated
reasoning but **excluding test execution**. It is not a benchmark of a multi-turn
software engineering task. Devstral Small 2 illustrates that low decode throughput
can coexist with low per-problem latency; output length and reasoning budget matter.
A fast token generator can spend a long time reasoning before returning useful code.

## 5. Prompt-processing throughput

All values below are tokens/s from the same three-repeat benchmark configuration.

| Model | pp512 | pp8192 | pp30000 |
|---|---:|---:|---:|
| Nemotron Lightning | 2916.90 | 2797.04 | 2339.48 |
| Qwen3.6-35B-A3B | 3106.09 | 2771.46 | 2053.01 |
| Gemma 4 26B-A4B | 3511.88 | 3090.79 | 2311.57 |
| GLM-4.7-Flash | 2719.60 | 1548.10 | 642.31 |
| Qwen3.8-Flash-Next GSQ-RCO | 1133.80 | 928.47 | 770.34 |
| Nemotron Super | 918.33 | 845.49 | 783.70 |
| Devstral Small 2 | 973.25 | 738.24 | 558.38 |
| Qwen3.8-27B | 756.99 | 649.57 | 559.59 |

Prompt-processing speed generally declines as the prompt grows. Do not substitute
these short-prompt measurements for the separate cold 100k-request timings below.

## 6. Agent compatibility

`PASS` means the agent exited successfully, fixed the small task, and left its test
unchanged. A failed client integration is not necessarily a wrong coding answer.

| Model | Copilot | OpenCode | Claude Code | Codex | Qwen Code | Aider | Total |
|---|---|---|---|---|---|---|---:|
| Nemotron Lightning | PASS | PASS | PASS | PASS | PASS | PASS | 6/6 |
| Qwen3.6-35B-A3B | PASS | PASS | PASS | PASS | PASS | PASS | 6/6 |
| Gemma 4 26B-A4B | PASS | PASS | PASS | PASS | PASS | FAIL | 5/6 |
| GLM-4.7-Flash | PASS | PASS | PASS | PASS | FAIL | PASS | 5/6 |
| Qwen3.8-Flash-Next GSQ-RCO | PASS | PASS | PASS | PASS | PASS | PASS | 6/6 |
| Nemotron Super | PASS | PASS | PASS | PASS | PASS | PASS | 6/6 |
| Devstral Small 2 | PASS | PASS | FAIL | FAIL | FAIL | PASS | 3/6 |
| Qwen3.8-27B | PASS | PASS | FAIL | PASS | PASS | PASS | 5/6 |

Observed failures:

- **Gemma / Aider:** timed out.
- **GLM-4.7-Flash / Qwen Code:** timed out.
- **Qwen3.8-27B / Claude Code:** local HTTP 500, with the template error
  `System message must be at the beginning`.
- **Devstral Small 2 / Claude Code:** the template rejected an additional system role.
- **Devstral Small 2 / Qwen Code:** the template rejected the conversation's role
  alternation. Codex also failed with repeated request errors in this integration;
  this was a local-server test, not a hosted API comparison.

These results describe the tested GGUF templates and wrappers. They are not a claim
that model-specific adapter work could never make a failed integration function.

## 7. Repair fixtures

Each fixture column contains two attempts: one OpenCode and one Copilot run.

| Model | Arithmetic fix | Multi-file repair | LRU repair | Total |
|---|---:|---:|---:|---:|
| Nemotron Lightning | 2/2 | 2/2 | 2/2 | 6/6 |
| Qwen3.6-35B-A3B | 2/2 | 2/2 | 1/2 | 5/6 |
| Gemma 4 26B-A4B | 2/2 | 2/2 | 2/2 | 6/6 |
| GLM-4.7-Flash | 2/2 | 2/2 | 2/2 | 6/6 |
| Qwen3.8-Flash-Next GSQ-RCO | 2/2 | 2/2 | 2/2 | 6/6 |
| Nemotron Super | 2/2 | 2/2 | 2/2 | 6/6 |
| Devstral Small 2 | 2/2 | 2/2 | 2/2 | 6/6 |
| Qwen3.8-27B | 2/2 | 2/2 | 2/2 | 6/6 |

Qwen3.6's Copilot LRU attempt repeatedly invoked an inappropriate agent-reading
tool and hit the 600-second limit. Its other five fixture runs passed.

## 8. Weight size, memory, and long-context behavior

Weights are decimal GB; RSS is GiB. **RSS is not total system memory, total GPU
allocation, or a guarantee of how much RAM another machine needs.** Weights plus
KV cache, compute buffers, macOS, and other applications all need headroom.

| Model | Weight GB | Peak server RSS GiB | Swap growth MiB |
|---|---:|---:|---:|
| Nemotron Lightning | 33.59 | 41.50 | 0 |
| Qwen3.6-35B-A3B | 29.31 | 39.90 | 0 |
| Gemma 4 26B-A4B | 23.17 | 37.60 | 0 |
| GLM-4.7-Flash | 24.69 | 40.05 | 0 |
| Qwen3.8-Flash-Next GSQ-RCO | 83.62 | 71.02 | 0 |
| Nemotron Super | 71.93 | 78.85 | 0 |
| Devstral Small 2 | 19.35 | 45.76 | 0 |
| Qwen3.8-27B | 21.98 | 39.40 | 0 |

The GSQ-RCO run began with approximately 26.94 MiB of pre-existing swap after the
unsuccessful Devstral 2 attempt. It caused **no additional swap growth**; its result
does not imply the system had absolutely zero swap allocated.

All eight completed models recalled **3/3 facts in both cold and warm runs**.

| Model | Actual prompt tokens | Cold request s | Cached-prefix request s | Recall cold/warm |
|---|---:|---:|---:|---|
| Nemotron Lightning | 100128 | 61.747 | 2.826 | 3/3, 3/3 |
| Qwen3.6-35B-A3B | 100125 | 88.260 | 13.291 | 3/3, 3/3 |
| Gemma 4 26B-A4B | 100126 | 77.139 | 6.382 | 3/3, 3/3 |
| GLM-4.7-Flash | 100125 | 621.974 | 61.821 | 3/3, 3/3 |
| Qwen3.8-Flash-Next GSQ-RCO | 100125 | 143.004 | 3.217 | 3/3, 3/3 |
| Nemotron Super | 100128 | 165.660 | 22.269 | 3/3, 3/3 |
| Devstral Small 2 | 100125 | 308.010 | 1.463 | 3/3, 3/3 |
| Qwen3.8-27B | 100125 | 259.411 | 5.529 | 3/3, 3/3 |

These request times include generation, and models produce different amounts of
reasoning. They are not pure prefill benchmarks. Needle recall is also not a test
of understanding or editing an entire 100k-token codebase.

The server's phase-specific timings for the **cold 100k request** show how decoding
at long context differs from empty-context generation:

| Model | Cold prefill tok/s | Decode at 100k tok/s |
|---|---:|---:|
| Nemotron Lightning | 1698.19 | 75.49 |
| Qwen3.6-35B-A3B | 1328.89 | 59.64 |
| Gemma 4 26B-A4B | 1414.24 | 48.85 |
| GLM-4.7-Flash | 175.47 | 8.47 |
| Qwen3.8-Flash-Next GSQ-RCO | 715.70 | 39.91 |
| Nemotron Super | 697.92 | 31.43 |
| Devstral Small 2 | 326.53 | 13.83 |
| Qwen3.8-27B | 394.01 | 16.30 |

## 9. Unsuccessful and unfinished candidates

### DeepSeek-Coder-V2-Lite-Instruct

- Quantization: Q6_K; weights: **14.07 GB**.
- Failed the native streaming tool-call gate:
  `incomplete streaming response or expected one tool call`.
- No decode benchmark, HumanEval score, agent matrix, or long-context result was
  collected after that gate failure.
- Gate-run peak RSS: approximately **46.99 GiB**, with no swap growth.

### DeepSeek-R1-Distill-Qwen-32B

- Quantization: Q6_K; weights: **26.89 GB**.
- Failed the same native streaming tool-call gate.
- No coding-quality or throughput score was assigned.
- Gate-run peak RSS: approximately **57.32 GiB**, with no swap growth.

Both rejections concern this native coding-agent pipeline. They do **not** show that
the models cannot perform standalone chat, code generation, or reasoning.

### Devstral 2 123B: 128k failure and 32k retry

| Property | Recorded outcome |
|---|---|
| Quantization | Q4_K_M |
| Weights | 74.90 GB |
| Original context | 131072 |
| Original failure | HTTP 500 `Compute error.` |
| Backend diagnosis | Metal `kIOGPUCommandBufferCallbackErrorOutOfMemory` |
| Original peak server RSS | Approximately 100.21 GiB |
| Original swap growth | 26.94 MiB |
| Retry context | 32768, explicitly set in a local profile override |
| Retry at this snapshot | Compatibility gate passed; full performance/quality suite unfinished |

The failed run is preserved at
[`candidates/results/archive/cand-devstral-2-128k-763ef58783c5/`](candidates/results/archive/cand-devstral-2-128k-763ef58783c5/).

The retry uses the same verified weights, f16 KV cache, and output-token budget.
It does not raise macOS GPU limits. A 32k-context run cannot earn the 100k-recall
label; the long-context stage uses the smaller available prompt budget and records
the actual token count. No final retry score is inferred from its passing gate.

Provenance note: while this retry was running, `bin/opencode-local` and `bin/copilot-local`
were edited for the `lite`/`medium` profile change. Only their non-candidate branches
changed, so `cand-*` agent runs behave the same. However, the retry's `run.json` source hashes
predate the edit, and resuming this run would require archiving it first.

### Optional models not run

| Candidate | Quantization | Weight GB | Status |
|---|---|---:|---|
| GLM-4.5-Air | UD-Q4_K_XL | 67.72 | Optional; not run |
| DeepSeek-V4-Flash-0731 | UD-IQ2_XXS | 90.86 | Experimental, above the nominal 90 GB cap; not run |

These two are excluded from the 11 default-candidate progress counts.

## 10. Categories and provisional conclusions

### Speed tiers

The thresholds apply only to empty-context decode on this machine.

| Tier | Threshold | Fully measured candidates |
|---|---|---|
| Fast | At least 100 tokens/s | Nemotron Lightning; Qwen3.6-35B-A3B |
| Balanced | At least 50 and below 100 tokens/s | Gemma 4; GLM-4.7-Flash |
| Deep | Below 50 tokens/s | Qwen3.8-Flash-Next GSQ-RCO; Nemotron Super; Devstral Small 2; Qwen3.8-27B |

"Deep" is a throughput bucket, not proof of superior reasoning.

### Qualification rules

- Agentic coding: at least **5/6** smoke passes and **all 6/6** repair fixtures.
- Debugging label: at least **96% HumanEval** and both LRU repair fixtures passing.
  This label describes these tests only, not a general reasoning benchmark.
- 100k recall: 3/3 facts in both runs at at least 100000 actual prompt tokens, with
  memory qualification.
- Quick edits: Fast tier, at least 90% HumanEval, median task time at most 5 seconds,
  and non-thinking mode. No completed candidate satisfies all these conditions.
- Autocomplete/FIM: not evaluated; no label is awarded.

| Candidate | Harness decision | Interpretation |
|---|---|---|
| Qwen3.8-Flash-Next GSQ-RCO | Keep as alternate | 99.4% HumanEval; all agents and fixtures; 100k recall |
| Gemma 4 | Keep as alternate | Promising throughput/score balance; Aider timeout is a caveat |
| Nemotron Super | Keep as alternate | Measured 4-bit option with 98.2% HumanEval and complete agent/fixture passes |
| Nemotron Lightning | Keep as alternate | Fastest decode and complete agent/fixture passes; lower HumanEval and 10 truncations |
| Qwen3.8-27B | Keep as alternate | High HumanEval score but slower decode and Claude template incompatibility |
| GLM-4.7-Flash | Keep as alternate | Good short-context throughput; lower score and much slower 100k request |
| Qwen3.6-35B-A3B | Reject under strict agent qualification | One Copilot repair timeout; not a claim that all coding uses fail |
| Devstral Small 2 | Reject under strict agent qualification | Only 3/6 agent integrations passed, despite 6/6 fixtures |
| Both tested DeepSeek models | Reject for this native agent pipeline | Tool-call gate failures, not measured coding-quality failures |
| Devstral 2 | Pending smaller-context retry | Original 128k configuration exhausted GPU memory |

Promotion to a production profile requires a matched incumbent run and an explicit
decision. Historical HumanEval results alone are insufficient to justify promotion.

## 11. Four-bit models and bits-per-weight interpretation

Yes, this bake-off includes four-bit-class models:

- **Nemotron Super Q4_0:** fully tested; 36.8 tokens/s, 161/164 HumanEval.
- **Devstral 2 Q4_K_M:** original 128k allocation failed; 32k retry unfinished.
- **GLM-4.5-Air UD-Q4_K_XL:** optional, not run.

Q4_0 and Q4_K_M are both commonly described as four-bit quantization, but scales,
metadata, and mixed-precision tensors mean effective bits per weight need not be
exactly four. IQ3_S is a lower-bit quantization family, not a four-bit model.

Qwen, Gemma, and GLM also publish four-bit variants, but their Q6 variants were chosen
for most first-round candidates. **A matched Q4-versus-Q6 study of the same model has
not been performed here.** Cross-model comparisons mix architecture, total/active
parameters, training quality, quantization method, kernel support, and context cost.

Consequently:

- Lower-bit weights generally reduce storage and memory needs, but do not guarantee
  faster useful answers or better quality.
- More parameters can add capability, but do not guarantee a better model.
- MoE active-parameter counts affect per-token work; all required weights still
  need memory or an explicitly slower offload strategy.
- GSQ-RCO versus the existing Unsloth Flash-Next quantization changes quantization
  method as well as precision. It does not isolate bits per weight.

## 12. Production profiles before the October 23 change: historical reference

These figures come from the repository's earlier measurements. They were **not**
re-run as matched controls for this complete candidate bake-off.

| Profile (before change) | Model / quantization | Historical decode tok/s | Historical HumanEval |
|---|---|---:|---|
| fast | gpt-oss-20b MXFP4 | About 150 | 159/164 = 97.0% |
| lite | Qwen3-Coder-30B-A3B Q6_K | About 128 | 152/164 = 92.7% |
| medium | Qwen3-Coder-Next Q6_K | About 82 | 154/164 = 93.9% |
| coder | Qwen3.8-Flash-Next UD-IQ3_XXS | About 51 | 162/164 = 98.8% |
| smart | gpt-oss-120b MXFP4 | About 109 | 161/164 = 98.2% |

Before the change, the 256k `long` profile shared the `medium` weights; it now has its own
manifest entry for the same Qwen3-Coder-Next files. The experimental Qwen3-235B `max`
profile is not part of the candidate results above.

For example, 163/164 on the new GSQ-RCO variant versus 162/164 historically on
`coder` is one problem, not evidence of a statistically established improvement.

**Profile change applied:** `lite` → Nemotron Lightning (Q8_0) and `medium` → Gemma 4
(UD-Q6_K), with the sampling settings used in this bake-off. Trade-offs accepted: both
are thinking models, so median HumanEval latency rose from about 1.5–2.4 s to 17.6–22.1 s;
Gemma 4 timed out with Aider; Nemotron Lightning needs more RAM than Gemma 4. The
Qwen3-Coder-specific wrapper workarounds now apply only to `long`. Previous lite/medium
HumanEval results are archived in `eval/results/archive/`. The Qwen3-Coder-30B weights
were not deleted. The `fast`, `coder`, and `smart` profiles are unchanged.

## 13. Provenance, licenses, and implementation details

The 11 default candidates total approximately **423.49 GB of pinned weight files**,
excluding existing production models and the two optional experiments. Failed and
completed weights are preserved; models are not automatically deleted.

Every candidate is pinned to an immutable Hugging Face revision. The
[candidate manifest](candidates/manifest.json) records each file's exact byte size,
SHA-256, repository, revision, and publisher license metadata. The
[catalog](candidates/catalog.json) records the selection, quantization, wave,
thinking flag, and sampling arguments.

The shortlist uses an approximately 90 GB **weight-file** budget, not a 90 GB total
runtime-memory budget. Full GLM-5.3, MiniMax-M3, Kimi, Ling, and DeepSeek-V4.1 models
were screened out for size at the considered quantizations. Inkling was excluded
because the installed llama.cpp build lacks its architecture; MiniMax-H3 is a video
model rather than a text LLM. These exclusions are not failed local benchmark runs.

| Candidate ID | GGUF source | Publisher license field |
|---|---|---|
| `cand-qwen36-35b` | [unsloth/Qwen3.6-35B-A3B-GGUF](https://huggingface.co/unsloth/Qwen3.6-35B-A3B-GGUF) | apache-2.0 |
| `cand-qwen38-27b` | [unsloth/Qwen3.8-27B-GGUF](https://huggingface.co/unsloth/Qwen3.8-27B-GGUF) | apache-2.0 |
| `cand-gemma4-26b` | [unsloth/gemma-4-26B-A4B-it-GGUF](https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF) | apache-2.0 |
| `cand-glm47-flash` | [unsloth/GLM-4.7-Flash-GGUF](https://huggingface.co/unsloth/GLM-4.7-Flash-GGUF) | mit |
| `cand-nemo35-light` | [ggml-org/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF](https://huggingface.co/ggml-org/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-GGUF) | other |
| `cand-devstral-s2` | [unsloth/Devstral-Small-2-24B-Instruct-2512-GGUF](https://huggingface.co/unsloth/Devstral-Small-2-24B-Instruct-2512-GGUF) | other |
| `cand-ds-coder-lite` | [bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF](https://huggingface.co/bartowski/DeepSeek-Coder-V2-Lite-Instruct-GGUF) | other |
| `cand-ds-r1-32b` | [unsloth/DeepSeek-R1-Distill-Qwen-32B-GGUF](https://huggingface.co/unsloth/DeepSeek-R1-Distill-Qwen-32B-GGUF) | apache-2.0 |
| `cand-nemo35-super` | [ggml-org/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-GGUF](https://huggingface.co/ggml-org/NVIDIA-Nemotron-3.5-Super-VL-120B-A12B-GGUF) | other |
| `cand-devstral-2` | [unsloth/Devstral-2-123B-Instruct-2512-GGUF](https://huggingface.co/unsloth/Devstral-2-123B-Instruct-2512-GGUF) | other |
| `cand-qwen38fn-gsq` | [ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF](https://huggingface.co/ISTA-DASLab/Qwen3.8-Flash-Next-GSQ-RCO-GGUF) | apache-2.0 |
| `cand-glm45-air` | [unsloth/GLM-4.5-Air-GGUF](https://huggingface.co/unsloth/GLM-4.5-Air-GGUF) | mit |
| `cand-ds-v4-flash` | [unsloth/DeepSeek-V4-Flash-0731-GGUF](https://huggingface.co/unsloth/DeepSeek-V4-Flash-0731-GGUF) | mit |

License fields are transcribed from the pinned GGUF publishers, not independently
verified legal conclusions. Check the upstream model and conversion licenses before
commercial use or redistribution.

Implementation and validation notes:

- Candidate profiles and results are separate from production profiles.
- A shared profile resolver enables `cand-*` names in downloads, server management,
  and local agent wrappers.
- The downloader resumes interrupted files and verifies pinned hashes.
- The runner holds an exclusive candidate lock and refuses to interrupt an active
  server request.
- Run fingerprints include weights, effective profile settings and local overrides,
  templates, source hashes, package lock, dataset, and llama.cpp build.
- A gate bug uncovered by Mistral was fixed: after a tool result, the harness no
  longer appends an unnecessary extra user message before the assistant answers.
  Earlier failed/interrupted evidence was archived rather than overwritten.
- Sandbox compatibility fixes added healthy-prestarted-server checks, isolated
  Claude temporary storage, and an outer-sandbox-only Codex invocation.
- Completed measurements retain their original source fingerprints. Not every
  candidate ran the identical revision of the orchestration code.
- The existing `fast` model was used to validate the harness: chat/tools, all six
  agents, all six fixtures, a HumanEval sample, and cold/warm 100k recall passed.
  This was a harness check, not a fresh 164-problem incumbent comparison.
- Seventeen offline tests currently cover pinning, shard validation, thresholds,
  missing evidence, profile names, fixture mutations, sandbox containment,
  streaming-tool assembly, role order, and blocked-state recording.

## 14. Raw evidence and reproduction

Primary evidence lives under
[`candidates/results/<candidate-id>/`](candidates/results/).

| Artifact | Contents |
|---|---|
| `run.json` | Effective configuration, runtime, pinned entry, source hashes, fingerprint |
| `gate.json`, `gate.responses.json` | Gate outcome and response evidence |
| `bench.raw.json` | Detailed throughput measurements and runtime metadata |
| `bench.md`, `bench.summary.json` | Readable throughput table and decode summary |
| `humaneval.jsonl`, `humaneval.json` | Per-task results and aggregate counts |
| `smoke.json`, `smoke-*.log` | Agent outcomes and logs |
| `fixtures.json`, `fixture-*.log` | Repair outcomes and logs |
| `long.json` | Actual prompt tokens, cold/warm timings, answers, recall, server timings |
| `memory.json` | Swap baseline/growth, RSS peak, pressure, monitoring errors |
| `summary.json`, `blocked.json` | Stage completion or explicit infrastructure failure |
| `server-final.log` | Retained server diagnostics where captured |

Logs can exist locally while being excluded by the repository's `*.log` ignore
rule. A fresh clone does not automatically include weights, runtime keys, agent
installations, local overrides, or every log.

```bash
# Inspect selected candidates without inference.
python3 candidates/run.py --list

# Run or resume one candidate using its pinned weights.
bash candidates/run_candidate.sh cand-gemma4-26b

# Regenerate the compact machine-readable-evidence-based Markdown scorecard.
python3 candidates/score.py

# Validate the harness without downloading models.
python3 -m unittest discover -s candidates -p 'test_*.py' -v
```

If a run fingerprint changes, preserve/archive the existing result directory before
starting a new run. Do not silently combine incompatible evidence.

This root `report.md` is a **dated narrative snapshot**. The compact
[`candidates/REPORT.md`](candidates/REPORT.md) is regenerated by the scoring script
and by completed candidate runs. The snapshot must be updated when Devstral 2's
32k retry finishes; until then, its final score and memory qualification are pending.

## 15. Limitations and remaining work

- Finish the explicit Devstral 2 32k retry and record its actual result without
  mixing it with the archived 128k OOM configuration.
- HumanEval is relatively easy and potentially saturated/contaminated; it does not
  establish reliability on difficult, long-horizon engineering tasks.
- Smoke tests and fixtures are small, single attempts. Compatibility failures can
  be template/wrapper-specific, and passes do not guarantee repository-scale success.
- General reasoning, FIM autocomplete, vision, audio, million-token context, and
  speculative decoding have not been qualified by this study.
- A same-model Q4/Q6 comparison and matched incumbent runs remain unperformed.
- Optional models remain opt-in. No hosted-model
  comparison, power measurement, or energy/cost benchmark was performed.
