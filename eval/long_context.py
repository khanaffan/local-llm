#!/usr/bin/env python3
"""Long-context recall test: hides 3 facts at 10/50/90% depth in filler and asks for them.

Usage: long_context.py <alias> <filler_items> [--yarn-note TEXT]
Prints prompt tokens, cold/warm latency, prefill/decode speed, recall, server RSS and swap.
"""
import json, os, random, subprocess, sys, time, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
ALIAS, N = sys.argv[1], int(sys.argv[2])
KEY = open(os.path.join(ROOT, "..", "run", "api-key")).read().strip()
random.seed(7)
words = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu".split()
items = [f"{random.choice(words)}{random.randint(0, 9999)}" for _ in range(N)]
facts = {"vault code": "7391-QX", "project codename": "BLUE HERON", "server port": "48213"}
for depth, (k, v) in zip((0.1, 0.5, 0.9), facts.items()):
    items.insert(int(len(items) * depth), f"\nIMPORTANT FACT: the {k} is {v}.\n")
question = ("\n\nList the vault code, the project codename and the server port stated in the "
            "IMPORTANT FACT lines above. Answer in one line.")
body = {"model": ALIAS, "max_tokens": 512, "temperature": 0,
        "messages": [{"role": "user", "content": "Document:\n" + " ".join(items) + question}]}


def post():
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", json.dumps(body).encode(),
                                 {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    t = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=7200))
    return d, time.time() - t


for run in ("cold", "warm"):
    d, secs = post()
    ans = d["choices"][0]["message"]["content"] or ""
    tm = d["timings"]
    hits = sum(v.lower() in ans.lower() for v in facts.values())
    print(f"{run}: prompt_tokens={d['usage']['prompt_tokens']} total={secs:.1f}s "
          f"prefill={tm['prompt_per_second']:.0f} tok/s decode={tm['predicted_per_second']:.1f} tok/s "
          f"recall={hits}/3 answer={ans.strip()[:120]!r}", flush=True)

pid = open(os.path.join(ROOT, "..", "run", "server.pid")).read().strip()
rss = int(subprocess.run(["ps", "-o", "rss=", "-p", pid], capture_output=True, text=True).stdout) / 1048576
swap = subprocess.run(["sysctl", "-n", "vm.swapusage"], capture_output=True, text=True).stdout.strip()
print(f"server RSS {rss:.1f} GiB | swap: {swap}")
