# Packagify

A packaging utility to access folders that aren't suitable to be used as packages, as python packages.

## How to use

``` python
from packagify import Packagify
package = Packagify("/home/workspace/my_package", "my_package")
object = package.import_module("module", ["object"])
object1, object2 = package.import_module("module", ["object1", "object2"])
```

The name is given rather than taken from the folder, and has nothing to do with where the folder
sits or what it is called, so a folder that could never be written as an import is loaded the same
as any other:

``` python
package = Packagify("/home/workspace/my package-1.2", "my_package")
```

It is the name the project holds for as long as it is loaded, so no two projects of a process can
be given the same one.

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
package into a temp dir and loads it through `Packagify`. The folder's contents are defined at the
top of [tests/test_e2e.py](tests/test_e2e.py).

In VSCode the tests are discovered by the Python extension (see `.vscode/settings.json`); pick the
interpreter that has `pytest` installed, then use the Testing panel or the `Test` task.
