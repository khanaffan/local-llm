#!/usr/bin/env python3
"""HumanEval pass@1 against the running llama-server profile.

Usage: run_humaneval.py <fast|medium|smart> [limit]
Resumable: problems already in results/<profile>.jsonl are skipped.
Generated code runs under macOS sandbox-exec (no network, writes only to a temp dir).
"""
import gzip, json, os, re, subprocess, sys, tempfile, time, urllib.request, urllib.error

ROOT = os.path.dirname(os.path.abspath(__file__))
PROFILE = sys.argv[1]
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else None
ALIAS = {"fast": "local-fast", "medium": "local-medium", "smart": "local-smart"}[PROFILE]
KEY = open(os.path.join(ROOT, "..", "run", "api-key")).read().strip()
OUT = os.path.join(ROOT, "results", f"{PROFILE}.jsonl")
os.makedirs(os.path.dirname(OUT), exist_ok=True)

PROMPT = ("Complete the following Python function. Reply with the complete function "
          "(including any needed imports) in a single ```python code block and no explanation.\n\n"
          "```python\n{p}\n```")


def chat(content):
    body = {"model": ALIAS, "max_tokens": 8192, "messages": [{"role": "user", "content": content}]}
    req = urllib.request.Request("http://127.0.0.1:8080/v1/chat/completions", json.dumps(body).encode(),
                                 {"Authorization": "Bearer " + KEY, "Content-Type": "application/json"})
    t = time.time()
    d = json.load(urllib.request.urlopen(req, timeout=1800))
    return d, time.time() - t


def extract(text):
    blocks = re.findall(r"```(?:python|py)?\s*\n(.*?)```", text or "", re.S)
    return blocks[-1] if blocks else (text or "")


def run_tests(task, completion):
    program = (task["prompt"] + "    pass\n\n" + completion + "\n\n" + task["test"]
               + f"\n\ncheck({task['entry_point']})\n")
    with tempfile.TemporaryDirectory(dir=os.path.join(ROOT, "tmp")) as td:
        td = os.path.realpath(td)
        path = os.path.join(td, "prog.py")
        open(path, "w").write(program)
        sb = ('(version 1)(allow default)(deny network*)(deny file-write*)'
              f'(allow file-write* (subpath "{td}") (literal "/dev/null"))')
        try:
            r = subprocess.run(["sandbox-exec", "-p", sb, "/usr/bin/python3", path], cwd=td,
                               capture_output=True, text=True, timeout=15,
                               env={"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1"})
            return r.returncode == 0, (r.stderr or "")[-300:]
        except subprocess.TimeoutExpired:
            return False, "timeout"


def main():
    os.makedirs(os.path.join(ROOT, "tmp"), exist_ok=True)
    with gzip.open(os.path.join(ROOT, "HumanEval.jsonl.gz"), "rt") as f:
        tasks = [json.loads(l) for l in f]
    if LIMIT:
        tasks = tasks[:LIMIT]
    done = set()
    if os.path.exists(OUT):
        done = {json.loads(l)["task_id"] for l in open(OUT)}
    for i, task in enumerate(tasks):
        if task["task_id"] in done:
            continue
        try:
            d, secs = chat(PROMPT.format(p=task["prompt"].rstrip()))
            m = d["choices"][0]
            ok, err = run_tests(task, extract(m["message"].get("content")))
            rec = {"task_id": task["task_id"], "passed": ok, "error": "" if ok else err,
                   "secs": round(secs, 2), "completion_tokens": d["usage"]["completion_tokens"],
                   "finish": m["finish_reason"], "reasoning_chars": len(m["message"].get("reasoning_content") or "")}
        except (urllib.error.URLError, KeyError, TimeoutError) as e:
            rec = {"task_id": task["task_id"], "passed": False, "error": f"request failed: {e}",
                   "secs": 0, "completion_tokens": 0, "finish": "error", "reasoning_chars": 0}
        with open(OUT, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"[{PROFILE}] {i+1}/{len(tasks)} {task['task_id']} {'PASS' if rec['passed'] else 'FAIL'} "
              f"{rec['secs']}s {rec['completion_tokens']}tok", flush=True)


main()
