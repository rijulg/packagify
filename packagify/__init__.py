import builtins
import os
import sys
from uuid import uuid4
import importlib.abc
from importlib.machinery import PathFinder


class Packagify:
    """
    Used to load python projects that aren't suitable to be used as packages
    You can use this class as following:

    ```
    from packagify import Packagify
    package = Packagify("/home/workspace/my_package")
    object = package.import_module("module", ["object"])
    object1, object2 = package.import_module("module", ["object1", "object2"])
    ```
    This will allow you to import modules and objects from my_package as and where it exists.


    How this works:
    1. The project's directory goes on `sys.meta_path` as a finder for a package
    of its own name, so that its modules are imported as `<directory>.<module>`
    without the directory having to be importable from anywhere.

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

    def __init__(self, location):
        self.name = os.path.basename(location)
        _Project.install(location=location, name=self.name)

    def import_module(self, module, from_list=()):
        """Import a module of the project, or the objects named in from_list."""
        imported = builtins.__import__(f"{self.name}.{module}", fromlist=from_list)
        if not from_list:
            # equivalent to: `import X`
            return imported
        objects = tuple(getattr(imported, name) for name in from_list)
        if len(objects) > 1:
            # equivalent to: `from X import Y1, Y2`
            return objects
        else:
            # equivalent to: `from X import Y`
            return objects[0]


class _Project(importlib.abc.MetaPathFinder):
    """A project, as a finder of the modules it holds."""

    @classmethod
    def install(cls, name: str, location: str):
        """
        Idempotent installer
        if `Project` already exists in `sys.meta_path` then return that. 
        Otherwise, create an instance of the `Project` and add it to `sys.meta_path`.
        """
        for finder in sys.meta_path:
            if isinstance(finder, cls) and finder.__name == name:
                return finder
        if not os.path.isdir(location):
            raise ModuleNotFoundError(f"Invalid location: {location} provided for module: {name}")
        project = cls(location=location, name=name)
        sys.meta_path.insert(0, project)

    def __init__(self, name: str, location: str):
        self.__location = location
        self.__name = name

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.__name:
            # the project itself, found under its own directory's name
            path = [os.path.dirname(self.__location)]
        elif fullname.startswith(f"{self.__name}."):
            # a module of the project, searched for where the project keeps it
            path = list(path or [self.__location])
        else:
            return None
        spec = PathFinder.find_spec(fullname, path, target)
        if spec is not None and hasattr(spec.loader, "exec_module"):
            spec.loader = _Loader(
                loader=spec.loader,
                import_func=self.__import,
                new_path=_SysPath(sys.path, self.__location),
            )
        return spec

    def provides(self, name):
        """Whether the module `name` asks for is one of the project's own."""
        return self.find_spec(f"{self.__name}.{name.partition('.')[0]}") is not None

    def __import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """The `__import__` the project's own modules are run with."""
        if level > 0 or not self.provides(name):
            return builtins.__import__(name, globals, locals, fromlist, level)
        module = builtins.__import__(
            f"{self.__name}.{name}", globals, locals, fromlist, 0
        )
        if fromlist:
            return module
        # `import a.b` binds `a`, the same as it does anywhere else
        return sys.modules[f"{self.__name}.{name.partition('.')[0]}"]


class _SysPath(list):
    """A `sys.path` that reads an appended relative path as the project's."""

    def __init__(self, entries, location):
        super().__init__(entries)
        self.__location = location

    def append(self, entry):
        if not os.path.isabs(entry):
            entry = os.path.join(self.__location, entry)
        super().append(entry)

class _Loader(importlib.abc.Loader):
    """Runs a module of the project the way the module expects to be run.

    Everything but running the module is left to the loader the module would
    have been given otherwise.
    """

    def __init__(self,
        loader: importlib.abc.Loader,
        new_path: _SysPath,
        import_func: any,
    ):
        self.__loader = loader
        self.__builtins = dict(vars(builtins), __import__=import_func)
        self.__new_path = new_path

    def __getattr__(self, attribute):
        return getattr(self.__loader, attribute)

    def exec_module(self, module):
        # override sys.path and module.__builtins__ and load the module
        # then return sys.path to original
        path = sys.path
        try:
            sys.path = self.__new_path
            module.__dict__["__builtins__"] = self.__builtins
            self.__loader.exec_module(module)
        finally:
            sys.path = path
