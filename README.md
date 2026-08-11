# Packagify

Import folders that aren't usable as python packages — bad names, no `__init__.py`, modules that import each other as though the interpreter ran from inside the folder.

## How to use

A folder inside your repository is declared in `pyproject.toml`. Nothing to install, nothing to call:

```toml
[tool.packagify]
reports = "vendor/legacy report tool v2"
```

```python
from packagify.reports.api import report
```

The declaration is the nearest `pyproject.toml` above the importing file that holds a `[tool.packagify]` table; a nearer one without that table is skipped rather than treated as empty. Relative locations are resolved against the file declaring them, so the repository works from a fresh clone. Absolute locations are used as written.

A folder with no repository of its own is named in a call instead:

```python
from packagify import packagify

packagify("/somewhere/acme toolkit 1.2", "acme")

from acme.scales import weigh
```

The name is yours to pick and is unrelated to the folder's own. Imports must be written after the call, since the name doesn't exist until then. It's a top-level name like any other, so pick one nothing else answers for — a folder loaded as `json` is what the whole process gets for `json`. For a name only known at runtime, use `importlib.import_module(f"{name}.module")`.

## Examples

Three working projects in [examples/](examples/), one per way of naming a folder:

```bash
PYTHONPATH=. python "examples/declared_project/src/main.py"
PYTHONPATH=. python examples/loaded_project/main.py

python examples/absolute_project/place_the_folder.py
PYTHONPATH=. python examples/absolute_project/src/main.py
```

## How this works

1. The folder is registered as a [finder](https://docs.python.org/3/reference/import.html#finders-and-loaders) on `sys.meta_path` under the given name, so its modules import as `<name>.<module>`. The package is built from the folder rather than searched for, so the folder needn't be importable or even named like a package. An `__init__.py`, if present, still runs.

2. Its modules are executed by a [loader](https://docs.python.org/3/reference/import.html#loaders) that gives each one its own `__import__`, so `import sibling` is served out of the folder and everything else is imported as usual. The import belongs to the module, so it keeps working for imports made later — inside a function, say.

3. A relative path a module appends to `sys.path` is rewritten to sit under the folder, which is where it means to point.

Nothing is installed globally: `builtins.__import__` is never replaced, and each finder only answers for its own name.

## Development

```bash
pipenv install
pipenv run pytest
```

The suite is end to end: each test writes a folder that is deliberately not usable as a package into a temp dir, loads it, and imports it with ordinary import statements. The folder's contents are at the top of [tests/test_e2e.py](tests/test_e2e.py).

Each test uses a name of its own, since a name is only loaded once per process — a later caller would be served the module cached for whichever project took the name first.

In VSCode the tests are discovered by the Python extension (see `.vscode/settings.json`); pick the interpreter with `pytest` installed, then use the Testing panel or the `Test` task.
