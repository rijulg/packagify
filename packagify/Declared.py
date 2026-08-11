import functools
import importlib
import importlib.abc
import os
import sys
import tomllib
from pathlib import Path

from .Project import Project
from .Repository import Repository

class Declared(importlib.abc.MetaPathFinder):
    """The projects a declaration holds, as modules of this package.

    A project named by the nearest declaring `pyproject.toml` above the importing
    file is imported as `packagify.<name>`, with nothing to install and nothing to
    call. This finder goes on the end of `sys.meta_path`, so it only answers for
    names nothing else could.
    """
    DECLARATION = "pyproject.toml"
    PACKAGE = __package__
    PREFIX = f"{PACKAGE}."
    # files the import system runs while answering an import, which are never the
    # file that wrote one. Matched by directory rather than module name so future
    # python versions stay covered, and the whole of this package rather than just
    # this module, since a project's own imports are answered through it.
    __MACHINERY = (
        os.path.dirname(importlib.__file__) + os.sep,
        os.path.dirname(os.path.abspath(__file__)) + os.sep,
    )

    def find_spec(self, fullname, path=None, target=None):
        if not fullname.startswith(self.PREFIX):
            return None
        directory = self.__calling_directory()
        location = self.__declarations(directory).get(fullname[len(self.PREFIX):])
        if location is None:
            # a name nothing declares, or a module of a project that is already
            # answered for by the finder installed for the project itself
            return None
        # a repository is fetched here rather than where the declaration is read,
        # so only the folder an import asks for is ever fetched
        project = Project.install(location=Repository.folder(location), name=fullname)
        return project.find_spec(fullname, path, target)

    def __declarations(self, directory):
        """The projects the nearest declaration above `directory` holds.

        A `pyproject.toml` without a `[tool.packagify]` table is skipped: a
        repository holds one per package it publishes, and only one of them
        declares the folders the repository imports.
        """
        for parent in (Path(directory), *Path(directory).parents):
            declared = self.__declared_at(parent)
            if declared is not None:
                return declared
        return {}

    @staticmethod
    @functools.lru_cache(maxsize=None)
    def __declared_at(directory):
        """The projects declared in `directory`, or None if it declares nothing.

        A location is resolved against the declaring file rather than the working
        directory; one that names a repository is left as it was written, since
        what it points at is not on this machine yet. Read once per directory, so
        answering an import twice costs nothing; the cached result is shared, so
        it is never modified.
        """
        declaration = directory / Declared.DECLARATION
        if not declaration.is_file():
            return None
        with declaration.open("rb") as file:
            declared = tomllib.load(file).get("tool", {}).get(Declared.PACKAGE)
        if declared is None:
            return None
        return {
            name: location if Repository.is_named_by(location)
            else os.path.join(directory, location)
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