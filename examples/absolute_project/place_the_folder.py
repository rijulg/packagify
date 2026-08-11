"""Puts the folder where this repository's declaration says it lives.

Stands in for whatever really puts a folder outside a repository: a shared
mount, an unzipped vendor drop, a checkout someone made beside this one. The
declaration is read rather than repeated, so there is one place saying where
the folder goes and the example cannot drift from it.
"""

import os
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))

TOOLKIT = {
    "borders.py": '''"""Draws the lines, and knows nothing of who imports it."""


def line(width):
    return "=" * width
''',
    "formatting.py": '''"""Imports its sibling the way a script run from in here would."""

from borders import line


def banner(text):
    return f"{line(len(text))}\\n{text}\\n{line(len(text))}"
''',
}


def declared():
    with open(os.path.join(HERE, "pyproject.toml"), "rb") as declaration:
        return tomllib.load(declaration)["tool"]["packagify"]


if __name__ == "__main__":
    for name, location in declared().items():
        os.makedirs(location, exist_ok=True)
        for path, content in TOOLKIT.items():
            with open(os.path.join(location, path), "w") as file:
                file.write(content)
        print(f"placed {name} at {location}")
