"""End to end tests loading a real folder that is not usable as a package."""

import builtins
import random
import sys
from pathlib import Path
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
    package_name: str
    location: str
    version: str

    def __init__(self):
        # A name of its own means the project is a package python has never
        # seen, so nothing it imports can be served out of the module cache
        # and no project has to be cleaned back out of it afterwards.
        self.name = f"sample_project_{uuid4().hex}"
        # The name the project is loaded under is never the one its directory
        # has, so that no test can pass on the two being the same.
        self.package_name = f"package_{uuid4().hex}"
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
            },
            {
                # a name of its own, so that reaching it through the package
                # that holds it is not the same as reaching the package
                "path": "submodule/deeper.py",
                "content": f"""
                    DEEPER_VERSION = "{self.version}"
                """
            },
            {
                "path": "uses_dotted_module.py",
                "content": """
                    from submodule.deeper import DEEPER_VERSION
                """
            },
            {
                "path": "imports_dotted_module.py",
                "content": """
                    import submodule.deeper

                    DEEPER_VERSION = submodule.deeper.DEEPER_VERSION
                """
            },
            {
                # a directory down, so no finder of the project answers for it
                "path": "vendor/vendored.py",
                "content": f"""
                    VERSION = "{self.version}"
                """
            },
            {
                "path": "uses_vendored.py",
                "content": f"""
                    import sys

                    sys.path.append("vendor")

                    from vendored import VERSION
                """
            },
            {
                # a name of its own, so that the module reaching it this way
                # cannot be served the one the relative path reached
                "path": "vendor/vendored_absolutely.py",
                "content": f"""
                    VERSION = "{self.version}"
                """
            },
            {
                "path": "uses_absolutely_vendored.py",
                "content": """
                    import os
                    import sys

                    sys.path.append(os.path.join(os.path.dirname(__file__), "vendor"))

                    from vendored_absolutely import VERSION
                """
            }
        ]

    def write(self, parent, directory=None):
        """Write the folder into `parent` and return where it landed.

        The folder is named after the project unless a name is asked for, so
        that a test can put it in a directory named however it likes.
        """
        location = parent / (directory or self.name)
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

    def write(directory=None):
        project = SampleProject()
        project.write(tmp_path, directory)
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
        self.package = Packagify(sample_project.location, sample_project.package_name)

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

    def test_imports_a_sibling_once_the_module_is_already_loaded(self):
        """A module of the project keeps its own import for as long as it lives,
        so an import it only reaches when called still finds its siblings."""
        hello_later = self.package.import_module("main", ["hello_later"])
        assert hello_later() == "hello later"

    def test_imports_a_module_of_a_package_of_the_project(self):
        """`from a.b import C` is served the project's `a.b`, and the object it
        asks for is the one on `b`, not the one on `a`."""
        version = self.package.import_module("uses_dotted_module", ["DEEPER_VERSION"])
        assert version == self.project.version

    def test_imports_a_package_of_the_project_by_its_module(self):
        """`import a.b` binds `a`, the same as it does anywhere else, so the
        module reaches `b` through the package that holds it."""
        version = self.package.import_module("imports_dotted_module", ["DEEPER_VERSION"])
        assert version == self.project.version

    def test_imports_through_a_relative_import(self):
        """A relative import (`from .submodule import X`) is one the interpreter
        already resolves against the package holding the module, so it is left
        to be imported as usual rather than served out of the project."""
        version = self.package.import_module("uses_submodule", ["VERSION"])
        assert version == self.project.version

    def test_imports_through_a_relative_path_the_module_appends(self):
        """A relative path a module appends to `sys.path` is meant as one under
        its own project. The module it reaches for that way is one no finder of
        the project answers for, so the appended path is the only way there."""
        version = self.package.import_module("uses_vendored", ["VERSION"])
        assert version == self.project.version

    def test_imports_through_an_absolute_path_the_module_appends(self):
        """An absolute path a module appends already points where it means to,
        so it is left as the module wrote it."""
        version = self.package.import_module("uses_absolutely_vendored", ["VERSION"])
        assert version == self.project.version


class TestNames:
    """The name a project is imported under is its own, not its directory's."""

    def test_imports_a_directory_that_could_not_be_named_as_a_package(self, sample_projects):
        """The directory is only where the project is kept, so a directory that
        could never be written as an import is loaded the same as any other."""
        project = sample_projects(directory="not a package-1.2")
        package = Packagify(project.location, project.package_name)
        assert package.import_module("main", ["VERSION"]) == project.version

    def test_imports_a_directory_that_holds_no_init(self, sample_project):
        """A directory with no `__init__.py` is the case this package is for,
        and it is the one every other test loads. The package the project is
        imported as is built for it, so the directory is what the project's
        modules are searched for under without there being anything to run."""
        assert not (Path(sample_project.location) / "__init__.py").exists()
        package = Packagify(sample_project.location, sample_project.package_name)
        root = package.import_module("main")
        assert root.__path__ == [sample_project.location]
        assert root.main.hello() == "hello world"

    def test_runs_the_init_of_a_directory_that_is_a_package(self, sample_project):
        """A directory that does hold an `__init__.py` means it to be run, and
        it is run as one of the project's own modules."""
        init = Path(sample_project.location) / "__init__.py"
        init.write_text("from helper import greet\n\nROOT = greet('root')\n")
        package = Packagify(sample_project.location, sample_project.package_name)
        assert package.import_module("main").ROOT == "hello root"

    def test_keeps_the_project_a_name_already_holds(self, sample_project):
        """Loading the same project under the same name twice is the one
        project, so nothing is installed a second time."""
        name = f"reused_{uuid4().hex}"
        once = Packagify(sample_project.location, name=name)
        installed = len(sys.meta_path)
        again = Packagify(sample_project.location, name=name)
        assert len(sys.meta_path) == installed
        assert once.import_module("main", ["VERSION"]) == sample_project.version
        assert again.import_module("main", ["VERSION"]) == sample_project.version

    def test_refuses_a_name_another_project_holds(self, sample_projects):
        """The first finder of a name is the one that answers for it, so a
        second project of that name would never be the one reached."""
        first, second = sample_projects(), sample_projects()
        name = f"taken_{uuid4().hex}"
        Packagify(first.location, name=name)
        with pytest.raises(ValueError, match=first.location):
            Packagify(second.location, name=name)

    def test_refuses_a_name_that_is_not_a_package_of_its_own(self, sample_project):
        with pytest.raises(ValueError, match="dotted.name"):
            Packagify(sample_project.location, name="dotted.name")


class TestMissingProjects:
    """A location that holds no project is not one."""

    def test_refuses_a_location_that_is_not_there(self, tmp_path):
        location = tmp_path / "not_a_project"
        with pytest.raises(ModuleNotFoundError, match=str(location)):
            Packagify(str(location), f"missing_{uuid4().hex}")

    def test_refuses_a_location_that_is_not_a_directory(self, tmp_path):
        location = tmp_path / "not_a_directory.py"
        location.write_text("")
        with pytest.raises(ModuleNotFoundError, match=str(location)):
            Packagify(str(location), f"not_a_directory_{uuid4().hex}")


class TestImportMachinery:
    """Everything hijacked during the import has to be handed back afterwards."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_project):
        self.original_import = builtins.__import__
        self.original_syspath = list(sys.path)
        self.package = Packagify(sample_project.location, sample_project.package_name)
        self.package.import_module("main", ["hello"])

    def test_restores_the_import_function(self):
        assert builtins.__import__ is self.original_import

    def test_restores_the_sys_path(self):
        assert sys.path == self.original_syspath

    def test_restores_the_sys_path_type(self):
        assert type(sys.path) is list

    def test_leaves_the_module_the_loader_it_would_have_had(self):
        """Only running the module is taken over, so everything else the loader
        answers for is still answered by the one the module would have had."""
        module = self.package.import_module("main")
        assert module.main.__loader__.get_filename() == module.main.__file__


class TestMultipleInstances:
    """More than one project can be loaded in a single process."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_projects):
        self.first = sample_projects()
        self.second = sample_projects()

    def test_each_instance_imports_its_own_project(self):
        first = Packagify(self.first.location, self.first.package_name)
        second = Packagify(self.second.location, self.second.package_name)
        assert first.import_module("main", ["VERSION"]) == self.first.version
        assert second.import_module("main", ["VERSION"]) == self.second.version

    def test_one_project_can_be_loaded_twice(self):
        """A name is what a project is reached by rather than what it is, so a
        directory answers under each of the names it is loaded under."""
        once = Packagify(self.first.location, f"once_{uuid4().hex}")
        again = Packagify(self.first.location, f"again_{uuid4().hex}")
        assert once.import_module("main", ["VERSION"]) == self.first.version
        assert again.import_module("main", ["VERSION"]) == self.first.version
