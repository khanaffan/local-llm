# Local LLM for coding agents on Apple Silicon – llama.cpp + Copilot CLI, Claude Code, Codex, OpenCode, Qwen Code, Aider

Run open-weight models locally and use them from popular coding agents. One model is
loaded at a time and served by `llama-server` on `127.0.0.1:8080`. The server speaks the
OpenAI Chat, OpenAI Responses and Anthropic Messages APIs, needs an API key, and has its
web UI disabled.

## Quick start

Requirements:
- Apple Silicon Mac (M1 or newer). RAM decides which models fit: 24 GB runs `fast`, 48 GB adds
  `medium`, 64 GB adds `lite`, 96 GB adds `smart`/`long`, 128 GB adds `coder` (table below).
- [Homebrew](https://brew.sh).
- Disk space for the models you choose: 12–215 GB (`all` = fast, lite, medium, coder, smart: ~214 GB;
  `long` adds 66 GB).

```bash
git clone https://github.com/khanaffan/local-llm.git && cd local-llm
./setup.sh
```

`setup.sh` does the whole setup and can safely be re-run:
1. Checks your Mac (chip, RAM, free disk).
2. Installs any missing `llama.cpp`, `node` and `uv` with Homebrew.
3. Creates a private API key in `run/api-key`.
4. Installs the coding agents at pinned versions into `tools/`. Nothing is installed globally.
5. **Recommends the models that fit your RAM** and asks which ones to download.
6. Downloads them. Downloads resume after interruption, and each file is checked against its SHA-256 hash.
7. Loads one model and sends a test chat.

Non-interactive options:

```bash
./setup.sh --recommended             # every model that fits this Mac's RAM
./setup.sh --models fast,coder       # exactly these (fast|lite|medium|coder|smart|long|all|none)
./setup.sh --no-agents --no-test     # server + models only
./download.sh smart                  # add a model later (set HF_TOKEN if rate-limited)
```

Then start any agent; it loads the matching model automatically:

```bash
bin/claude-local coder       # or: copilot-local, codex-local, opencode-local, qwen-local, aider-local
```

| Profile | Model | Download | Recommended RAM |
|---|---|---|---|
| fast | gpt-oss-20b | 12 GB | ≥ 24 GB |
| lite | Nemotron-3.5-Lightning (30B-A3B) Q8_0 | 34 GB | ≥ 64 GB (license "other"/NVIDIA, not Apache; check the model card) |
| medium | Gemma-4-26B-A4B UD-Q6_K | 23 GB | ≥ 48 GB |
| coder | Qwen3.8-Flash-Next (125B-A6B) UD-IQ3_XXS | 82 GB | ≥ 128 GB (qwen-community-1.0 license, not Apache) |
| smart | gpt-oss-120b | 63 GB | ≥ 96 GB |
| long | Qwen3-Coder-Next (80B-A3B) Q6_K, 256k context (the previous medium) | 66 GB | ≥ 96 GB |
| max (experimental, opt-in) | Qwen3-235B-A22B-Thinking-2507 UD-Q3_K_XL | 104 GB | ≥ 128 GB; raised GPU limit required on 128 GB |

**Trying `max` on 128 GB:** it uses a conservative 16k context and f16 KV cache;
loading, speed, and memory pressure have not yet been measured. Close memory-heavy
apps first. A higher GPU limit allows Metal allocations but does not add RAM;
macOS can still swap or run out of memory. This profile is excluded from
`setup.sh --recommended` and `--models all`; select it explicitly.

```bash
sudo sysctl iogpu.wired_limit_mb=114688   # 112 GiB; temporary until reboot
./download.sh max                       # resumable, verifies all three shards
./llm.sh switch max                     # replaces the current resident model
# Or: bin/claude-local max (other bin/*-local wrappers also accept max)
```

**Which one for coding?** `coder` is the strongest coding model here; `medium` (Gemma 4) is
the default: ~99 tok/s and 97.6% HumanEval in a 23 GB download; `lite` (Nemotron Lightning)
is the fastest thinking model (~106 tok/s) and passed every agent and fixture test, with lower
HumanEval (90.9%); `smart` is the strongest general reasoner. `setup.sh` recommends `medium`
and skips `lite` when `medium` fits. Both new models reason before answering, so a short
answer takes longer than with the previous non-thinking Qwen3-Coder models (median ~18–22 s
vs ~2 s per HumanEval problem).

**Changed 2026-10-23:** `lite` and `medium` were replaced after the
[candidate bake-off](report.md): `lite` was Qwen3-Coder-30B-A3B, `medium` was Qwen3-Coder-Next
(still used by `long`). The old Qwen3-Coder-30B weights are not deleted; remove
`models/Qwen3-Coder-30B-A3B-Instruct-Q6_K.gguf` yourself if you no longer need it.

**Smaller Mac?** Create `profiles/<profile>.local.env` (git-ignored) to override settings
on that machine, e.g. `CTX=65536` to cut KV-cache memory. Both the server and the agent
wrappers read it. Weights (`models/`), runtime state and the key (`run/`), and installed
agents (`tools/`) are never committed.

Only GitHub Copilot CLI is installed globally, and it is optional:
`brew install copilot-cli`.

## Test machine

All numbers in this README (tok/s, prefill, RSS, HumanEval, times) were measured on this machine:

| Component | Spec |
|---|---|
| Chip | Apple M5 Max |
| CPU | 18 cores: 6 performance-class + 12 efficiency-class (`hw.perflevel0/1`) |
| GPU | 40 cores, Metal, all model layers offloaded |
| Neural Engine (NPU) | 16-core (Apple spec); **not used**, llama.cpp runs on the GPU via Metal |
| Memory | 128 GB unified LPDDR5X, ~614 GB/s bandwidth, shared by CPU and GPU |
| OS | macOS 27.0.1 |
| Runtime | llama.cpp 0.7.0 (build 11669, commit 620d2225c), Homebrew, Metal backend |
| Server settings | 1 slot, flash attention on, f16 KV cache (all profiles) |

Decode speed is limited mainly by memory bandwidth, and prefill mainly by GPU cores.
On a different Mac, scale roughly by those two figures (see
[Bottleneck: memory vs compute](#bottleneck-memory-vs-compute)).

## Tiers (measured on this machine, llama.cpp 0.7.0 build 11669, Metal)

| Profile | Alias | Model | Weights | Context | Gen (tok/s) | Prefill (tok/s)† | Server RSS @100k |
|---|---|---|---|---|---|---|---|
| fast | `local-fast` | gpt-oss-20b MXFP4 | 11.3 GiB | 131072 | ~150 | ~2230 @30k | 14.8 GiB |
| lite | `local-lite` | Nemotron-3.5-Lightning-30B-A3B Q8_0 | 31.3 GiB | 131072 | ~106 (thinking) | ~2340 @30k | 41.5 GiB‡ |
| medium | `local-medium` | Gemma-4-26B-A4B UD-Q6_K | 21.6 GiB | 131072 | ~99 (thinking) | ~2310 @30k | 37.6 GiB‡ |
| coder | `local-coder` | Qwen3.8-Flash-Next UD-IQ3_XXS | 76.3 GiB | 131072 | ~51 (thinking) | ~760 avg over 100k | 54.7 GiB* |
| smart | `local-smart` | gpt-oss-120b MXFP4 | 59.0 GiB | 131072 | ~109 | ~1300 @30k | 67.6 GiB |
| long | `local-long` | Qwen3-Coder-Next Q6_K (the previous medium) | 61.1 GiB | 262144 | ~82 empty / 30 @239k | ~510 avg over 239k | 43.4 GiB* @239k |

\* Weights are memory-mapped, so RSS can count part of them as file cache; plan on
weights + KV. No swap or memory pressure was seen for any profile.
† "@30k" is `llama-bench` at a 30k-token prompt; "avg over N" is a cold N-token server prompt
(slower, because attention cost grows with context). Compare within the same method only.
‡ lite and medium were measured by the [candidate bake-off](report.md): peak sampled server
RSS across all its stages (including a ~100k prompt), not a single reading at 100k.

Cold ~100k-token prompt: lite 62 s, medium 77 s, fast 95 s, coder 135 s, smart 138 s. Repeating the same
prefix is served from the prompt cache (≈0.1–3 s; medium 6 s). Treat these as measurements for
this setup, not guarantees. Raw `llama-bench` output is in `bench/` and
`candidates/results/<id>/bench.md`.

Qualification: fast and smart (and the retired Qwen3-Coder-30B) passed streaming
tool calls, multi-turn tool loops, tool-error recovery and the bug-fix / multi-file edit /
failing-test repair fixtures (`fixtures/`) in both OpenCode and Copilot CLI. coder and
long were qualified with the six-agent smoke test (`eval/agents_smoke.sh`), HumanEval and
the long-context recall runs instead. lite and medium went through the full candidate
bake-off: native streaming tool-call gate, all six fixtures (6/6 each), six-agent smoke test
(lite 6/6, medium 5/6), HumanEval, and cold/warm ~100k recall (3/3). No swap use or memory
pressure in any run.

## Eval scorecard (HumanEval, 164 problems, pass@1)

| Tier | Model | Pass@1 | 95% CI | Median s/problem | Avg tokens/answer | End-to-end tok/s | Total |
|---|---|---|---|---|---|---|---|
| fast | gpt-oss-20b | 97.0% (159/164) | 93–99% | 3.6 s | 645 | 140 | 12.6 min |
| medium | Gemma-4-26B-A4B | 97.6% (160/164) | 94–99% | 22.1 s | 2215 | 87§ | –§ |
| coder | Qwen3.8-Flash-Next | **98.8% (162/164)** | 96–100% | 10.7 s | 641 | 45 | 39.0 min |
| smart | gpt-oss-120b | 98.2% (161/164) | 95–99% | 4.2 s | 479 | 97 | 13.5 min |
| lite | Nemotron-3.5-Lightning-30B-A3B | 90.9% (149/164) | 85–94% | 17.6 s | 2218 | 95§ | –§ |
| *retired medium* | Qwen3-Coder-Next (now `long`) | 93.9% (154/164) | 89–97% | 2.4 s | 206 | 76 | 7.4 min |
| *retired lite* | Qwen3-Coder-30B-A3B | 92.7% (152/164) | 88–96% | 1.5 s | 213 | 116 | 5.0 min |

§ lite and medium come from the candidate bake-off. 15 (lite) and 20 (medium) requests stalled
for 15–30 min while producing few tokens; the cause was not determined. End-to-end tok/s excludes those requests; total time is
omitted because the stalls dominate it. lite hit the 8192-token cap on 10 problems, medium on 4.

**How it was run:** one sample per problem at each model's card sampling settings, 8192 max
tokens, single slot, one tier at a time. The original tiers had no truncation or request
error (see the § note for lite/medium). The
failures I inspected were genuine wrong answers (including one model syntax error), not
harness errors. Generated code ran under `sandbox-exec` (no network, writes confined to a
temp dir, 15 s timeout); the harness was checked with wrong-answer, network, file-write and
infinite-loop controls.

**How to read it:** fast, medium, coder and smart (97.0–98.8%) are within the noise of a single
sample, so HumanEval cannot separate them. lite is about 6–8 points lower, partly from hitting
the output cap while reasoning. The retired Qwen3-Coder models were quickest per problem
because they answer without reasoning. Coder at its template-default `xhigh` reasoning effort ran
past the 8192-token cap on 4 of its first 47 problems, so the profile uses `medium` effort. HumanEval
is easy and likely saturated, so this shows basic coding correctness, not a ranking on hard
or long-horizon tasks. The agent fixtures above cover multi-step tool use.

**Re-run:** `eval/run_all.sh [fast|lite|medium|coder|smart|long ...]`, then `python3 eval/score.py` (writes
`eval/SCORECARD.md`). Runs are resumable and must not be run with `sudo`.

### Testing additional models

See the [detailed benchmark report](report.md) for the dated results, methodology,
compatibility failures, memory measurements, and pending experiments.

The [candidate bake-off](candidates/README.md) downloads pinned models and measures
speed, memory, HumanEval, coding-agent compatibility, repair fixtures and 100k recall
without replacing the production profiles. See the [candidate report](candidates/REPORT.md)
for measured results; untested and blocked models are explicitly distinguished.

```bash
python3 candidates/run.py --list
bash candidates/run_candidate.sh --wave 1
```

## Local vs online models: speed, cost and coding workflows

Dated **2026-10-20**. Local speeds were measured on the [test machine](#test-machine).
**Sol and Sonnet were not benchmarked here**, and their docs give no fixed per-request
tok/s (it varies with service tier, load, prompt size and reasoning effort), so this
section does not claim local is faster or slower.

### Generation speed and time per million tokens

Decode-only estimates (`tokens ÷ measured tok/s`). "1M" means output accumulated over many
requests (wrappers cap each reply at 8192 tokens). Reasoning tokens count toward time.

| Model / profile | Decode | 1k tokens | 1M tokens | API $ per 1M in / out |
|---|---|---|---|---|
| gpt-oss-20b (`fast`) | ~150 tok/s | ~7 s | ~1 h 51 min | none* |
| Nemotron-3.5-Lightning (`lite`) | ~106 tok/s | ~9 s | ~2 h 37 min | none* |
| Gemma-4-26B-A4B (`medium`) | ~99 tok/s | ~10 s | ~2 h 49 min | none* |
| Qwen3.8-Flash-Next (`coder`) | ~51 tok/s | ~20 s | ~5 h 27 min | none* |
| gpt-oss-120b (`smart`) | ~109 tok/s | ~9 s | ~2 h 33 min | none* |
| Qwen3-Coder-Next (`long`, at 239k) | ~30 tok/s | ~33 s | ~9 h 16 min | none* |
| GPT-6.1 Sol | not measured | – | – | $2 / $10 |
| Claude Sonnet 5.5 | not measured (Anthropic: "Fast") | – | – | $2 / $10 |

\* No token fee, but hardware, electricity and upkeep still cost money (wall power not
measured). Cloud prices are standard direct-API rates; caching, batch, fast tiers and
long-context surcharges change them. Example: 1M uncached input + 100k output = **$3** on
either model. For reference, a cloud speed of 50 / 100 / 200 tok/s would mean
5 h 33 min / 2 h 47 min / 1 h 23 min per 1M output tokens (arithmetic, not benchmarks).

### What determines task time

`Task time ≈ load + cold prefill + output tokens ÷ decode rate + tool/test time + network`,
summed over agent turns. Cold ~100k-token prefill took **62–138 s** here (`long`: 470 s for
239k); cached prefixes are near-instant. Example: ten turns of 1k output each ≈ **101 s on
medium**, **196 s on coder** (≈ **588 s** if coder also reasons 2k tokens per turn), before
prefill and tools. lite and medium also reason before answering, which adds output tokens.
Faster decode does not guarantee a faster *successful* fix.

### Workflows to target

| Workflow | Start with | Guardrails |
|---|---|---|
| Routine edits, boilerplate, docstrings, test scaffolds | `medium` (or `lite`); `fast` for latency | Name the files and acceptance tests; review the diff. |
| Scoped bug fixes, test-driven repairs | `medium`, then `coder` | Reproduce first, run tests. The smoke task passing is not proof of repo-wide reliability. |
| Code explanation, log analysis, extraction | `fast` or `medium` | Send relevant snippets, not the whole repo; verify claims. |
| Hard debugging, multi-file reasoning | `coder` or `smart` | Checkpoint with tests; escalate to cloud if stalled (no head-to-head comparison run). |
| Very large code/log investigations | `long` when retrieval is not enough | Expect minutes of cold prefill; needle recall ≠ full understanding. |
| Sensitive / offline code | any local profile | Inference is local, but agents, MCP tools and shell commands may still use the network. |
| Overnight batches | `medium` or `coder` | Run sequentially with timeouts, isolated worktrees and test gates. |
| Many parallel agents, urgent repo-wide changes | Sol / Sonnet | This server has one slot and one resident model. |

**Practical default:** local `medium` for edit/test loops, `coder` for harder reasoning,
cloud for stalled or high-stakes work. Wrappers never route or fall back to cloud automatically.

Sources: [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol),
[Claude models](https://platform.claude.com/docs/en/models/overview),
[Claude pricing](https://platform.claude.com/docs/en/about-claude/pricing),
[OpenAI latency guide](https://developers.openai.com/api/docs/guides/latency-optimization).
Local evidence: tier table, `eval/results/`, `eval/long_*.log`.

## Larger context windows

| Model | Native (`n_ctx_train`) | Configured | Beyond native? |
|---|---|---|---|
| gpt-oss-20b / 120b | 131072 | 131072 (max) | No: already at the trained limit |
| Qwen3-Coder-Next | 262144 | **long 262144** | YaRN up to ~1M (not enabled) |
| Qwen3.8-Flash-Next | 262144 | coder 131072 | Could raise to 262144; YaRN to ~1M (not enabled) |

**`long` profile test** (`eval/long_context.py local-long 48000`, log in
`eval/long_qwen3-coder-next_256k.log`):
- 238,772-token prompt with 3 facts hidden at 10%, 50% and 90% depth: **3/3 recalled**, cold and warm.
- Cold prefill took **470 s (~8 min)**, ~510 tok/s on average.
- A cached repeat of the same prompt took 1.2 s.
- Decode was **30 tok/s** at that depth, versus ~82 tok/s when the context is short.
- No swap.
- The retired Qwen3-Coder-30B-A3B took 1312 s with 11.5 tok/s decode on the same prompt
  (`eval/long_qwen3-coder-30b_256k.log`). Qwen3-Coder-Next and Qwen3.8 use hybrid linear
  attention (Gated DeltaNet), so long prompts are much cheaper.

At ~100k tokens (3/3 recall each): Qwen3-Coder-Next prefill 943 tok/s, decode 48 tok/s; coder
prefill 763 tok/s, decode 44 tok/s (`eval/long_qwen3-coder-next_100k.log`,
`eval/long_qwen3.8-flash-next_100k.log`). lite prefill 1698 tok/s, decode 75 tok/s; medium
prefill 1414 tok/s, decode 49 tok/s (`candidates/results/cand-*/long.json`). lite and medium
were only tested up to ~100k; their 128k `CTX` is untested beyond that.

Use `long` only when a session really needs more than 128k tokens, e.g. reading a big
codebase or log in one go. In agent sessions the context grows a turn at a time and
the prefix is cached, so you never pay the full cold prefill. Generation still slows
as the context fills. For everyday work, the 128k tiers with client compaction are
much faster.

**Not enabled: YaRN past 256k** (`--rope-scaling yarn --rope-scale 2|4 --yarn-orig-ctx 262144`).
- Hybrid attention keeps KV small (only some layers keep a full KV cache), but long's 61 GiB
  of weights leave ~45 GiB for KV and buffers; measure before enabling 512k+.
- The cold prefill would take hours, and static YaRN can hurt quality on short prompts (Qwen model card).

## Bottleneck: memory vs compute

On this M5 Max (128 GB, 40-core GPU, 18-core CPU) **memory is plentiful and compute is
the limit**.

- **Memory has headroom.** The largest profile (coder: 76 GiB of weights plus a small hybrid
  KV cache) fits within the ~107 GiB Metal can use. No swap or memory
  pressure was seen. In earlier tests on gpt-oss-20b and the 30B Qwen3-Coder (the retired `lite`),
  a q8_0 KV cache saved memory nobody needed and made generation slower, so f16 is used.
- **Compute is the limit.** Cold prefill of a 239k-token prompt took ~8 min (22 min with
  the older 30B model). Generation runs ~50–150 tok/s at short context, limited by the GPU
  and memory bandwidth, and falls to 30 tok/s at 239k tokens. The CPU cores are mostly idle, because inference runs on
  the GPU.

Uses for the spare memory:
- Larger sparse (MoE) weights: done, see the `long` and `coder` tiers and
  [Coding model research](#coding-model-research-sparse-moe-oct-2026).
- Speculative decoding (e.g. gpt-oss-20b drafting for gpt-oss-120b) for faster generation.
- Parallel slots (`-np 2`) or two models resident at once.

More RAM would not make this setup faster. Faster prefill and generation need more GPU
compute and memory bandwidth.

## Coding model research (sparse MoE, Oct 2026)

Mixture-of-experts models store many parameters but read only the *active* ones per
token. Decode speed is roughly 614 GB/s ÷ (active parameters × bytes per weight), an upper
bound, while quality tracks total size more closely. Candidates that fit 128 GB (Hugging Face model cards and unsloth GGUF sizes):

| Model | Total / active | Fitting quant (size) | Status |
|---|---|---|---|
| **Qwen3.8-Flash-Next** | 125B / 6B (+51B n-gram embeddings) | UD-IQ3_XXS (82 GB) | **`coder` tier**. Card: SWE-bench Pro 62.5, SWE-bench Multilingual 81.0, LiveCodeBench v6 91.9. License: qwen-community-1.0 |
| **Qwen3-Coder-Next** | 80B / 3B | Q6_K (66 GB) | **`long` tier** (was `medium` until 2026-10-23). Coding-only, non-thinking, Apache-2.0 |
| Qwen3.5-122B-A10B | 122B / 10B | Q5_K_M (91 GB) | General model, slower; not added |
| MiniMax-M2.7 | 229B / ~10B‡ | UD-IQ3_XXS (80 GB) | Needs ~3-bit squeeze; not added |
| GLM-5.3-Flash | 320B / 18B | ≥ 93 GB even at 1-bit | Does not fit usefully |
| MiniMax-M3, DeepSeek-V4.1-Flash, Ling-3.1-flash | 428B–763B | – | Too large for 128 GB |

‡ Active count taken from the MiniMax-M2.x lineage; not confirmed on the M2.7 card.
The card scores are the vendors' own. Locally, both new tiers passed every agent smoke test
and their long-context recall tests. HumanEval is too easy to rank them.

## Usage

```bash
./llm.sh switch fast|lite|medium|coder|smart|long   # stop current model, start another (waits for readiness)
./llm.sh status | stop

# every wrapper: bin/<agent>-local [profile, default fast] [agent's own args]
bin/copilot-local  [--offline] [fast|lite|medium|coder|smart|long] [copilot args]
bin/opencode-local [fast|lite|medium|coder|smart|long] [opencode args]
bin/claude-local   [fast|lite|medium|coder|smart|long] [claude args]
bin/codex-local    [fast|lite|medium|coder|smart|long] [codex args]
bin/qwen-local     [fast|lite|medium|coder|smart|long] [qwen args]
bin/aider-local    [fast|lite|medium|coder|smart|long] [aider args]
```

Each wrapper switches the server to that profile if needed and then starts the agent.

Wrappers set configuration only for their own process; global agent settings are
untouched. Picking a different model inside a client does **not** switch the
server; use `llm.sh switch` or the wrapper. `copilot-local --offline` sets
`COPILOT_OFFLINE=true` (GitHub features such as code search/delegate are unavailable).

### Remote use (from another machine)

The server only listens on `127.0.0.1`. To use it from another machine, enable Remote Login
(SSH) on the server Mac, then clone this repo on the client and set:

```bash
export LOCAL_LLM_REMOTE=user@server-host     # needs key-based or agent SSH login
export LOCAL_LLM_REMOTE_DIR=local-llm        # repo path on the server, relative to ~ (default)
bin/opencode-local coder                     # any wrapper works
```

The wrappers then switch the model on the server over SSH, read its API key and `CTX`, and
open an SSH tunnel to `127.0.0.1:8080` if nothing is listening there yet. The client needs
no models, llama.cpp, or `run/api-key`, only the agent tools (`./setup.sh --models none`).
Close the tunnel with `pkill -f "ssh -f -N .*8080:127.0.0.1:8080"`, or `kill` its pid.

### Coding agents

All of these talk directly to `llama-server`; no proxy is needed. Everything except
Copilot CLI is installed locally in `tools/`.

| Wrapper | Agent (version) | API used | How it is configured |
|---|---|---|---|
| `copilot-local` | GitHub Copilot CLI (global install) | OpenAI Chat Completions | `COPILOT_PROVIDER_*` env (BYOK) |
| `opencode-local` | OpenCode 1.19.3 | OpenAI Chat Completions | `opencode.json` + `OPENCODE_CONFIG_CONTENT` |
| `claude-local` | Claude Code 2.1.304 | Anthropic Messages (`/v1/messages`) | `ANTHROPIC_BASE_URL`/`AUTH_TOKEN`; separate config dir `run/claude-home` |
| `codex-local` | OpenAI Codex CLI 0.163.0 | OpenAI Responses (`/v1/responses`) | `-c model_providers.local-llm=…` overrides |
| `qwen-local` | Qwen Code 0.25.3 | OpenAI Chat Completions | `OPENAI_*` env + generated `run/qwen-settings-<profile>.json` |
| `aider-local` | Aider 0.86.2 (uv, `tools/uv`) | OpenAI Chat Completions (LiteLLM) | `OPENAI_API_BASE` + generated `run/aider-metadata-<profile>.json` |

- **Limits:** every wrapper sets the context window to the profile's `CTX`, output to
  8192 tokens, and auto-compaction/prompt limit to `CTX - 8192` wherever the agent
  supports it.
- **Claude Code:** every model slot (main, Haiku/background, subagents) is mapped to the
  resident model. Your real Claude login and settings in `~/.claude` are not used.
  Nonessential traffic and auto-update are off. It logs a harmless
  `unrecognized_model` note.
- **Copilot with Qwen3-Coder-Next (long):** with the full tool set the model kept
  calling `read_bash`/`read_agent` with file names as arguments (as if they were file readers)
  and looped. The cause was not investigated further.
  For these profiles the wrapper offers only `bash view edit create glob grep`
  (`--available-tools`); override with `LOCAL_LLM_COPILOT_TOOLS="..."`.
- **Claude Code with coder:** the Qwen3.8 chat template rejects system messages after the
  first turn, which Claude Code sends. `templates/qwen3.8-flash-next.jinja` is the GGUF
  template with only that check changed to render them (`CHAT_TEMPLATE` in the profile).
- **OpenCode with Qwen3-Coder-Next (long):** Qwen3-Coder tended to keep calling tools
  (todo updates, re-running tests) after the task was done, so the turn never ended.
  For this profile the wrapper disables the todo tools and caps agent steps at 50.
  Raise the cap with `LOCAL_LLM_OPENCODE_STEPS=N`. lite and medium run with the full
  tool sets in OpenCode and Copilot, as they were tested.
- **Headless OpenCode with fast:** gpt-oss-20b sometimes globs `/`, which headless
  `opencode run` auto-rejects (2 of 7 runs). Interactive sessions prompt you instead.

**Smoke test:** `eval/agents_smoke.sh <profile> [agents…]` gives each agent the same
bug-fix task in a scratch directory. It then checks independently that the test passes
and that the test file is unchanged.

| Profile | copilot | opencode | claude | codex | qwen | aider |
|---|---|---|---|---|---|---|
| fast | PASS | PASS (flaky, see above) | PASS | PASS | PASS | PASS |
| lite | PASS | PASS | PASS | PASS | PASS | PASS |
| medium | PASS | PASS | PASS | PASS | PASS | FAIL (timeout) |
| coder | PASS | PASS | PASS (patched template) | PASS | PASS | PASS |
| smart | PASS | PASS | PASS | PASS | PASS | PASS |
| long | not run | PASS | PASS | PASS | not run | not run |

lite and medium rows are from the candidate bake-off's sandboxed run of the same task
(`candidates/results/cand-nemo35-light/`, `cand-gemma4-26b/`). Gemma 4 with Aider hit the
600 s timeout; use another agent with `medium`, or verify Aider on your own task first.
`long` uses Qwen3-Coder-Next, which passed all six agents when it was `medium`
(Copilot with core tools only).

Most runs took 10–60 s; coder is slower (25–140 s) because it reasons first.

Quick connectivity check:
```bash
curl -H "Authorization: Bearer $(cat run/api-key)" http://127.0.0.1:8080/v1/models
```

## Configuration and tuning decisions

- Flags: `-ngl all --flash-attn on --jinja -np 1`, `--no-webui`; sampling per model card
  (`profiles/*.env`). gpt-oss and Qwen3.8 reasoning effort is `medium`.
- KV cache: **f16**. `q8_0` KV was slower on both models tested (gpt-oss-20b tg 150→145,
  Qwen3-Coder-30B/retired `lite` tg 128→110; see `bench/`) and memory is not constrained, so it is
  not used. It was not re-tested on Qwen3-Coder-Next or Qwen3.8, whose hybrid attention
  keeps the KV cache small anyway.
- Memory: no `mlock`/`--no-mmap`/`iogpu.wired_limit_mb` changes were needed.
  Metal reports ~107 GiB usable; the largest profile (coder, 76 GiB weights) at 128k fits
  with headroom.
- Output is capped at 8192 tokens in clients; Copilot prompt limit = `CTX - 8192`.
- Cold long-context prefill is the main latency cost. Keep conversations prefix-stable
  to benefit from prompt caching; consider the fast tier for large-context scans.
- Requests beyond the context size are rejected (HTTP 400), not silently truncated.

## Files

- `manifest.json` – pinned model repo/revision/file; `download.sh <profile>` downloads
  and verifies the full SHA-256. `setup.sh` – bootstrap for a fresh clone.
- `profiles/*.env`, `llm.sh` – server lifecycle (one process, owned-PID stop, port-conflict checks).
- `opencode.json`, `bin/*-local` (+ shared `bin/_common.sh`) – agent wrappers. `run/api-key` – local key (mode 600; do not commit).
- `models/` – weights (~214 GB for `all`, +66 GB for `long`; do not commit). Multi-file (sharded) GGUFs are listed per shard in `manifest.json`; the profile points at shard 1. `templates/` – patched chat templates. `tools/` – locally installed agents (npm: OpenCode, Claude Code, Codex, Qwen Code; uv: Aider in `tools/uv`, `tools/bin`); only `tools/package*.json` is committed.
- `bench/`, `fixtures/` – benchmark output and qualification fixtures.
- `eval/` – HumanEval harness (`run_humaneval.py`, `run_all.sh`, `score.py`), the pinned
  dataset (`HumanEval.jsonl.gz`, MIT, from openai/human-eval), per-problem `results/*.jsonl`, and `SCORECARD.md`. `long_context.py` is the
  needle-recall / long-prefill test. `agents_smoke.sh` is the per-agent bug-fix smoke test.

## Troubleshooting / cleanup

- **Never run these tools with `sudo`.** Root-created files in `~/.copilot` (config, logs,
  sessions) become unreadable to your user, and Copilot then exits silently, which looks like
  "it needs sudo". The scripts refuse to run as root. If it happens, repair with:
  `sudo find ~/.copilot ~/local-llm -user root -exec chown -h "$USER":staff {} +`

- `error: port 8080 is in use` – another process owns the port; `lsof -nP -iTCP:8080`.
- Server log: `run/server.log`.
- Remove: `./llm.sh stop; rm -rf models tools run; brew uninstall llama.cpp`.
- Auto-start at login is intentionally not configured.
