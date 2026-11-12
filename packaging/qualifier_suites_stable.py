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
OUT = Path(os.environ.get('MIRIVUE_QUALIFICATION_OUTPUT', ROOT / 'qualification-artefacts'))
OUT.mkdir(parents=True, exist_ok=True)
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
            child = subprocess.Popen(["dbus-run-session", "--", sys.executable, "-c",
                "import faulthandler, runpy; faulthandler.dump_traceback_later(100); runpy.run_module('unittest', run_name='__main__')", "discover", "-s", "tests", "-p", suite.name, "-v"],
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
        row['covered_skips'] = 0
        # This one fake-application test intentionally rejects root. Run that
        # exact case as the disposable test account instead of dropping it.
        case = 'test_testlab_harness.FakeApplicationRuns.test_unconfined_write_outside_the_root_is_detected'
        if (suite.name == 'test_testlab_harness.py' and code == 0 and row['skipped'] == 1
                and 'test_unconfined_write_outside_the_root_is_detected' in text
                and 'en root, le harness refuse le mode sans confinement' in text):
            supplement_log = OUT / 'test_testlab_harness-nonroot.log'
            supplement_env = dict(os.environ, PYTHONPATH=str(ROOT) + os.pathsep + str(ROOT / 'tests'),
                                  QT_QPA_PLATFORM='offscreen', LANG='C.UTF-8', LC_ALL='C.UTF-8')
            for name in ('XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_CACHE_HOME',
                         'XDG_STATE_HOME', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS'):
                supplement_env.pop(name, None)
            with supplement_log.open('wb') as output:
                extra = subprocess.Popen(['runuser', '-u', os.environ['MIRIVUE_TESTLAB_USER'], '--',
                    'dbus-run-session', '--', sys.executable, '-m', 'unittest', case, '-v'],
                    cwd=ROOT, env=supplement_env, stdout=output, stderr=subprocess.STDOUT,
                    start_new_session=True)
                try:
                    extra_code = extra.wait(timeout=30)
                except subprocess.TimeoutExpired:
                    extra_code = 124
                finally:
                    try:
                        os.killpg(extra.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
                    extra.wait()
            extra_text = supplement_log.read_text(errors='replace')
            extra_runs = re.findall(r'^Ran (\d+) tests? in ', extra_text, re.M)
            row['supplemental'] = dict(case=case, code=extra_code,
                                       tests=int(extra_runs[-1]) if extra_runs else 0)
            if extra_code == 0 and extra_runs == ['1'] and 'skipped' not in extra_text:
                row['covered_skips'] = 1
            else:
                print(extra_text[-10000:], flush=True)
        if code != 0 or row["tests"] == 0:
            print(text[-10000:], flush=True)
        elif row["skipped"]:
            print("\n".join(line for line in text.splitlines() if " ... skipped " in line), flush=True)
        rows.append(row)
        print(json.dumps(row), flush=True)
        (OUT / "rapport.json").write_text(json.dumps(dict(suites=rows), indent=2))
failed = [r for r in rows if r["code"] != 0 or r["tests"] == 0]
skipped = sum(r["skipped"] for r in rows)
covered = sum(r['covered_skips'] for r in rows)
summary = (f"Suites: {len(rows)}; tests: {sum(r['tests'] for r in rows)}; "
           f"failed/empty: {len(failed)}; skipped: {skipped}; covered in another profile: {covered}\n")
print(summary)
(OUT / "resume.txt").write_text(summary)
# A skipped test is evidence to qualify, never a complete stable validation.
raise SystemExit(1 if failed or skipped != covered else 0)
