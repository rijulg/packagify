import builtins
import os
import sys
from importlib.abc import MetaPathFinder
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
        self.project = _Project.install(location)
        self.name = self.project.name
        self.location = self.project.location

    def import_module(self, module, from_list=()):
        """Import a module of the project, or the objects named in from_list."""
        imported = builtins.__import__(f"{self.name}.{module}", fromlist=from_list)
        if not from_list:
            return imported
        objects = tuple(getattr(imported, name) for name in from_list)
        return objects if len(objects) > 1 else objects[0]


class _Project(MetaPathFinder):
    """A project, as a finder of the modules it holds."""

    @classmethod
    def install(cls, location):
        """The project at `location`, on `sys.meta_path` if it wasn't already."""
        # an absolute location so that the project keeps being found from
        # anywhere, whatever directory the process moves on to
        location = os.path.abspath(location)
        for finder in sys.meta_path:
            if isinstance(finder, cls) and finder.location == location:
                return finder
        project = cls(location)
        sys.meta_path.insert(0, project)
        return project

    def __init__(self, location):
        self.location = location
        self.name = os.path.basename(location)
        if not os.path.isdir(location):
            raise ModuleNotFoundError(f"No module named {self.name!r}", name=self.name)
        self.builtins = dict(vars(builtins), __import__=self.__import)

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.name:
            # the project itself, found under its own directory's name
            path = [os.path.dirname(self.location)]
        elif fullname.startswith(f"{self.name}."):
            # a module of the project, searched for where the project keeps it
            path = list(path or [self.location])
        else:
            return None
        spec = PathFinder.find_spec(fullname, path, target)
        if spec is not None and hasattr(spec.loader, "exec_module"):
            spec.loader = _Loader(spec.loader, self)
        return spec

    def provides(self, name):
        """Whether the module `name` asks for is one of the project's own."""
        return self.find_spec(f"{self.name}.{name.partition('.')[0]}") is not None

    def __import(self, name, globals=None, locals=None, fromlist=(), level=0):
        """The `__import__` the project's own modules are run with."""
        if level or not self.provides(name):
            return builtins.__import__(name, globals, locals, fromlist, level)
        module = builtins.__import__(
            f"{self.name}.{name}", globals, locals, fromlist, 0
        )
        if fromlist:
            return module
        # `import a.b` binds `a`, the same as it does anywhere else
        return sys.modules[f"{self.name}.{name.partition('.')[0]}"]


class _Loader:
    """Runs a module of the project the way the module expects to be run.

    Everything but running the module is left to the loader the module would
    have been given otherwise.
    """

    def __init__(self, loader, project):
        self.loader = loader
        self.project = project

    def __getattr__(self, attribute):
        return getattr(self.loader, attribute)

    def exec_module(self, module):
        # a module carries its own builtins, so the project's import is the one
        # its code sees for as long as it lives, imports made after loading too
        module.__dict__["__builtins__"] = self.project.builtins
        path = sys.path
        sys.path = _SysPath(path, self.project.location)
        try:
            self.loader.exec_module(module)
        finally:
            sys.path = path


class _SysPath(list):
    """A `sys.path` that reads an appended relative path as the project's."""

    def __init__(self, entries, location):
        super().__init__(entries)
        self.location = location

    def append(self, entry):
        if not os.path.isabs(entry):
            entry = os.path.join(self.location, entry)
        super().append(entry)
