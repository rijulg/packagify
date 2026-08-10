# Packagify

A packaging utility to access folders that aren't suitable to be used as packages, as python packages.

## How to use

``` python
from packagify import Packagify
package = Packagify("/home/workspace/my_package")
object = package.import_module("module", ["object"])
object1, object2 = package.import_module("module", ["object1", "object2"])
```

## How this works

1. This class overrides the import functionality of python while importing the module.

    1. When the package tries to import certain modules from it's directory assuming the script ran from there, we change the level of import from absolute to relative.

    2. If a module adds a system path (using sys.path.append) we change the path to reflect the location of the module relative to the location from where we are loading the entire pacakage.

2. After importing we revert back the functions to originals so that rest of the importing can work as is

## Development

Run the tests from the repository root:

``` bash
pipenv install
pipenv run pytest
```

The suite is end to end: it loads [tests/fixtures/sample_project](tests/fixtures/sample_project), a folder that
is deliberately not usable as a package, through `Packagify`.

In VSCode the tests are discovered by the Python extension (see `.vscode/settings.json`); pick the
interpreter that has `pytest` installed, then use the Testing panel or the `Test` task.
