"""End to end tests loading a real folder that is not usable as a package."""

import builtins
import random
import sys
from textwrap import dedent
from uuid import uuid4

import pytest

from packagify import Packagify


class SampleProject:
    """
    Dynamically generated python project,
    used to prove that any directory can be imported using this module
    """

    __written: int = 0

    name: str
    location: str
    version: str

    def __init__(self):
        # A name of its own means the project is a package python has never
        # seen, so nothing it imports can be served out of the module cache
        # and no project has to be cleaned back out of it afterwards.
        self.name = f"sample_project_{uuid4().hex}"
        # The major is a running count so that no two projects can come out
        # holding the same version; the minor is rolled so that nothing can
        # quietly start passing against a hardcoded one.
        SampleProject.__written += 1
        self.version = f"{SampleProject.__written}.{random.randint(0, 99)}"

    def __files(self):
        return [
            {
                "path": "helper.py",
                "content": """
                    def greet(who):
                        return f"hello {who}"
                """
            },
            {
                "path": "main.py",
                "content": f"""
                    from helper import greet

                    VERSION = "{self.version}"

                    def hello():
                        return greet("world")

                    def hello_later():
                        from helper import greet

                        return greet("later")
                """
            },
            {
                "path": "submodule/__init__.py",
                "content": f"""
                    VERSION = "{self.version}"
                """
            },
            {
                "path": "uses_submodule.py",
                "content": f"""
                    from .submodule import VERSION
                """
            }
        ]

    def write(self, parent):
        """Write the folder into `parent` and return where it landed."""
        location = parent / self.name
        location.mkdir()
        for file in self.__files():
            file_path = location / file["path"]
            file_content = dedent(file["content"]).lstrip()
            file_path.parent.mkdir(exist_ok=True, parents=True)
            file_path.write_text(file_content)
        self.location = str(location)
        return self.location


@pytest.fixture
def sample_projects(tmp_path):
    """Write a folder under test per call.

    Each one lands in a folder of its own so that it is a package in its own
    right, separate from anything else the test asked for.
    """

    def write():
        project = SampleProject()
        project.write(tmp_path)
        return project

    return write


@pytest.fixture
def sample_project(sample_projects):
    """The one folder under test that most tests need.

    The project is handed back rather than just its location, so that a test
    can assert against the version that was generated for it.
    """
    return sample_projects()


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

    def test_imports_a_sibling_once_the_module_is_already_loaded(self):
        """A module of the project keeps its own import for as long as it lives,
        so an import it only reaches when called still finds its siblings."""
        hello_later = self.package.import_module("main", ["hello_later"])
        assert hello_later() == "hello later"

    def test_imports_through_a_relative_path_the_module_appends(self):
        """A relative path a module puts on `sys.path` is meant as its own
        project's, not as one of wherever the interpreter was started."""
        version = self.package.import_module("uses_submodule", ["VERSION"])
        assert version == self.project.version


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
    """More than one project can be loaded in a single process."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_projects):
        self.first = sample_projects()
        self.second = sample_projects()

    def test_the_projects_are_told_apart_by_their_version(self):
        assert self.first.version != self.second.version

    def test_each_instance_imports_its_own_project(self):
        first = Packagify(self.first.location)
        second = Packagify(self.second.location)
        assert first.import_module("main", ["VERSION"]) == self.first.version
        assert second.import_module("main", ["VERSION"]) == self.second.version

    def test_one_project_can_be_loaded_twice(self):
        once = Packagify(self.first.location)
        again = Packagify(self.first.location)
        assert once.import_module("main", ["VERSION"]) == self.first.version
        assert again.import_module("main", ["VERSION"]) == self.first.version
