import sys

from .Declared import Declared
from .Project import Project

def packagify(location, name):
    """Load the project at `location` so it can be imported as `name`.

    ```
    from packagify import packagify
    packagify("/home/workspace/my package-1.2", "my_package")

    import my_package.module
    from my_package.module import object
    ```

    Imports must come after the call, since the name does not exist until then;
    for a name only known at runtime, use `importlib.import_module`. The name is
    top level and unrelated to the directory's own, so no two projects of a
    process can share one. See the README for how this works.
    """
    if "." in name:
        raise ValueError(f"Invalid name: {name}, a project is a package of its own")
    Project.install(location=location, name=name)


# last, so that a declared project is only ever reached by a name that is not
# already something else the interpreter can import
sys.meta_path.append(Declared())
