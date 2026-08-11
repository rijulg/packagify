"""End to end tests loading a real folder that is not usable as a package."""

import builtins
import random
import sys
from pathlib import Path
from textwrap import dedent
from uuid import uuid4

import pytest

from packagify import packagify


class SampleProject:
    """A generated project, deliberately not usable as a package."""

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
                """,
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
                """,
            },
            {
                "path": "submodule/__init__.py",
                "content": f"""
                    VERSION = "{self.version}"
                """,
            },
            {
                "path": "uses_submodule.py",
                "content": f"""
                    from .submodule import VERSION
                """,
            },
            {
                # a name of its own, so that reaching it through the package
                # that holds it is not the same as reaching the package
                "path": "submodule/deeper.py",
                "content": f"""
                    DEEPER_VERSION = "{self.version}"
                """,
            },
            {
                "path": "uses_dotted_module.py",
                "content": """
                    from submodule.deeper import DEEPER_VERSION
                """,
            },
            {
                "path": "imports_dotted_module.py",
                "content": """
                    import submodule.deeper

                    DEEPER_VERSION = submodule.deeper.DEEPER_VERSION
                """,
            },
            {
                # a directory down, so no finder of the project answers for it
                "path": "vendor/vendored.py",
                "content": f"""
                    VERSION = "{self.version}"
                """,
            },
            {
                "path": "uses_vendored.py",
                "content": f"""
                    import sys

                    sys.path.append("vendor")

                    from vendored import VERSION
                """,
            },
            {
                # a name of its own, so that the module reaching it this way
                # cannot be served the one the relative path reached
                "path": "vendor/vendored_absolutely.py",
                "content": f"""
                    VERSION = "{self.version}"
                """,
            },
            {
                "path": "uses_absolutely_vendored.py",
                "content": """
                    import os
                    import sys

                    sys.path.append(os.path.join(os.path.dirname(__file__), "vendor"))

                    from vendored_absolutely import VERSION
                """,
            },
        ]

    def write(self, parent, directory=None):
        """Write the folder into `parent` and return where it landed.

        Named after the project unless `directory` says otherwise, so a test can
        choose the directory name.
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
    """Write a folder under test per call, each in a directory of its own."""

    def write(directory=None):
        project = SampleProject()
        project.write(tmp_path, directory)
        return project

    return write


@pytest.fixture
def sample_project(sample_projects):
    """The single folder most tests need, handed back whole so a test can assert
    against the version generated for it."""
    return sample_projects()


class TestImports:
    """Loads the sample project the way a consumer would: ordinary imports.

    Each test uses a name of its own, since a name is only loaded once per
    process — a later caller gets the module cached for whoever took it first.
    """

    def test_imports_a_module_of_the_project(self, sample_project):
        packagify(sample_project.location, "imported_by_statement")

        import imported_by_statement.main

        assert imported_by_statement.main.hello() == "hello world"
        assert imported_by_statement.main.VERSION == sample_project.version

    def test_imports_the_objects_of_a_module(self, sample_project):
        packagify(sample_project.location, "imported_from_statement")

        from imported_from_statement.main import VERSION, hello

        assert hello() == "hello world"
        assert VERSION == sample_project.version

    def test_imports_a_sibling_once_the_module_is_already_loaded(self, sample_project):
        """A module keeps its own `__import__` for life, so an import reached
        only when called still finds its siblings."""
        packagify(sample_project.location, "imports_a_sibling_later")

        from imports_a_sibling_later.main import hello_later

        assert hello_later() == "hello later"

    def test_imports_a_module_of_a_package_of_the_project(self, sample_project):
        """`from a.b import C` is served the project's `a.b`, and takes `C` from
        `b` rather than `a`."""
        packagify(sample_project.location, "imports_a_dotted_module")

        from imports_a_dotted_module.uses_dotted_module import DEEPER_VERSION

        assert DEEPER_VERSION == sample_project.version

    def test_imports_a_package_of_the_project_by_its_module(self, sample_project):
        """`import a.b` binds `a` as it does anywhere else, so the module reaches
        `b` through the package holding it."""
        packagify(sample_project.location, "imports_a_dotted_package")

        from imports_a_dotted_package.imports_dotted_module import DEEPER_VERSION

        assert DEEPER_VERSION == sample_project.version

    def test_imports_through_a_relative_import(self, sample_project):
        """A relative import (`from .submodule import X`) is already resolved
        against the holding package, so it is left to import as usual."""
        packagify(sample_project.location, "imports_relatively")

        from imports_relatively.uses_submodule import VERSION

        assert VERSION == sample_project.version

    def test_imports_through_a_relative_path_the_module_appends(self, sample_project):
        """A relative path appended to `sys.path` means one under the project.
        No finder answers for the module it reaches, so that path is the only
        way there."""
        packagify(sample_project.location, "appends_a_relative_path")

        from appends_a_relative_path.uses_vendored import VERSION

        assert VERSION == sample_project.version

    def test_imports_through_an_absolute_path_the_module_appends(self, sample_project):
        """An absolute path already points where it means to, so it is left as
        the module wrote it."""
        packagify(sample_project.location, "appends_an_absolute_path")

        from appends_an_absolute_path.uses_absolutely_vendored import VERSION

        assert VERSION == sample_project.version


class TestNames:
    """The name a project is imported under is its own, not its directory's."""

    def test_imports_a_directory_that_could_not_be_named_as_a_package(
        self, sample_projects
    ):
        """The directory is only where the project is kept, so one that could
        never be written as an import loads the same as any other."""
        project = sample_projects(directory="not a package-1.2")
        packagify(project.location, "named_unlike_its_directory")

        from named_unlike_its_directory.main import VERSION

        assert VERSION == project.version

    def test_imports_a_directory_that_holds_no_init(self, sample_project):
        """A directory with no `__init__.py` is the case this package is for.
        Its package is built rather than found, so the modules are searched for
        under the directory with nothing to run."""
        assert not (Path(sample_project.location) / "__init__.py").exists()
        packagify(sample_project.location, "holds_no_init")

        import holds_no_init.main

        assert holds_no_init.__path__ == [sample_project.location]
        assert holds_no_init.main.hello() == "hello world"

    def test_runs_the_init_of_a_directory_that_is_a_package(self, sample_project):
        """A directory that does hold an `__init__.py` has it run, as one of the
        project's own modules."""
        init = Path(sample_project.location) / "__init__.py"
        init.write_text("from helper import greet\n\nROOT = greet('root')\n")
        packagify(sample_project.location, "runs_its_init")

        import runs_its_init

        assert runs_its_init.ROOT == "hello root"

    def test_keeps_the_project_a_name_already_holds(self, sample_project):
        """Loading the same project under the same name twice installs once."""
        packagify(sample_project.location, "keeps_its_name")
        installed = len(sys.meta_path)
        packagify(sample_project.location, "keeps_its_name")
        assert len(sys.meta_path) == installed

        from keeps_its_name.main import VERSION

        assert VERSION == sample_project.version

    def test_refuses_a_name_another_project_holds(self, sample_projects):
        """The first finder of a name answers for it, so a second project of
        that name would never be reached."""
        first, second = sample_projects(), sample_projects()
        name = f"taken_{uuid4().hex}"
        packagify(first.location, name)
        with pytest.raises(ValueError, match=first.location):
            packagify(second.location, name)

    def test_refuses_a_name_that_is_not_a_package_of_its_own(self, sample_project):
        with pytest.raises(ValueError, match="dotted.name"):
            packagify(sample_project.location, "dotted.name")


class TestMissingProjects:
    """A location that holds no project is not one."""

    def test_refuses_a_location_that_is_not_there(self, tmp_path):
        location = tmp_path / "not_a_project"
        with pytest.raises(ModuleNotFoundError, match=str(location)):
            packagify(str(location), f"missing_{uuid4().hex}")

    def test_refuses_a_location_that_is_not_a_directory(self, tmp_path):
        location = tmp_path / "not_a_directory.py"
        location.write_text("")
        with pytest.raises(ModuleNotFoundError, match=str(location)):
            packagify(str(location), f"not_a_directory_{uuid4().hex}")


class TestImportMachinery:
    """Everything hijacked during the import has to be handed back afterwards."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_project):
        """The interpreter before any module of the project runs, which is what
        it must look like again afterwards."""
        self.project = sample_project
        self.original_import = builtins.__import__
        self.original_syspath = list(sys.path)

    def test_restores_the_import_function(self):
        packagify(self.project.location, "restores_the_import")

        # the import is the thing that does the hijacking
        import restores_the_import.main  # noqa: F401

        assert builtins.__import__ is self.original_import

    def test_restores_the_sys_path(self):
        packagify(self.project.location, "restores_the_path")

        # the import is the thing that does the hijacking
        import restores_the_path.main  # noqa: F401

        assert sys.path == self.original_syspath

    def test_restores_the_sys_path_type(self):
        packagify(self.project.location, "restores_the_path_type")

        # the import is the thing that does the hijacking
        import restores_the_path_type.main  # noqa: F401

        assert type(sys.path) is list

    def test_leaves_the_module_the_loader_it_would_have_had(self):
        """Only execution is taken over; everything else is still answered by
        the loader the module would have had."""
        packagify(self.project.location, "keeps_its_loader")

        import keeps_its_loader.main

        loader = keeps_its_loader.main.__loader__
        assert loader.get_filename() == keeps_its_loader.main.__file__


class TestMultipleInstances:
    """More than one project can be loaded in a single process."""

    @pytest.fixture(autouse=True)
    def setup(self, sample_projects):
        self.first = sample_projects()
        self.second = sample_projects()

    def test_each_instance_imports_its_own_project(self):
        packagify(self.first.location, "first_of_two")
        packagify(self.second.location, "second_of_two")

        from first_of_two.main import VERSION as first
        from second_of_two.main import VERSION as second

        assert first == self.first.version
        assert second == self.second.version

    def test_one_project_can_be_loaded_twice(self):
        """A name is how a project is reached, not what it is, so a directory
        answers under every name it is loaded under."""
        packagify(self.first.location, "loaded_once")
        packagify(self.first.location, "loaded_again")

        from loaded_again.main import VERSION as again
        from loaded_once.main import VERSION as once

        assert once == self.first.version
        assert again == self.first.version
