# Local LLM scorecard

HumanEval (164 problems), pass@1, one sample per problem at each model's card sampling settings, 8192 max tokens, hidden unit tests run in a sandbox.

| Tier | Model | HumanEval pass@1 | 95% CI | Median s/problem | Avg tokens | End-to-end tok/s | Total min | Truncated/errors |
|---|---|---|---|---|---|---|---|---|
| fast | gpt-oss-20b | 159/164 = 97.0% | 93–99% | 3.6 | 645 | 140 | 12.6 | 0 |
| lite | Nemotron-3.5-Lightning-30B-A3B Q8_0 | 149/164 = 90.9% | 85–94% | 17.6 | 2218 | 20 | 307.1 | 10 |
| medium | Gemma-4-26B-A4B UD-Q6_K | 160/164 = 97.6% | 94–99% | 22.1 | 2215 | 15 | 403.1 | 4 |
| coder | Qwen3.8-Flash-Next UD-IQ3_XXS | 162/164 = 98.8% | 96–100% | 10.7 | 641 | 45 | 39.0 | 0 |
| smart | gpt-oss-120b | 161/164 = 98.2% | 95–99% | 4.2 | 479 | 97 | 13.5 | 0 |
| lite (retired) | Qwen3-Coder-30B-A3B Q6_K | 152/164 = 92.7% | 88–96% | 1.5 | 213 | 116 | 5.0 | 0 |
| medium (retired) | Qwen3-Coder-Next Q6_K | 154/164 = 93.9% | 89–97% | 2.4 | 206 | 76 | 7.4 | 0 |

lite and medium were measured in the candidate bake-off (`candidates/results/`). Some of their requests stalled for 15-30 min while producing few tokens (unexplained host stalls), which lowers their end-to-end tok/s and inflates total minutes; per-request decode was otherwise ~95 (lite) and ~87 (medium) tok/s. Truncated = hit the 8192-token cap. Retired rows are the previous lite/medium models, kept for reference.
