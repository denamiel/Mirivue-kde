"""Tests synthetiques du filtre : aucun secret reel et aucun appel Anthropic."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    "diagnostic_sdk", Path(__file__).resolve().parents[1] / "packaging/diagnostic_claude_sdk.py")
diag = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diag)
SENTINEL = "SENTINEL_NE_JAMAIS_PUBLIER_12345"


class DiagnosticTests(unittest.TestCase):
    def run_report(self, messages, debug=""):
        with tempfile.TemporaryDirectory() as temp:
            execution, log = Path(temp) / "execution.json", Path(temp) / "debug.log"
            execution.write_text(json.dumps(messages), encoding="utf-8")
            log.write_text(debug, encoding="utf-8")
            return "\n".join(diag.report(execution, log))

    def test_no_untrusted_text_or_keys_are_emitted(self):
        output = self.run_report([
            {"type": SENTINEL, SENTINEL: SENTINEL},
            {"type": "result", "result": SENTINEL, "errors": [SENTINEL],
             "api_error": SENTINEL, "terminal_reason": SENTINEL,
             "api_error_status": SENTINEL},
        ], SENTINEL + "\nHTTP 401 " + SENTINEL)
        self.assertNotIn(SENTINEL, output)
        self.assertIn("SDK evenements autres : 1", output)
        self.assertIn("Journal HTTP possible : 401", output)

    def test_http_requires_integer_and_range(self):
        for invalid in (True, False, "429", 99, 600, 429.0):
            with self.subTest(value=invalid):
                output = self.run_report([{"type": "result", "api_error_status": invalid}])
                self.assertNotIn("SDK HTTP :", output)
        self.assertIn("SDK HTTP : 429", self.run_report(
            [{"type": "result", "api_error_status": 429}]))

    def test_missing_differs_from_empty(self):
        output = self.run_report([{"type": "result", "result": "", "errors": []}])
        self.assertIn("result : texte_vide", output)
        self.assertIn("errors : liste_vide", output)
        self.assertIn("api_error_status : absent", output)

    def test_session_limit_only_emits_fixed_category(self):
        output = self.run_report([{"type": "result",
                                  "result": "session limit " + SENTINEL}])
        self.assertIn("SDK indice : limitation", output)
        self.assertNotIn(SENTINEL, output)

    def test_malformed_and_oversized_inputs(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "data"
            path.write_text(SENTINEL, encoding="utf-8")
            output = "\n".join(diag.report(path, path))
            self.assertIn("json_invalide", output)
            self.assertNotIn(SENTINEL, output)
            with patch.object(diag, "MAX_BYTES", 4):
                self.assertEqual(diag.bounded_text(path)[1], "trop_volumineux")

    def test_cleanup_even_if_parser_fails(self):
        with tempfile.TemporaryDirectory() as temp:
            paths = [Path(temp) / name for name in
                     ("claude-execution-output.json", "claude-sdk-startup.log")]
            for path in paths:
                path.write_text(SENTINEL, encoding="utf-8")
            output = io.StringIO()
            with patch.dict(os.environ, {"RUNNER_TEMP": temp}), \
                 patch.object(diag, "report", side_effect=RuntimeError(SENTINEL)), \
                 contextlib.redirect_stdout(output):
                diag.main()
            self.assertTrue(all(not p.exists() for p in paths))
            self.assertNotIn(SENTINEL, output.getvalue())
            self.assertIn("analyse_impossible", output.getvalue())


if __name__ == "__main__":
    unittest.main()
