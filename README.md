# Local LLM for coding agents on Apple Silicon – llama.cpp + Copilot CLI, Claude Code, Codex, OpenCode, Qwen Code, Aider

Run open-weight models locally and use them from popular coding agents. One model is
loaded at a time and served by `llama-server` on `127.0.0.1:8080`. The server speaks the
OpenAI Chat, OpenAI Responses and Anthropic Messages APIs, needs an API key, and has its
web UI disabled.

## Quick start

Requirements:
- Apple Silicon Mac (M1 or newer). 24 GB RAM is the minimum; 64 GB or more is recommended.
- [Homebrew](https://brew.sh).
- Disk space for the models you choose: 12–100 GB.

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
./setup.sh --models fast,medium      # exactly these (fast|medium|smart|long|all|none)
./setup.sh --no-agents --no-test     # server + models only
./download.sh smart                  # add a model later (set HF_TOKEN if rate-limited)
```

Then start any agent; it loads the matching model automatically:

```bash
bin/claude-local medium      # or: copilot-local, codex-local, opencode-local, qwen-local, aider-local
```

| Profile | Model | Download | Recommended RAM |
|---|---|---|---|
| fast | gpt-oss-20b | 12 GB | ≥ 24 GB |
| medium | Qwen3-Coder-30B-A3B Q6_K | 25 GB | ≥ 48 GB |
| long | same as medium, 256k context | (uses medium) | ≥ 64 GB |
| smart | gpt-oss-120b | 63 GB | ≥ 96 GB |

**Smaller Mac?** Create `profiles/<profile>.local.env` (git-ignored) to override settings
on that machine, e.g. `CTX=65536` to cut KV-cache memory. Both the server and the agent
wrappers read it. Weights (`models/`), runtime state and the key (`run/`), and installed
agents (`tools/`) are never committed.

Only GitHub Copilot CLI is installed globally, and it is optional:
`brew install copilot-cli`.

The measurements below come from an Apple M5 Max with 128 GB RAM.

## Tiers (measured on this machine, llama.cpp 0.7.0 build 11669, Metal)

| Profile | Alias | Model | Weights | Context | Gen (tok/s) | Prefill 30k (tok/s) | Server RSS @100k |
|---|---|---|---|---|---|---|---|
| fast | `local-fast` | gpt-oss-20b MXFP4 | 11.3 GiB | 131072 | ~150 | ~2230 | 14.8 GiB |
| medium | `local-medium` | Qwen3-Coder-30B-A3B Q6_K | 23.4 GiB | 131072 | ~128 | ~1050 | 35.8 GiB |
| smart | `local-smart` | gpt-oss-120b MXFP4 | 59.0 GiB | 131072 | ~109 | ~1300 | 67.6 GiB |
| long | `local-long` | Qwen3-Coder-30B-A3B Q6_K (same file as medium) | 23.4 GiB | 262144 | ~128 empty / 11.5 @239k | ~180 avg over 239k | 48.1 GiB @239k |

Cold ~100k-token prompt: fast 95 s, medium 265 s, smart 138 s. Repeating the same
prefix is served from the prompt cache (≈0.1–1.3 s). Treat these as measurements for
this setup, not guarantees. Raw `llama-bench` output is in `bench/`.

Qualification (both OpenCode and Copilot CLI): streaming tool calls, multi-turn tool
loops, tool-error recovery, and scoped bug fix / multi-file edit / failing-test repair
fixtures (`fixtures/`), with tests left untouched. No swap use or memory pressure.

## Eval scorecard (HumanEval, 164 problems, pass@1)

| Tier | Model | Pass@1 | 95% CI | Median s/problem | Avg tokens/answer | End-to-end tok/s | Total |
|---|---|---|---|---|---|---|---|
| fast | gpt-oss-20b | 97.0% (159/164) | 93–99% | 3.6 s | 645 | 140 | 12.6 min |
| medium | Qwen3-Coder-30B-A3B | 92.7% (152/164) | 88–96% | 1.5 s | 213 | 116 | 5.0 min |
| smart | gpt-oss-120b | 98.2% (161/164) | 95–99% | 4.2 s | 479 | 97 | 13.5 min |

**How it was run:** one sample per problem at each model's card sampling settings, 8192 max
tokens, single slot, one tier at a time. No run was truncated or hit a request error. The
failures I inspected were genuine wrong answers (including one model syntax error), not
harness errors. Generated code ran under `sandbox-exec` (no network, writes confined to a
temp dir, 15 s timeout); the harness was checked with wrong-answer, network, file-write and
infinite-loop controls.

**How to read it:** fast vs smart (97.0% vs 98.2%) is within the noise of a single sample, so
HumanEval cannot separate them. Medium is the quickest but about 4–5 points lower. HumanEval
is easy and likely saturated, so this shows basic coding correctness, not a ranking on hard
or long-horizon tasks. The agent fixtures above cover multi-step tool use.

**Re-run:** `eval/run_all.sh [fast|medium|smart|long ...]`, then `python3 eval/score.py` (writes
`eval/SCORECARD.md`). Runs are resumable and must not be run with `sudo`.

## Larger context windows

| Model | Native (`n_ctx_train`) | Configured | Beyond native? |
|---|---|---|---|
| gpt-oss-20b / 120b | 131072 | 131072 (max) | No: already at the trained limit |
| Qwen3-Coder-30B-A3B | 262144 | medium 131072, **long 262144** | YaRN up to ~1M (not enabled) |

**`long` profile test** (`eval/long_context.py local-long 48000`, log in
`eval/long_medium_256k.log`):
- 238,772-token prompt with 3 facts hidden at 10%, 50% and 90% depth: **3/3 recalled**, cold and warm.
- Cold prefill took **1312 s (~22 min)**. Average prefill speed drops as the context grows: ~1050 tok/s over the first 30k tokens, ~180 tok/s over the full 239k.
- A cached repeat of the same prompt took 1.7 s.
- Decode was **11.5 tok/s** at that depth, versus ~128 tok/s when the context is short.
- Server RSS was 48.1 GiB, with no swap.

Use `long` only when a session really needs more than 128k tokens, e.g. reading a big
codebase or log in one go. In agent sessions the context grows a turn at a time and
the prefix is cached, so you never pay the full cold prefill. Generation still slows
as the context fills. For everyday work, the 128k tiers with client compaction are
much faster.

**Not enabled: YaRN past 256k** (`--rope-scaling yarn --rope-scale 2|4 --yarn-orig-ctx 262144`).
- KV memory for Qwen3-Coder is ~96 KiB per token at f16.
- 512k at f16 ≈ 48 GiB KV, about 72 GiB total; this fits.
- 1M ≈ 96 GiB KV at f16 (does not fit) or ≈ 48 GiB at q8_0 (fits).
- The cold prefill would take hours, and static YaRN can hurt quality on short prompts (Qwen model card).

## Usage

```bash
./llm.sh switch fast|medium|smart|long   # stop current model, start another (waits for readiness)
./llm.sh status | stop

# every wrapper: bin/<agent>-local [profile, default fast] [agent's own args]
bin/copilot-local  [--offline] [fast|medium|smart|long] [copilot args]
bin/opencode-local [fast|medium|smart|long] [opencode args]
bin/claude-local   [fast|medium|smart|long] [claude args]
bin/codex-local    [fast|medium|smart|long] [codex args]
bin/qwen-local     [fast|medium|smart|long] [qwen args]
bin/aider-local    [fast|medium|smart|long] [aider args]
```

Each wrapper switches the server to that profile if needed and then starts the agent.

Wrappers set configuration only for their own process; global agent settings are
untouched. Picking a different model inside a client does **not** switch the
server; use `llm.sh switch` or the wrapper. `copilot-local --offline` sets
`COPILOT_OFFLINE=true` (GitHub features such as code search/delegate are unavailable).

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
- **OpenCode with Qwen profiles (medium/long):** Qwen3-Coder tended to keep calling tools
  (todo updates, re-running tests) after the task was done, so the turn never ended.
  For these profiles the wrapper disables the todo tools and caps agent steps at 50.
  Raise the cap with `LOCAL_LLM_OPENCODE_STEPS=N`.
- **Headless OpenCode with fast:** gpt-oss-20b sometimes globs `/`, which headless
  `opencode run` auto-rejects (2 of 7 runs). Interactive sessions prompt you instead.

**Smoke test:** `eval/agents_smoke.sh <profile> [agents…]` gives each agent the same
bug-fix task in a scratch directory. It then checks independently that the test passes
and that the test file is unchanged.

| Profile | copilot | opencode | claude | codex | qwen | aider |
|---|---|---|---|---|---|---|
| fast | PASS | PASS (flaky, see above) | PASS | PASS | PASS | PASS |
| medium | PASS | PASS (after step cap) | PASS | PASS | PASS | PASS |
| smart | PASS | PASS | PASS | PASS | PASS | PASS |
| long | not run | PASS | PASS | PASS | not run | not run |

Most runs took 6–60 s.

Quick connectivity check:
```bash
curl -H "Authorization: Bearer $(cat run/api-key)" http://127.0.0.1:8080/v1/models
```

## Configuration and tuning decisions

- Flags: `-ngl all --flash-attn on --jinja -np 1`, `--no-webui`; sampling per model card
  (`profiles/*.env`). gpt-oss reasoning effort is `medium`.
- KV cache: **f16**. `q8_0` KV was slower on both tested models (gpt-oss-20b tg 150→145,
  Qwen3-Coder tg 128→110) and memory is not constrained, so it is not used.
- Memory: no `mlock`/`--no-mmap`/`iogpu.wired_limit_mb` changes were needed.
  Metal reports ~107 GiB usable; the smart tier at 128k fits with headroom.
- Output is capped at 8192 tokens in clients; Copilot prompt limit = `CTX - 8192`.
- Cold long-context prefill is the main latency cost. Keep conversations prefix-stable
  to benefit from prompt caching; consider the fast tier for large-context scans.
- Requests beyond the context size are rejected (HTTP 400), not silently truncated.

## Files

- `manifest.json` – pinned model repo/revision/file; `download.sh <profile>` downloads
  and verifies the full SHA-256. `setup.sh` – bootstrap for a fresh clone.
- `profiles/*.env`, `llm.sh` – server lifecycle (one process, owned-PID stop, port-conflict checks).
- `opencode.json`, `bin/*-local` (+ shared `bin/_common.sh`) – agent wrappers. `run/api-key` – local key (mode 600; do not commit).
- `models/` – weights (~100 GB, do not commit). `tools/` – locally installed agents (npm: OpenCode, Claude Code, Codex, Qwen Code; uv: Aider in `tools/uv`, `tools/bin`); only `tools/package*.json` is committed.
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
