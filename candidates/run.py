#!/usr/bin/env python3
"""Run pinned local candidates sequentially. Never modifies production profiles."""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import random
import re
import shlex
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STAGES = ("gate", "bench", "humaneval", "smoke", "fixtures", "long")
AGENTS = ("copilot", "opencode", "claude", "codex", "qwen", "aider")
ID_PATTERN = re.compile(r"cand-[a-z0-9]+(?:-[a-z0-9]+)*")


class GateFailure(RuntimeError):
    """The loaded model did not satisfy the chat/tool contract."""


def save(path, value):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2) + "\n")
    tmp.replace(path)


def record_blocked(out, name, detail):
    out.mkdir(parents=True, exist_ok=True)
    summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {"name": name, "stages": {}}
    summary.update(status="blocked", error=detail["error"])
    save(summary_path, summary)
    save(out / "blocked.json", detail)


def command(argv, log, *, cwd=ROOT, timeout=1800, env=None):
    with log.open("a") as stream:
        stream.write("$ " + shlex.join(map(str, argv)) + "\n")
        stream.flush()
        with subprocess.Popen(list(map(str, argv)), cwd=cwd, env=env, stdout=stream,
                              stderr=subprocess.STDOUT, start_new_session=True) as proc:
            try:
                return proc.wait(timeout=timeout)
            except BaseException:
                # Agents can spawn shells; bound and clean up the whole child tree.
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(proc.pid, signal.SIGTERM)
                try:
                    proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    with contextlib.suppress(ProcessLookupError):
                        os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()
                raise


def checked(argv, log, **kwargs):
    rc = command(argv, log, **kwargs)
    if rc:
        raise RuntimeError(f"command exited {rc}; see {log}")


def profile(name):
    path = HERE / "profiles" / (name + ".env")
    # Read shell syntax with Bash, including the same per-machine override as wrappers.
    script = '. "$1"; [ ! -f "$2" ] || . "$2"; printf "%s\\0" "$MODEL_FILE" "$ALIAS" "$CTX" "$CACHE_K" "$CACHE_V" "$EXTRA_ARGS" "${CHAT_TEMPLATE:-}"'
    values = subprocess.check_output(["bash", "-c", script, "profile", str(path),
                                      str(path.with_suffix(".local.env"))]).decode().split("\0")[:-1]
    return dict(zip(("model", "alias", "context", "cache_k", "cache_v", "args", "template"), values))


class Client:
    def __init__(self, alias):
        self.alias = alias
        self.key = (ROOT / "run/api-key").read_text().strip()
        self.gate_trace = []

    def request(self, route, body):
        return urllib.request.Request("http://127.0.0.1:8080" + route,
                                      json.dumps(body).encode(),
                                      {"Authorization": "Bearer " + self.key,
                                       "Content-Type": "application/json"})

    def post(self, route, body):
        with urllib.request.urlopen(self.request(route, body), timeout=1800) as response:
            return json.load(response)

    def chat(self, messages, **kwargs):
        return self.post("/v1/chat/completions",
                         {"model": self.alias, "messages": messages, "max_tokens": 8192, **kwargs})


def gate(client):
    messages = [{"role": "user", "content": "Reply with exactly READY."}]
    reply = client.chat(messages)
    client.gate_trace.append({"chat": reply})
    choice = reply["choices"][0]
    if choice["finish_reason"] != "stop" or "READY" not in (choice["message"].get("content") or ""):
        raise GateFailure("chat did not return READY within the output budget")
    tool = {"type": "function", "function": {
        "name": "lookup", "description": "Look up a code. Call this to answer the user.",
        "parameters": {"type": "object", "properties": {"code": {"type": "string"}},
                       "required": ["code"], "additionalProperties": False}}}
    messages = [{"role": "user", "content": "Call lookup with code PING, then reply with its result. Do not answer without calling lookup."}]
    body = {"model": client.alias, "messages": messages, "max_tokens": 8192,
            "tools": [tool], "stream": True}
    calls = {}
    saw_done = False
    with urllib.request.urlopen(client.request("/v1/chat/completions", body), timeout=1800) as response:
        for raw in response:
            line = raw.decode().strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                saw_done = True
                break
            event = json.loads(data)
            client.gate_trace.append({"stream": event})
            if "error" in event:
                raise GateFailure(f"stream error: {event['error']}")
            for item in event.get("choices", []):
                for delta in item.get("delta", {}).get("tool_calls", []):
                    index = delta["index"]
                    call = calls.setdefault(index, {"id": "", "type": "function",
                                                     "function": {"name": "", "arguments": ""}})
                    if delta.get("id"):
                        call["id"] = delta["id"]
                    for key in ("name", "arguments"):
                        call["function"][key] += delta.get("function", {}).get(key, "")
    if not saw_done or len(calls) != 1:
        raise GateFailure("incomplete streaming response or expected one tool call")
    call = next(iter(calls.values()))
    try:
        args = json.loads(call["function"]["arguments"])
    except json.JSONDecodeError as exc:
        raise GateFailure("tool call arguments were not JSON") from exc
    if not call["id"] or call["function"]["name"] != "lookup" or args != {"code": "PING"}:
        raise GateFailure("streaming tool call had the wrong name, ID or arguments")
    messages.extend([
        {"role": "assistant", "content": None, "tool_calls": [call]},
        {"role": "tool", "tool_call_id": call["id"], "content": "Result: PONG"},
    ])
    reply = client.chat(messages, tools=[tool])
    client.gate_trace.append({"tool_result": reply})
    choice = reply["choices"][0]
    if choice["finish_reason"] != "stop" or "PONG" not in (choice["message"].get("content") or ""):
        raise GateFailure("multi-turn tool-result recovery failed")
    return {"passed": True, "chat": True, "streaming_tool": True, "tool_result": True}


def sample_memory():
    swap_text = subprocess.check_output(["sysctl", "-n", "vm.swapusage"], text=True)
    match = re.search(r"used\s*=\s*([\d.]+)([KMG])", swap_text)
    if not match:
        raise RuntimeError("cannot parse vm.swapusage")
    used = float(match[1]) * {"K": 1 / 1024, "M": 1, "G": 1024}[match[2]]
    pressure = int(subprocess.check_output(
        ["sysctl", "-n", "kern.memorystatus_vm_pressure_level"], text=True).strip())
    rss = 0
    pidfile = ROOT / "run/server.pid"
    if pidfile.exists():
        pid = pidfile.read_text().strip()
        if pid.isdecimal():
            result = subprocess.run(["ps", "-o", "rss=", "-p", pid], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                rss = int(result.stdout.strip()) / 1024
    return {"swap_mib": used, "pressure": pressure, "rss_mib": rss}


class MemoryMonitor:
    def __init__(self, path):
        self.path = path
        self.first = sample_memory()
        self.peak = dict(self.first)
        self.stop = threading.Event()
        self.errors = []
        if path.exists():
            previous = json.loads(path.read_text())
            self.first = previous["baseline"]
            self.errors.extend(previous["errors"])
            for key in self.peak:
                self.peak[key] = max(self.peak[key], previous["peak"][key])
        self.thread = threading.Thread(target=self.watch, daemon=True)

    def watch(self):
        while not self.stop.wait(2):
            try:
                point = sample_memory()
            except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
                self.errors.append(str(exc))
                return
            for key in point:
                self.peak[key] = max(self.peak[key], point[key])

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.stop.set()
        self.thread.join()
        point = sample_memory()
        for key in point:
            self.peak[key] = max(self.peak[key], point[key])
        save(self.path, {"baseline": self.first, "peak": self.peak,
                         "swap_growth_mib": max(0, self.peak["swap_mib"] - self.first["swap_mib"]),
                         "qualified": not self.errors and self.peak["pressure"] == 1
                         and self.peak["swap_mib"] <= self.first["swap_mib"],
                         "errors": self.errors})


def bench(settings, out):
    # Never benchmark a second copy while the server still holds the model.
    checked([ROOT / "llm.sh", "stop"], out / "server.log")
    argv = ["llama-bench", "-m", ROOT / settings["model"], "-ngl", "999",
            "-fa", "on", "-ctk", settings["cache_k"], "-ctv", settings["cache_v"],
            "-p", "512,8192,30000", "-n", "128", "-r", "3", "-o", "json"]
    # Keep JSON stdout parseable; backend initialization is written to stderr.
    with (out / "bench.raw.json").open("w") as output, (out / "bench.log").open("w") as errors:
        subprocess.run(list(map(str, argv)), stdout=output, stderr=errors, timeout=3600, check=True)
    records = json.loads((out / "bench.raw.json").read_text())
    decode = [r["avg_ts"] for r in records if r["n_prompt"] == 0 and r["n_gen"] == 128]
    if len(decode) != 1 or decode[0] <= 0:
        raise RuntimeError("benchmark did not produce exactly one tg128 measurement")
    lines = ["| Test | tok/s |", "|---|---:|"]
    for r in records:
        label = f"pp{r['n_prompt']}" if r["n_prompt"] else f"tg{r['n_gen']}"
        lines.append(f"| {label} | {r['avg_ts']:.2f} |")
    (out / "bench.md").write_text("\n".join(lines) + "\n")
    return {"decode_tps": decode[0], "repetitions": 3}


def fixture(directory, kind):
    """Build a broken scratch fixture from repository fixtures, never mutate originals."""
    source = ROOT / "fixtures" / (kind + "_oc")
    shutil.copytree(source, directory, dirs_exist_ok=True)
    if kind == "bugfix":
        (directory / "calc.py").write_text("def average(nums):\n    return sum(nums) / (len(nums) + 1)\n")
        test = "test_calc.py"
        prompt = "Fix average() in calc.py. Do not edit the test. Run python3 test_calc.py."
    elif kind == "multi":
        (directory / "fmt.py").write_text('def format_price(cents):\n    return f"${cents:.2f}"\n')
        (directory / "receipt.py").write_text(
            'from fmt import format_price\n\n'
            'def receipt(items):\n'
            '    return "\\n".join(f"{name}: {format_price(c)}" for name, c in items)\n')
        test = "test_all.py"
        prompt = ("Fix currency formatting in fmt.py and the missing total in receipt.py. "
                  "Do not edit the test. Run python3 test_all.py.")
    else:
        path = directory / "lru.py"
        text = path.read_text()
        needle = "        self.order.remove(key)\n        self.order.append(key)\n"
        if text.count(needle) != 1:
            raise RuntimeError("LRU fixture changed: cannot inject the controlled bug")
        path.write_text(text.replace(needle, "        pass\n", 1))
        test = "test_lru.py"
        prompt = "Fix the LRU cache bug in lru.py. Do not edit the test. Run python3 test_lru.py."
    return test, prompt


def sandbox(directory):
    # All agent and generated-test writes are confined to scratch, and inference stays local.
    path = str(directory.resolve())
    return (f'(version 1)(allow default)(deny file-write*)(deny network*)'
            f'(allow file-write* (subpath "{path}") (literal "/dev/null"))'
            '(allow network-outbound (remote ip "localhost:8080"))'
            '(allow network-bind (local ip "localhost:*"))'
            '(allow network-inbound (local ip "localhost:*"))')


def agent_command(agent, name, prompt):
    wrapper = ROOT / "bin" / (agent + "-local")
    if agent == "copilot":
        return [wrapper, "--offline", name, "-p", prompt, "--allow-all-tools", "--no-ask-user"]
    if agent == "opencode":
        return [wrapper, name, "run", prompt]
    if agent == "claude":
        return [wrapper, name, "-p", prompt, "--dangerously-skip-permissions"]
    if agent == "codex":
        # Already enclosed in our scratch-only OS sandbox; nested Seatbelt blocks edits.
        return [wrapper, name, "exec", "--skip-git-repo-check",
                "--dangerously-bypass-approvals-and-sandbox", prompt]
    if agent == "qwen":
        return [wrapper, name, "--yolo", "-p", prompt]
    return [wrapper, name, "--yes-always", "--no-git", "--no-pretty", "--message", prompt, "calc.py"]


def agent_environment(directory, name, settings):
    home = directory / "home"
    home.mkdir()
    tmp = directory / "tmp"
    tmp.mkdir()
    env = dict(os.environ)
    for key in list(env):
        if key.startswith(("ANTHROPIC_", "OPENAI_", "COPILOT_", "LOCAL_LLM_REMOTE",
                           "OPENCODE_", "QWEN_", "CLAUDE_")) or key in (
                               "NODE_OPTIONS", "HF_TOKEN", "GITHUB_TOKEN", "GH_TOKEN"):
            env.pop(key)
    env.update(HOME=str(home), TMPDIR=str(tmp), XDG_CONFIG_HOME=str(home / ".config"),
               XDG_DATA_HOME=str(home / ".local/share"), XDG_CACHE_HOME=str(home / ".cache"),
               COPILOT_HOME=str(home / ".copilot"), CLAUDE_CONFIG_DIR=str(home / ".claude"),
               CLAUDE_CODE_TMPDIR=str(tmp), CLAUDE_TMPDIR=str(tmp),
               PYTHONDONTWRITEBYTECODE="1", NO_COLOR="1", LOCAL_LLM_PRESTARTED="1")
    # Override generated files/config dirs so wrappers do not write outside the sandbox.
    env["LOCAL_LLM_RUN_DIR"] = str(home / "run")
    Path(env["LOCAL_LLM_RUN_DIR"]).mkdir()
    return env


def run_agent(agent, name, directory, prompt, test, out, settings):
    original = (directory / test).read_bytes()
    test_log = out.with_suffix(".test.log")
    policy = sandbox(directory)
    test_command = ["sandbox-exec", "-p", policy, "/usr/bin/python3", "-B", "-c",
                    f"import runpy,sys; sys.path.insert(0,{str(directory)!r}); runpy.run_path({test!r},run_name='__main__')"]
    if command(test_command, test_log, cwd=directory, timeout=30) == 0:
        raise RuntimeError("fixture already passes before agent run")
    if "AssertionError" not in test_log.read_text():
        raise RuntimeError(f"fixture failed for an infrastructure reason; see {test_log}")
    env = agent_environment(directory, name, settings)
    start = time.monotonic()
    try:
        rc = command(["sandbox-exec", "-p", policy, *agent_command(agent, name, prompt)],
                     out, cwd=directory, timeout=600, env=env)
        timed_out = False
    except subprocess.TimeoutExpired:
        rc, timed_out = None, True
    unchanged = (directory / test).is_file() and (directory / test).read_bytes() == original
    test_rc = command(test_command, test_log, cwd=directory, timeout=30)
    return {"agent": agent, "passed": rc == 0 and test_rc == 0 and unchanged,
            "exit_code": rc, "test_exit_code": test_rc, "test_unchanged": unchanged,
            "timeout": timed_out, "secs": round(time.monotonic() - start, 2)}


def agents(name, settings, out, full_fixtures=False):
    rows = []
    kinds = ("bugfix", "multi", "repair") if full_fixtures else ("bugfix",)
    agents_to_run = ("opencode", "copilot") if full_fixtures else AGENTS
    for kind in kinds:
        for agent in agents_to_run:
            label = ("fixture-" if full_fixtures else "smoke-") + kind + "-" + agent
            # Results retain logs, not mutable agent state.
            with tempfile.TemporaryDirectory(prefix="candidate-", dir=ROOT / "eval/tmp") as tmp:
                directory = Path(tmp).resolve()
                test, prompt = fixture(directory, kind)
                row = run_agent(agent, name, directory, prompt, test, out / (label + ".log"), settings)
                row["fixture"] = kind
                rows.append(row)
                print(f"{name}: {label} {'PASS' if row['passed'] else 'FAIL'}", flush=True)
    return {"passed": sum(row["passed"] for row in rows), "total": len(rows), "results": rows}


def long_context(client, settings):
    rng = random.Random(7)
    words = "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu".split()
    # Leave room for tokenizer/template differences while measuring at least 100k actual tokens.
    target = min(100128, int(settings["context"]) - 8192)
    facts = {"vault code": "7391-QX", "project codename": "BLUE HERON", "server port": "48213"}
    items = [f"{rng.choice(words)}{rng.randint(0, 9999)}" for _ in range(target // 2)]

    def text_for(count):
        part = items[:count]
        for depth, (key, value) in zip((0.1, 0.5, 0.9), facts.items()):
            part.insert(int(len(part) * depth), f"\nIMPORTANT FACT: the {key} is {value}.\n")
        return ("Document:\n" + " ".join(part) +
                "\nList the vault code, project codename and server port in one line.")

    # Tokenize the rendered chat, rather than guessing tokens from filler words.
    low, high, best = 1, len(items), ""
    while low <= high:
        mid = (low + high) // 2
        text = text_for(mid)
        rendered = client.post("/apply-template", {"messages": [{"role": "user", "content": text}],
                                                   "add_generation_prompt": True})["prompt"]
        count = len(client.post("/tokenize", {"content": rendered, "add_special": True})["tokens"])
        if count <= target:
            best = text
            low = mid + 1
        else:
            high = mid - 1
    if not best:
        raise RuntimeError("could not construct a context within the token budget")
    # Restart before calling this stage so its first request has no reused prompt prefix.
    runs = []
    for mode in ("cold", "warm"):
        start = time.monotonic()
        reply = client.chat([{"role": "user", "content": best}], temperature=0)
        answer = reply["choices"][0]["message"].get("content") or ""
        prompt_tokens = reply["usage"]["prompt_tokens"]
        runs.append({"mode": mode, "prompt_tokens": prompt_tokens,
                     "secs": round(time.monotonic() - start, 3),
                     "recall": sum(value.lower() in answer.lower() for value in facts.values()),
                     "answer": answer, "timings": reply.get("timings"),
                     "finish": reply["choices"][0]["finish_reason"]})
    return {"target_tokens": target, "runs": runs}


def identity(name, entry, settings):
    files = [HERE / "run.py", HERE / "pin.py", ROOT / "eval/run_humaneval.py",
             ROOT / "profile.sh", ROOT / "llm.sh", ROOT / "bin/_common.sh",
             HERE / "profiles" / (name + ".env"), ROOT / "eval/HumanEval.jsonl.gz",
             ROOT / "tools/package-lock.json"]
    files += sorted((ROOT / "bin").glob("*-local"))
    files += sorted((ROOT / "fixtures").glob("*/*.py"))
    override = HERE / "profiles" / (name + ".local.env")
    if override.exists():
        files.append(override)
    if settings["template"]:
        files.append(ROOT / settings["template"])
    version = subprocess.check_output(["llama-server", "--version"], stderr=subprocess.STDOUT, text=True).strip()
    hashes = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in files}
    data = {"entry": entry, "profile": settings, "runtime": version, "sources": hashes}
    return {**data, "fingerprint": hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()}


def ensure_server(name, out, restart=False):
    if restart:
        checked([ROOT / "llm.sh", "stop"], out / "server.log")
    checked([ROOT / "llm.sh", "switch", name], out / "server.log", timeout=660)


def run_candidate(name, entry, args):
    out = HERE / "results" / name
    out.mkdir(parents=True, exist_ok=True)
    settings = profile(name)
    if settings["alias"] != "local-" + name or settings["model"] != "models/" + Path(entry["files"][0]["file"]).name:
        raise RuntimeError("candidate model/alias must match its pinned manifest; only tune runtime settings")
    ident = identity(name, entry, settings)
    runfile = out / "run.json"
    previous = json.loads(runfile.read_text()) if runfile.exists() else None
    if previous and previous["fingerprint"] != ident["fingerprint"]:
        raise RuntimeError(f"{name}: inputs changed; archive {out.relative_to(ROOT)} before a new run")
    save(runfile, ident)
    if not args.no_download:
        checked([ROOT / "download.sh", name], out / "download.log", timeout=24 * 3600)
    else:
        for item in entry["files"]:
            path = ROOT / "models" / Path(item["file"]).name
            stamp = path.with_name("." + path.name + ".sha256")
            if not path.is_file() or path.stat().st_size != item["bytes"] or not stamp.is_file() or stamp.read_text().strip() != item["sha256"]:
                raise RuntimeError(f"unverified model file: {path.name}; run download.sh {name}")
    summary = {"name": name, "status": "running", "stages": {}}
    if (out / "summary.json").exists():
        summary = json.loads((out / "summary.json").read_text())
        summary["status"] = "running"
    save(out / "summary.json", summary)
    with MemoryMonitor(out / "memory.json"):
        for stage in STAGES:
            stagefile = out / (stage + (".summary.json" if stage == "bench" else ".json"))
            if stagefile.exists():
                cached = json.loads(stagefile.read_text())
                summary["stages"][stage] = cached
                if stage == "gate" and not summary["stages"][stage]["passed"]:
                    summary["status"] = "rejected"
                    break
                if stage != "humaneval" or cached["errors"] == 0:
                    continue
            if stage not in args.stages:
                continue
            print(f"{name}: starting {stage}", flush=True)
            if stage != "gate" and not summary["stages"].get("gate", {}).get("passed"):
                raise RuntimeError("a passing gate is required before running later stages")
            if stage == "bench":
                result = bench(settings, out)
            else:
                ensure_server(name, out, restart=stage == "long")
                client = Client(settings["alias"])
                if stage == "gate":
                    try:
                        result = gate(client)
                    except GateFailure as exc:
                        result = {"passed": False, "error": str(exc)}
                    except urllib.error.HTTPError as exc:
                        if exc.code not in (400, 422):
                            raise
                        result = {"passed": False, "error": f"chat/tool template HTTP {exc.code}: " + exc.read().decode()[:1000]}
                    finally:
                        save(out / "gate.responses.json", client.gate_trace)
                elif stage == "humaneval":
                    checked(["python3", ROOT / "eval/run_humaneval.py", name,
                             "--output", out / "humaneval.jsonl", "--retry-errors"], out / "humaneval.log",
                            timeout=24 * 3600)
                    rows = [json.loads(line) for line in (out / "humaneval.jsonl").read_text().splitlines()]
                    result = {"total": len(rows), "passed": sum(row["passed"] for row in rows),
                              "errors": sum(row["finish"] == "error" for row in rows),
                              "truncated": sum(row["finish"] == "length" for row in rows),
                              "median_secs": statistics.median(row["secs"] for row in rows)}
                elif stage in ("smoke", "fixtures"):
                    result = agents(name, settings, out, full_fixtures=stage == "fixtures")
                else:
                    result = long_context(client, settings)
            save(stagefile, result)
            summary["stages"][stage] = result
            save(out / "summary.json", summary)
            if stage == "gate" and not result["passed"]:
                summary["status"] = "rejected"
                break
        else:
            summary["status"] = "complete" if set(summary["stages"]) == set(STAGES) else "partial"
            if summary["stages"].get("humaneval", {}).get("errors"):
                summary["status"] = "incomplete"
    if (out / "blocked.json").exists():
        (out / "blocked.json").unlink()
    save(out / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*")
    parser.add_argument("--wave", type=int, choices=(1, 2, 3))
    parser.add_argument("--include-optional", action="store_true")
    parser.add_argument("--experimental", action="store_true")
    parser.add_argument("--no-download", action="store_true")
    parser.add_argument("--stages", default=",".join(STAGES),
                        help="Comma-separated stages; omitted stages stay unmeasured")
    parser.add_argument("--list", action="store_true", help="Print selected pinned candidates without running")
    args = parser.parse_args()
    args.stages = args.stages.split(",")
    if not set(args.stages) <= set(STAGES):
        parser.error(f"stages must be selected from {','.join(STAGES)}")
    entries = json.loads((HERE / "manifest.json").read_text())
    names = args.names or [name for name, entry in entries.items()
                           if (args.wave is None or entry["wave"] == args.wave)
                           and (not entry.get("optional") or args.include_optional)
                           and (not entry.get("experimental") or args.experimental)]
    for name in names:
        if not ID_PATTERN.fullmatch(name) or name not in entries:
            parser.error(f"unknown candidate: {name}")
        if entries[name].get("experimental") and not args.experimental:
            parser.error(f"{name} is experimental; requires --experimental")
    if args.list:
        for name in names:
            print(f"{name}\t{entries[name]['bytes']/1e9:.1f} GB\t{entries[name]['model']}")
        return
    if os.geteuid() == 0:
        parser.error("do not run as root")
    if not names:
        parser.error("no candidates selected")
    (ROOT / "run").mkdir(exist_ok=True)
    (ROOT / "eval/tmp").mkdir(exist_ok=True)
    with (ROOT / "run/candidates.lock").open("w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("another candidate run is active")
        status = subprocess.check_output([ROOT / "llm.sh", "status"], text=True)
        previous = None
        if status.startswith("running:"):
            previous = (ROOT / "run/server.profile").read_text().strip()
            client = Client("local-" + previous)
            with urllib.request.urlopen(urllib.request.Request(
                    "http://127.0.0.1:8080/slots",
                    headers={"Authorization": "Bearer " + client.key}), timeout=5) as response:
                if any(slot["is_processing"] for slot in json.load(response)):
                    parser.error("the current server is processing a request; refusing to interrupt it")
        failures = []
        try:
            for name in names:
                try:
                    result = run_candidate(name, entries[name], args)
                    if result["status"] == "incomplete":
                        failures.append(name)
                except (OSError, ValueError, KeyError, RuntimeError, urllib.error.URLError,
                        subprocess.SubprocessError) as exc:
                    failures.append(name)
                    out = HERE / "results" / name
                    detail = {"error": str(exc), "type": type(exc).__name__}
                    if isinstance(exc, urllib.error.HTTPError):
                        detail["response"] = exc.read().decode(errors="replace")[:8000]
                    record_blocked(out, name, detail)
                    print(f"{name}: BLOCKED: {exc}", file=sys.stderr, flush=True)
                finally:
                    server_log = ROOT / "run/server.log"
                    resident = ROOT / "run/server.profile"
                    if resident.exists() and resident.read_text().strip() == name and server_log.exists():
                        shutil.copyfile(server_log, HERE / "results" / name / "server-final.log")
                    checked([ROOT / "llm.sh", "stop"], ROOT / "run/candidates-stop.log")
                    subprocess.run(["python3", HERE / "score.py"], check=True)
        finally:
            if previous:
                checked([ROOT / "llm.sh", "switch", previous], ROOT / "run/candidates-restore.log", timeout=660)
        if failures:
            raise SystemExit("Blocked candidates: " + ", ".join(failures))


if __name__ == "__main__":
    main()
