"""End to end tests loading a real folder that is not usable as a package."""

import builtins
import random
import sys
from textwrap import dedent

import pytest

from packagify import Packagify


class SampleProject:
    """
    Dynamically generated python project,
    used to prove that any directory can be imported using this module
    """

    __package_name: str
    location: str
    version: str

    def __init__(self):
        self.version = f"{random.randint(0, 99)}.{random.randint(0, 99)}"

    def helper(self):
        return """
            def greet(who):
                return f"hello {who}"
        """

    def main(self):
        return f"""
            from helper import greet

            VERSION = "{self.version}"

            def hello():
                return greet("world")
        """

    def write(self, parent):
        """Write the folder into `parent` and return where it landed."""
        self.__package_name = parent.name
        self.location = str(parent)
        for file in (self.helper, self.main):
            (parent / f"{file.__name__}.py").write_text(dedent(file()).lstrip())
        return self.location

    def forget(self):
        """Drop what a test imported out of the module cache.

        The package name is the temp dir's, so pytest already keeps tests from
        colliding; this is what stops the process from holding every project
        any test ever imported.
        """
        for name in list(sys.modules):
            if name == self.__package_name or name.startswith(
                f"{self.__package_name}."
            ):
                del sys.modules[name]


@pytest.fixture
def sample_project(tmp_path):
    """Write the folder under test to a temp dir and hand back the project.

    The project itself is yielded rather than just its location, so that a test
    can assert against the version that was generated for it.
    """
    project = SampleProject()
    project.write(tmp_path)
    yield project
    project.forget()


class TestImports:
    """Loads the sample project the way a consumer of the package would."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_project):
        self.project = sample_project
        self.package = Packagify(sample_project.location)

    def test_imports_a_single_object(self):
        hello = self.package.import_module("main", ["hello"])
        assert hello() == "hello world"

    def test_imports_multiple_objects(self):
        hello, version = self.package.import_module("main", ["hello", "VERSION"])
        assert hello() == "hello world"
        assert version == self.project.version

    def test_imports_a_whole_module(self):
        root = self.package.import_module("main")
        assert root.main.hello() == "hello world"

    def test_imports_a_module_that_imports_its_sibling(self):
        greet = self.package.import_module("helper", ["greet"])
        assert greet("there") == "hello there"


class TestImportMachinery:
    """Everything hijacked during the import has to be handed back afterwards."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_project):
        self.original_import = builtins.__import__
        self.original_syspath = list(sys.path)
        self.package = Packagify(sample_project.location)
        self.package.import_module("main", ["hello"])

    def test_restores_the_import_function(self):
        assert builtins.__import__ is self.original_import

    def test_restores_the_sys_path(self):
        assert sys.path == self.original_syspath

    def test_restores_the_sys_path_type(self):
        assert type(sys.path) is list


class TestMultipleInstances:
    """The same location can be loaded more than once in a single process."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_project):
        self.project = sample_project
        self.first = Packagify(sample_project.location)
        self.second = Packagify(sample_project.location)

    def test_both_instances_import_the_same_module(self):
        assert self.first.import_module("main", ["VERSION"]) == self.project.version
        assert self.second.import_module("main", ["VERSION"]) == self.project.version
