#!/usr/bin/env python3
"""Offline unit/integration tests; no model downloads or inference."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from io import BytesIO

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def module(name):
    spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


pin = module("pin")
run = module("run")
score = module("score")


class PinTests(unittest.TestCase):
    def file(self, filename):
        return {"rfilename": filename, "size": 123, "lfs": {"sha256": "a" * 64}}

    def test_exact_quant_not_prefix_or_projector(self):
        files = [self.file(name) for name in ("X-Q6_K.gguf", "X-Q6_K_XL.gguf",
                                             "mmproj-X-Q6_K.gguf", "draft-X-Q6_K.gguf")]
        self.assertEqual(pin.model_files(files, "Q6_K")[0]["file"], "X-Q6_K.gguf")

    def test_complete_shards(self):
        files = [self.file("Q6_K/X-Q6_K-00002-of-00002.gguf"),
                 self.file("Q6_K/X-Q6_K-00001-of-00002.gguf")]
        self.assertEqual(len(pin.model_files(files, "Q6_K")), 2)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            pin.model_files(files[:1], "Q6_K")

    def test_duplicate_models_rejected(self):
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            pin.model_files([self.file("a-Q6_K.gguf"), self.file("b-Q6_K.gguf")], "Q6_K")

    def test_missing_hash_rejected(self):
        f = self.file("X-Q6_K.gguf")
        del f["lfs"]
        with self.assertRaisesRegex(ValueError, "hash"):
            pin.model_files([f], "Q6_K")

    def test_generated_profiles_match_manifest(self):
        entries = json.loads((HERE / "manifest.json").read_text())
        names = set()
        for name, entry in entries.items():
            self.assertEqual((HERE / "profiles" / (name + ".env")).read_text(), pin.profile(name, entry))
            for f in entry["files"]:
                basename = Path(f["file"]).name
                self.assertNotIn(basename, names)
                names.add(basename)


class ScoreTests(unittest.TestCase):
    def complete(self):
        rows = [{"task_id": f"HumanEval/{i}", "passed": True, "finish": "stop", "secs": 2}
                for i in range(164)]
        return {
            "gate": {"passed": True}, "bench": {"decode_tps": 120},
            "humaneval": score.human_rows(rows),
            "smoke": {"total": 6, "passed": 6,
                      "results": [{"agent": agent, "passed": True} for agent in score.AGENTS]},
            "fixtures": {"total": 6, "passed": 6, "results": [
                {"agent": agent, "fixture": kind, "passed": True}
                for agent in ("copilot", "opencode") for kind in ("bugfix", "multi", "repair")]},
            "long": {"runs": [{"recall": 3, "prompt_tokens": 100001, "finish": "stop"}] * 2},
            "memory": {"qualified": True},
        }

    def test_speed_boundaries(self):
        self.assertEqual([score.speed_tier(x) for x in (None, 49.99, 50, 99.99, 100)],
                         ["unmeasured", "Deep", "Balanced", "Balanced", "Fast"])

    def test_missing_evidence_never_qualifies(self):
        labels, decision, _ = score.categorize({"thinking": False}, {})
        self.assertEqual((labels, decision), ([], "Pending"))

    def test_complete_candidate_never_auto_promoted(self):
        labels, decision, _ = score.categorize({"thinking": False}, self.complete())
        self.assertIn("agentic coding", labels)
        self.assertIn("quick edits", labels)
        self.assertIn("100k recall", labels)
        self.assertEqual(decision, "Keep as alternate")

    def test_partial_errors_duplicates_never_complete(self):
        row = {"task_id": "HumanEval/0", "passed": True, "finish": "stop", "secs": 1}
        for rows in ([row], [row] * 164):
            self.assertFalse(score.human_rows(rows)["complete"])
        rows = [dict(row, task_id=f"HumanEval/{i}") for i in range(164)]
        rows[4]["finish"] = "error"
        self.assertFalse(score.human_rows(rows)["complete"])

    def test_missing_agent_combinations_rejected(self):
        value = self.complete()
        value["smoke"]["results"][0] = value["smoke"]["results"][1]
        self.assertEqual(score.categorize({"thinking": True}, value)[1], "Incomplete")

    def test_swap_disqualifies(self):
        value = self.complete()
        value["memory"]["qualified"] = False
        self.assertEqual(score.categorize({"thinking": True}, value)[1], "Reject (memory qualification)")

    def test_blocked_is_not_model_rejection(self):
        self.assertEqual(score.categorize({}, {"blocked": {"error": "disk full"}})[1], "Blocked")


class HarnessTests(unittest.TestCase):
    def test_blocked_run_never_keeps_running_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            run.save(out / "summary.json", {"name": "cand-test", "status": "running",
                                            "stages": {"gate": {"passed": True}}})
            detail = {"error": "Compute error", "type": "HTTPError"}
            run.record_blocked(out, "cand-test", detail)
            summary = json.loads((out / "summary.json").read_text())
            self.assertEqual(summary["status"], "blocked")
            self.assertTrue(summary["stages"]["gate"]["passed"])
            self.assertEqual(json.loads((out / "blocked.json").read_text()), detail)

    def test_streamed_function_arguments_and_tool_recovery(self):
        class Client:
            alias = "local-test"
            gate_trace = []

            def __init__(self):
                self.answers = iter(("READY", "PONG"))

            def chat(self, messages, **kwargs):
                if len(messages) > 1:
                    self_test.assertEqual([m["role"] for m in messages],
                                          ["user", "assistant", "tool"])
                return {"choices": [{"finish_reason": "stop",
                                      "message": {"content": next(self.answers)}}]}

            def request(self, route, body):
                return body

        chunks = [
            {"index": 0, "id": "call-1", "function": {"name": "look", "arguments": '{"code":'}},
            {"index": 0, "function": {"name": "up", "arguments": '"PING"}'}},
        ]
        events = "".join("data: " + json.dumps({"choices": [{"delta": {"tool_calls": [chunk]}}]}) + "\n\n"
                         for chunk in chunks) + "data: [DONE]\n\n"
        self_test = self
        with patch.object(run.urllib.request, "urlopen", return_value=BytesIO(events.encode())):
            self.assertTrue(run.gate(Client())["passed"])
        with patch.object(run.urllib.request, "urlopen", return_value=BytesIO(b"data: [DONE]\n\n")):
            with self.assertRaises(run.GateFailure):
                run.gate(Client())

    def test_profile_resolution(self):
        script = '. ./profile.sh; resolve_profile "$1"; printf "%s" "$PROFILE_DIR"'
        for name in ("fast", "lite", "medium", "coder", "smart", "long", "max", "cand-ds-coder-lite"):
            r = subprocess.run(["bash", "-ec", script, "test", name],
                               cwd=ROOT, env={"ROOT": str(ROOT), "PATH": "/usr/bin:/bin"},
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("candidates/profiles" if name.startswith("cand-") else "/profiles", r.stdout)
        for name in ("cand-../fast", "cand-test/../../fast", "cand-X", "unknown", "cand-missing"):
            r = subprocess.run(["bash", "-ec", script, "test", name], cwd=ROOT,
                               env={"ROOT": str(ROOT), "PATH": "/usr/bin:/bin"}, capture_output=True)
            self.assertNotEqual(r.returncode, 0)

    def test_fixtures_initially_fail_and_originals_unchanged(self):
        paths = sorted((ROOT / "fixtures").glob("*/*.py"))
        originals = {path: path.read_bytes() for path in paths}
        with tempfile.TemporaryDirectory() as tmp:
            for kind in ("bugfix", "multi", "repair"):
                directory = Path(tmp) / kind
                test, _ = run.fixture(directory, kind)
                r = subprocess.run(["/usr/bin/python3", "-B", test], cwd=directory, capture_output=True)
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(b"AssertionError", r.stderr)
        self.assertEqual(originals, {path: path.read_bytes() for path in paths})

    def test_sandbox_blocks_outside_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            scratch = root / "scratch"
            scratch.mkdir()
            program = ("from pathlib import Path\n"
                       f"Path({str(scratch / 'ok')!r}).write_text('yes')\n"
                       "try:\n"
                       f"    Path({str(root / 'outside')!r}).write_text('no')\n"
                       "except PermissionError:\n    pass\n"
                       "else:\n    raise AssertionError('sandbox allowed outside write')\n")
            result = subprocess.run(["sandbox-exec", "-p", run.sandbox(scratch),
                                     "/usr/bin/python3", "-c", program], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr.decode())
            self.assertTrue((scratch / "ok").exists())
            self.assertFalse((root / "outside").exists())


if __name__ == "__main__":
    unittest.main()
