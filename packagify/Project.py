import builtins
import importlib.abc
import importlib.util
import os
import sys
from importlib.machinery import ModuleSpec, PathFinder

from .Loader import Loader
from .SysPath import SysPath


class Project(importlib.abc.MetaPathFinder):
    """A project, as a finder of the modules it holds."""

    @classmethod
    def install(cls, name: str, location: str):
        """Install a finder for `name`, or return the one already installed.

        The name is dotted for a declared project, since those are held as
        modules of this package.
        """
        for finder in sys.meta_path:
            if isinstance(finder, cls) and finder.__name == name:
                if finder.__location != location:
                    # the first finder of a name is the one that answers for it,
                    # so a second project of that name would never be reached
                    raise ValueError(
                        f"Name: {name} is already taken by the project at: {finder.__location}"
                    )
                return finder
        if not os.path.isdir(location):
            raise ModuleNotFoundError(
                f"Invalid location: {location} provided for module: {name}"
            )
        project = cls(location=location, name=name)
        sys.meta_path.insert(0, project)
        return project

    def __init__(self, name: str, location: str):
        self.__location = location
        self.__name = name

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.__name:
            # the project itself: the directory, under the given name rather
            # than the one it happens to have
            spec = self.__spec_of_the_project(fullname)
        elif fullname.startswith(f"{self.__name}."):
            # a module of the project, searched for where the project keeps it
            spec = PathFinder.find_spec(
                fullname, list(path or [self.__location]), target
            )
        else:
            return None
        if spec is not None and hasattr(spec.loader, "exec_module"):
            spec.loader = Loader(
                loader=spec.loader,
                import_func=self.__import,
                new_path=SysPath(sys.path, self.__location),
            )
        return spec

    def __spec_of_the_project(self, fullname):
        """The project's directory, as the package it is imported as.

        Built rather than searched for, since the directory is not named after
        the project and need not be importable as a package at all.
        """
        init = os.path.join(self.__location, "__init__.py")
        if os.path.isfile(init):
            # a directory that is already a package is loaded as one
            return importlib.util.spec_from_file_location(
                fullname, init, submodule_search_locations=[self.__location]
            )
        # otherwise there is nothing to run, only modules to search
        spec = ModuleSpec(fullname, None, is_package=True)
        spec.submodule_search_locations = [self.__location]
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
