# Packagify

A packaging utility to access folders that aren't suitable to be used as packages, as python packages.

## How to use

``` python
from packagify import Packagify
Packagify("/home/workspace/my_package", "my_package")

import my_package.module
from my_package.module import object
from my_package.module import object1, object2
```

Loading the folder is all there is to it: from then on its modules are reached by the import
statements any other package's are. A name that is only known while the program runs has nothing
to write those statements with, so it is imported the way any other computed name is:

``` python
import importlib

package = Packagify(location, name)
module = importlib.import_module(f"{package.name}.module")
```

The name is given rather than taken from the folder, and has nothing to do with where the folder
sits or what it is called, so a folder that could never be written as an import is loaded the same
as any other:

``` python
Packagify("/home/workspace/my package-1.2", "my_package")
```

It is the name the project holds for as long as it is loaded, so no two projects of a process can
be given the same one. It is a top level name like any other, so a folder loaded as `json` is what
the rest of the process imports under that name: pick one nothing else answers for.

A folder that sits inside a repository can be declared instead of loaded, in which case there is
nothing to install and nothing to call:

``` toml
[tool.packagify]
reports = "vendor/legacy report tool v2"
```

``` python
from packagify.reports.api import report
```

The declaration is the nearest `pyproject.toml` above the file writing the import, and the
locations in it are read relative to that file, so the repository works from a fresh clone.

## Examples

Two working folders, one per way of using packagify, in [examples/](examples/):

``` bash
PYTHONPATH=. python "examples/declared_project/src/main.py"
PYTHONPATH=. python examples/loaded_project/main.py
```

## How this works

1. The folder is registered as a [finder](https://docs.python.org/3/reference/import.html#finders-and-loaders) on `sys.meta_path`, under a package of the project's name, so its modules are imported as `<name>.<module>` without the folder having to be importable from anywhere, or even having to be named like a package. The package the name stands for is built from the folder rather than searched for, so the folder is reached under the project's name whatever it is called; a folder that holds an `__init__.py` still has it run.

2. Those modules are executed by a [loader](https://docs.python.org/3/reference/import.html#loaders) that hands them an `__import__` of their own, so that the imports they write as though the interpreter ran from their own directory (`import sibling`) are served out of the folder, and everything else is imported as usual. Since the import belongs to the module rather than to the interpreter, it keeps working for imports made after loading, such as one inside a function.

3. While a module of the folder runs, a relative path it appends to `sys.path` is rewritten to sit under the folder, since that is where it means to point.

Nothing is installed into the interpreter at large: `builtins.__import__` is never replaced, and the finder only ever answers for the folder's own name.

## Development

Run the tests from the repository root:

``` bash
pipenv install
pipenv run pytest
```

The suite is end to end: each test writes a small folder that is deliberately not usable as a
package into a temp dir, loads it through `Packagify`, and imports it with ordinary import
statements. The folder's contents are defined at the top of [tests/test_e2e.py](tests/test_e2e.py).

Each test loads its folder under a name of its own, since a statement can only be written against
a name that is written too, and a name is only ever loaded once in a process: whoever asked for it
after that would be served the module cached for the project that took it first.

In VSCode the tests are discovered by the Python extension (see `.vscode/settings.json`); pick the
interpreter that has `pytest` installed, then use the Testing panel or the `Test` task.
