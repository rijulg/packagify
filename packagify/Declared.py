import functools
import importlib
import importlib.abc
import os
import sys
import tomllib
from pathlib import Path

from .Project import Project

class Declared(importlib.abc.MetaPathFinder):
    """The projects a declaration holds, as modules of this package.

    A project the nearest declaring `pyproject.toml` above the importing file
    holds is imported as `packagify.<name>`, with nothing to install and nothing
    to call. The finder goes on the end of `sys.meta_path` rather than the front,
    so it only ever answers for a name that nothing else could.
    """
    DECLARATION = "pyproject.toml"
    PACKAGE = __package__
    PREFIX = f"{PACKAGE}."
    # the files the import system runs while it answers an import statement,
    # which are never the file that wrote one. Held as files rather than as
    # module names so that every part of the machinery is covered, including the
    # ones a later python grows, and every module of this package rather than
    # this one alone, since a project's own import is answered through them.
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
        project = Project.install(location=location, name=fullname)
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
        declaration = directory / Declared.DECLARATION
        if not declaration.is_file():
            return None
        with declaration.open("rb") as file:
            declared = tomllib.load(file).get("tool", {}).get(Declared.PACKAGE)
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