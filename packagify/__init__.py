import builtins
import functools
import os
import sys
import tomllib
import importlib.abc
import importlib.util
from importlib.machinery import ModuleSpec, PathFinder
from pathlib import Path



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
    _Project.install(location=location, name=name)


class _Declared(importlib.abc.MetaPathFinder):
    """The projects a declaration holds, as modules of this package.

    A project the nearest declaring `pyproject.toml` above the importing file
    holds is imported as `packagify.<name>`, with nothing to install and nothing
    to call. The finder goes on the end of `sys.meta_path` rather than the front,
    so it only ever answers for a name that nothing else could.
    """
    DECLARATION = "pyproject.toml"
    PREFIX = f"{__name__}."
    # the files the import system runs while it answers an import statement,
    # which are never the file that wrote one. Held as files rather than as
    # module names so that every part of the machinery is covered, including the
    # ones a later python grows.
    __MACHINERY = (os.path.dirname(importlib.__file__) + os.sep, os.path.abspath(__file__))

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(self.PREFIX):
            return None
        directory = self.__calling_directory()
        location = self.__declarations(directory).get(fullname[len(self.PREFIX):])
        if location is None:
            # a name nothing declares, or a module of a project that is already
            # answered for by the finder installed for the project itself
            return None
        project = _Project.install(location=location, name=fullname)
        return project.find_spec(fullname, path, target)
    
    def __declarations(self, directory):
        """The projects the nearest declaration above `directory` holds.

        A `pyproject.toml` that declares nothing is not the declaration, since a
        repository holds one per package it publishes and only one of them is
        answering for the folders the repository imports.
        """
        for parent in (Path(directory), *Path(directory).parents):
            declared = self.__declared_at(parent)
            if declared is not None:
                return declared
        return {}

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def __declared_at(directory):
        """The projects the declaration in `directory` holds, or None if it holds
        no declaration at all.

        The locations are read as the declaring file means them, which is relative
        to the directory holding it rather than to wherever python was started.

        Read once per directory, the same as any other tool reads its
        configuration, so that an import costs nothing to answer twice. The
        result is shared between callers and so is never modified.
        """
        declaration = directory / _Declared.DECLARATION
        if not declaration.is_file():
            return None
        with declaration.open("rb") as file:
            declared = tomllib.load(file).get("tool", {}).get(__name__)
        if declared is None:
            return None
        return {
            name: os.path.join(directory, location)
            for name, location in declared.items()
        }

    def __calling_directory(self):
        """The directory of the file whose import statement is being answered."""
        frame = sys._getframe(1)
        while frame is not None:
            file = frame.f_globals.get("__file__")
            if file is not None and not os.path.abspath(file).startswith(self.__MACHINERY):
                return os.path.dirname(os.path.abspath(file))
            frame = frame.f_back
        # a caller with no file of its own, such as a REPL, means where it is run from
        return os.getcwd()  # pragma: no cover


class _Project(importlib.abc.MetaPathFinder):
    """A project, as a finder of the modules it holds."""

    @classmethod
    def install(cls, name: str, location: str):
        """
        Idempotent installer
        if `Project` already exists in `sys.meta_path` then return that.
        Otherwise, create an instance of the `Project` and add it to `sys.meta_path`.

        The name is dotted for a project that is declared rather than loaded by
        hand, since those are held as modules of this package.
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
            raise ModuleNotFoundError(f"Invalid location: {location} provided for module: {name}")
        project = cls(location=location, name=name)
        sys.meta_path.insert(0, project)
        return project

    def __init__(self, name: str, location: str):
        self.__location = location
        self.__name = name

    def find_spec(self, fullname, path=None, target=None):
        if fullname == self.__name:
            # the project itself, which is the directory under the project's
            # name rather than under the one the directory happens to have
            spec = self.__spec_of_the_project(fullname)
        elif fullname.startswith(f"{self.__name}."):
            # a module of the project, searched for where the project keeps it
            spec = PathFinder.find_spec(fullname, list(path or [self.__location]), target)
        else:
            return None
        if spec is not None and hasattr(spec.loader, "exec_module"):
            spec.loader = _Loader(
                loader=spec.loader,
                import_func=self.__import,
                new_path=_SysPath(sys.path, self.__location),
            )
        return spec

    def __spec_of_the_project(self, fullname):
        """The project's own directory, as the package the project is imported as.

        The spec is built rather than searched for, since the directory is not
        named after the project and need not be importable as a package at all.
        """
        init = os.path.join(self.__location, "__init__.py")
        if os.path.isfile(init):
            # a directory that is a package of its own is loaded as one
            return importlib.util.spec_from_file_location(
                fullname, init, submodule_search_locations=[self.__location]
            )
        # a directory that is not holds its modules and nothing else to run
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


# last, so that a declared project is only ever reached by a name that is not
# already something else the interpreter can import
sys.meta_path.append(_Declared())
