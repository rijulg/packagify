"""The examples are run the way their README says to run them.

An example that is not run is an example that stops being true, so each one is
executed as its own program here and checked against what it prints.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
EXAMPLES = ROOT / "examples"


@pytest.fixture
def example():
    """Run an example the way the README says to, and hand back what it said."""

    def run(script):
        finished = subprocess.run(
            [sys.executable, str(EXAMPLES / script)],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT)},
            capture_output=True,
            text=True,
            check=False,
        )
        assert finished.returncode == 0, finished.stderr
        return finished.stdout

    return run


def test_the_declared_example_runs(example):
    """Two folders declared in one `pyproject.toml`, imported from a file a
    directory below it, with nothing installed and nothing called."""
    printed = example("declared_project/src/main.py")

    assert printed.startswith("Quarterly\n")
    assert "| north 120 |" in printed
    # the column is as wide as the longest row, so the sibling that does the
    # rendering was reached and run rather than merely found
    assert "| west 61   |" in printed
    # the second declared folder, which nothing but the declaration names
    assert printed.rstrip().endswith("total: 422")


def test_the_loaded_example_runs(example):
    """A folder with no repository of its own, named in a call instead."""
    printed = example("loaded_project/main.py")

    assert printed.strip() == "500g is 17.64oz"


def test_every_example_is_run_by_this_file():
    """A new example that nothing here runs is one that can quietly rot."""
    scripts = {
        str(path.relative_to(EXAMPLES))
        for path in EXAMPLES.rglob("*.py")
        if path.name == "main.py"
    }
    assert scripts == {
        os.path.join("declared_project", "src", "main.py"),
        os.path.join("loaded_project", "main.py"),
    }
