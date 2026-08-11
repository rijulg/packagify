"""Makes the repository this repository's declaration says to fetch from.

Stands in for whatever really holds a folder worth fetching: a repository on a
host, private or not. The declaration is read rather than repeated, so the
example cannot drift from it, and the version it pins is the tag made here.
"""

import os
import shutil
import subprocess
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))

TOOLKIT = {
    "digits.py": '''"""Reads the number, and knows nothing of who imports it."""


def digits(number):
    return [int(character) for character in str(number) if character.isdigit()]
''',
    "checksum.py": '''"""Imports its sibling the way a script run from in here would."""

from digits import digits


def valid(number):
    doubled = [
        digit * 2 - 9 if digit * 2 > 9 else digit * 2
        for digit in digits(number)[-2::-2]
    ]
    return (sum(digits(number)[::-2]) + sum(doubled)) % 10 == 0
''',
}


def declared():
    with open(os.path.join(HERE, "pyproject.toml"), "rb") as declaration:
        return tomllib.load(declaration)["tool"]["packagify"]


def parsed(location):
    """The repository the declaration names, the version it pins, and the folder.

    Read the same way packagify reads it, which is the way pip reads a
    requirement.
    """
    url, _, fragment = location.removeprefix("git+").partition("#")
    url, _, version = url.rpartition("@")
    return url.removeprefix("file://"), version, fragment.removeprefix("subdirectory=")


def make(repository, folder, version):
    """A repository holding the folder, with the pinned version tagged on it."""
    shutil.rmtree(repository, ignore_errors=True)
    os.makedirs(os.path.join(repository, folder))
    for path, content in TOOLKIT.items():
        with open(os.path.join(repository, folder, path), "w") as file:
            file.write(content)

    def git(*arguments):
        # an identity for the commit, given here so that a machine without one
        # configured can still run the example
        subprocess.run(
            (
                "git",
                "-c",
                "user.email=example@packagify",
                "-c",
                "user.name=example",
                *arguments,
            ),
            cwd=repository,
            check=True,
            capture_output=True,
        )

    git("init", "--quiet")
    git("add", "--all")
    git("commit", "--quiet", "--message", "the toolkit")
    git("tag", version)


if __name__ == "__main__":
    for name, location in declared().items():
        repository, version, folder = parsed(location)
        make(repository, folder, version)
        print(f"made {name} at {repository} tagged {version}")
