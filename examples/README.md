# Examples

Three working projects, one per way of naming a folder. Run them from the repository root:

```bash
PYTHONPATH=. python "examples/declared_project/src/main.py"
PYTHONPATH=. python examples/loaded_project/main.py

python examples/absolute_project/place_the_folder.py
PYTHONPATH=. python examples/absolute_project/src/main.py
```

`PYTHONPATH=.` is only needed because packagify isn't installed into this repository's environment; after `pip install packagify`, plain `python` works.

All three are run by [tests/test_examples.py](../tests/test_examples.py), so they can't quietly stop working.

## declared_project

A repository that declares the two folders it imports, which is all the setup there is:

```toml
[tool.packagify]
reports = "vendor/legacy report tool v2"
totals = "vendor/totals (unreleased)"
```

```python
from packagify.reports.api import report
from packagify.totals.summing import total
```

Locations are resolved against the `pyproject.toml` holding them, not the working directory, so the repository works from a fresh clone. The importing file is `src/main.py`, a directory below the declaration, since the declaration is found by looking upwards.

Neither folder could be written as an import — `legacy report tool v2` and `totals (unreleased)` — and the first one's modules import each other (`from renderer import render`) the way a script run from inside the folder would. That last part is what no amount of installing or path juggling fixes, and it's why packagify exists.

## absolute_project

The same declaration with an absolute location:

```toml
[tool.packagify]
shared = "/tmp/packagify-example-shared-toolkit"
```

A folder that lives nowhere near the repository — a shared mount, an unzipped vendor drop, a checkout beside this one — is declared the same way as one inside it, and `src/main.py` writes the same import either way.

Prefer a relative location when there is one: an absolute path is true of one machine rather than of the code, so committing it won't hold for anyone else. This example works around that by putting the folder there first — `place_the_folder.py` reads the declaration and creates what it names, standing in for whatever really puts a folder outside a repository. `/tmp` keeps it runnable on any posix machine; Windows would need a path of its own.

## loaded_project

A folder with no repository of its own to declare it, named in a call instead:

```python
packagify("/somewhere/acme toolkit 1.2", "acme")

from acme.scales import weigh
```

This reaches folders a declaration can't: another checkout, a shared drive, a path computed at runtime. The import comes after the call, since the name doesn't exist until then.

The name is top-level, so it's what the whole process imports under that name from then on — pick one nothing else answers for.
