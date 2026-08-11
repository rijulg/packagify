# Examples

Two working folders, one per way of using packagify. Run them from the repository root:

``` bash
PYTHONPATH=. python "examples/declared_project/src/main.py"
PYTHONPATH=. python examples/loaded_project/main.py
```

`PYTHONPATH=.` is only needed because packagify is not installed into this repository's own
environment. A consumer who has run `pip install packagify` runs the same files with plain
`python`.

Both examples are run by [tests/test_examples.py](../tests/test_examples.py), so they cannot
quietly stop working.

## declared_project

A repository that declares the two folders it wants to import, which is all the setup there is:

``` toml
[tool.packagify]
reports = "vendor/legacy report tool v2"
totals = "vendor/totals (unreleased)"
```

``` python
from packagify.reports.api import report
from packagify.totals.summing import total
```

Nothing is installed and nothing is called. The declaration travels with the code, so the
repository works from a fresh clone, and the locations in it are read relative to the
`pyproject.toml` that holds them rather than to wherever python was started. The file doing the
importing is `src/main.py`, a directory below the declaration, since the declaration is found by
looking up from whichever file writes the import.

Neither folder could be written as an import — `legacy report tool v2` and `totals (unreleased)`
— and the first one's modules import each other (`from renderer import render`) the way a script
run from inside the folder would. That last part is the half no amount of installing or path
juggling can fix, and it is the reason packagify exists.

## loaded_project

A folder with no repository of its own to declare it, named in a call instead:

``` python
packagify("/somewhere/acme toolkit 1.2", "acme")

from acme.scales import weigh
```

This reaches folders a declaration cannot: another checkout, a shared drive, a path worked out
while the program runs. The import has to be written after the call, since the name does not
exist until the call is made.

The name is a top level one, so it is what the whole process imports under that name from then
on — pick one nothing else answers for.
