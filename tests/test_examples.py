"""Runs the examples the way their README says to, and checks what they print.

An example nothing runs is one that quietly stops being true.
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
    """Run an example as the README says to, and hand back its output."""

    def run(script, **environment):
        finished = subprocess.run(
            [sys.executable, str(EXAMPLES / script)],
            cwd=ROOT,
            env={**os.environ, "PYTHONPATH": str(ROOT), **environment},
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


def test_the_absolute_example_runs(example):
    """A folder outside the repository, declared by its absolute path.

    It is placed where the declaration says before anything imports it."""
    placed = example("absolute_project/place_the_folder.py")
    assert placed.startswith("placed shared at ")

    printed = example("absolute_project/src/main.py")

    assert printed.splitlines() == ["=" * 19, "from a shared drive", "=" * 19]


def test_the_repository_example_runs(example, tmp_path):
    """A folder fetched out of a git repository, pinned to a tag.

    The repository is made before anything imports it, and it is fetched into a
    cache of this test's own rather than the machine's, so what the example prints
    came out of the repository as it is now."""
    made = example("repository_project/make_the_repository.py")
    assert made.startswith("made identifiers at ")
    assert made.rstrip().endswith("tagged v1.0")

    printed = example(
        "repository_project/src/main.py", PACKAGIFY_CACHE=str(tmp_path / "cache")
    )

    assert printed.splitlines() == [
        "4137 8947 1175 5904: valid",
        "4137 8947 1175 5905: invalid",
    ]


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
        os.path.join("absolute_project", "src", "main.py"),
        os.path.join("repository_project", "src", "main.py"),
    }
