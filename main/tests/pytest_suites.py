"""Feature E25: pytest entry point for the two dependency-free FundTrail suites.

The suites stay plain scripts (runnable with no installs on an offline machine);
this wrapper lets `pytest` collect them too, with proper per-suite pass/fail:

    pytest main/tests/pytest_suites.py
"""

import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
MAIN = os.path.dirname(HERE)


def _run(script):
    proc = subprocess.run(
        [sys.executable, os.path.join(HERE, script)], cwd=MAIN, capture_output=True, text=True, timeout=600
    )
    assert proc.returncode == 0, (
        f"{script} failed (exit {proc.returncode}):\n{proc.stdout[-3000:]}\n{proc.stderr[-1000:]}"
    )


def test_smoke_suite():
    _run("smoke_test.py")


def test_access_control_suite():
    _run("test_access_control.py")
