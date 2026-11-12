"""Inventory every existing unittest suite in a disposable CI container."""
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "qualification-artefacts"
OUT.mkdir(exist_ok=True)
rows = []
suites = sorted((ROOT / "tests").glob("test_*.py"))
if not suites:
    raise SystemExit("No suites discovered")
for suite in suites:
    started = time.monotonic()
    timed_out = False
    with tempfile.TemporaryDirectory(prefix="mirivue-suite-") as folder:
        env = dict(os.environ, HOME=folder + "/home", XDG_CONFIG_HOME=folder + "/config",
                   XDG_DATA_HOME=folder + "/data", XDG_CACHE_HOME=folder + "/cache",
                   XDG_STATE_HOME=folder + "/state", XDG_RUNTIME_DIR=folder + "/runtime",
                   PYTHONPATH=str(ROOT) + os.pathsep + str(ROOT / "tests"),
                   QT_QPA_PLATFORM="offscreen", LANG="C.UTF-8", LC_ALL="C.UTF-8")
        for key in ("HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_CACHE_HOME",
                    "XDG_STATE_HOME", "XDG_RUNTIME_DIR"):
            Path(env[key]).mkdir(mode=0o700)
        logfile = OUT / (suite.stem + ".log")
        with logfile.open("wb") as output:
            child = subprocess.Popen(["dbus-run-session", "--", sys.executable, "-m",
                "unittest", "discover", "-s", "tests", "-p", suite.name, "-v"],
                cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                code = child.wait(timeout=120)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(child.pid, signal.SIGTERM)
                try:
                    child.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    os.killpg(child.pid, signal.SIGKILL)
                    child.wait()
                code = 124
            finally:
                # A bus, worker or GUI spawned by a finished suite must not leak
                # into the next suite. All members belong to this disposable group.
                try:
                    os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
        text = logfile.read_text(errors="replace")
        runs = re.findall(r"^Ran (\d+) tests? in ", text, re.M)
        skips = re.findall(r"^OK \(skipped=(\d+)\)", text, re.M)
        row = dict(suite=suite.name, code=code, timeout=timed_out,
                   tests=int(runs[-1]) if runs else 0,
                   skipped=int(skips[-1]) if skips else text.count(" ... skipped "),
                   duration=round(time.monotonic() - started, 3))
        if code != 0 or row["tests"] == 0:
            print(text[-10000:], flush=True)
        elif row["skipped"]:
            print("\\n".join(line for line in text.splitlines() if " ... skipped " in line), flush=True)
        rows.append(row)
        print(json.dumps(row), flush=True)
        (OUT / "rapport.json").write_text(json.dumps(dict(suites=rows), indent=2))
failed = [r for r in rows if r["code"] != 0 or r["tests"] == 0]
skipped = sum(r["skipped"] for r in rows)
summary = (f"Suites: {len(rows)}; tests: {sum(r['tests'] for r in rows)}; "
           f"failed/empty: {len(failed)}; skipped: {skipped}\n")
print(summary)
(OUT / "resume.txt").write_text(summary)
# A skipped test is evidence to qualify, never a complete stable validation.
raise SystemExit(1 if failed or skipped else 0)
