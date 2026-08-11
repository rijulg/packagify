import sys

from .Declared import Declared
from .Project import Project

def packagify(location, name):
    """
    Used to load python projects that aren't suitable to be used as packages
    You can use this class as following:

    ```
    from packagify import packagify
    packagify("/home/workspace/my_package", "my_package")

    import my_package.module
    from my_package.module import object
    from my_package.module import object1, object2
    ```
    This will allow you to import modules and objects from my_package as and where it exists.

    Loading the project is all there is to it: from then on its modules are
    reached by the import statements any other package's are. A name that is
    only known while the program runs has nothing to write those statements
    with, so it is imported with `importlib.import_module(f"{name}.module")`.


    The name the project is imported under is given, and has nothing to do with
    where the project sits or what its directory is called. It is the name the
    project holds for as long as it is loaded, so no two projects of a process
    can be given the same one.

    How this works:
    1. The project's directory goes on `sys.meta_path` as a finder for a package
    under the project's name, so that its modules are imported as
    `<name>.<module>` without the directory having to be importable from
    anywhere, or even having to be named like a package.

    2. Those modules are run by a loader that hands them an `__import__` of their
    own, so that the imports they write as though the interpreter ran from their
    own directory (`import sibling`) are served out of the project, and everything
    else is imported as usual.

    3. While a module of the project runs, a relative path it appends to
    `sys.path` is rewritten to sit under the project, since that is where it
    means to point.

    Nothing is installed into the interpreter at large: `builtins.__import__` is
    never replaced, and the finder only ever answers for the project's own name.
    """
    if "." in name:
        raise ValueError(f"Invalid name: {name}, a project is a package of its own")
    Project.install(location=location, name=name)


# last, so that a declared project is only ever reached by a name that is not
# already something else the interpreter can import
sys.meta_path.append(Declared())
