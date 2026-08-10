"""End to end tests loading a real folder that is not usable as a package."""

import builtins
import sys

import pytest

from packagify import Packagify


@pytest.fixture
def sample_project(request):
    """Location of the folder under test, resolved against this test module."""
    return str(request.path.parent / "fixtures" / "sample_project")


class TestImports:
    """Loads the sample project the way a consumer of the package would."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_project):
        self.package = Packagify(sample_project)

    def test_imports_a_single_object(self):
        hello = self.package.import_module("main", ["hello"])
        assert hello() == "hello world"

    def test_imports_multiple_objects(self):
        hello, version = self.package.import_module("main", ["hello", "VERSION"])
        assert hello() == "hello world"
        assert version == "1.0"

    def test_imports_a_whole_module(self):
        # Without a from_list, __import__ hands back the root package rather
        # than the submodule, so the module is reached through the root package
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
        self.package = Packagify(sample_project)
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
        self.first = Packagify(sample_project)
        self.second = Packagify(sample_project)

    def test_both_instances_import_the_same_module(self):
        assert self.first.import_module("main", ["VERSION"]) == "1.0"
        assert self.second.import_module("main", ["VERSION"]) == "1.0"
