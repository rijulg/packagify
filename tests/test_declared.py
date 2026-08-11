"""Declared-project behaviours an example cannot show.

What a declaration looks like in use is [examples/declared_project], run by
`test_examples.py`. Left here is what an example is the wrong shape for: the
ways a declaration fails, and the promise that every other import is untouched.
The success case is repeated because an example runs in its own process and so
asserts nothing about this one.
"""

import sys
import importlib.util
from textwrap import dedent
from uuid import uuid4

import pytest

# a folder of the kind this package is for: its modules import each other as
# though the interpreter ran from inside it, which no `sys.path` entry and no
# name in a declaration fixes on its own
NOT_A_PACKAGE = {
    "helper.py": """
        def greet(who):
            return f"hello {who}"
    """,
    "main.py": """
        from helper import greet

        def hello():
            return greet("world")
    """,
}

DECLARES_MY_APP = """
    [tool.packagify]
    my_app = "weird project 1.2"
"""


@pytest.fixture(autouse=True)
def leave_the_declared_names_free():
    """Declared projects are cached like any other module, so each test hands
    back the names it claimed."""
    finders = list(sys.meta_path)
    modules = set(sys.modules)
    yield
    sys.meta_path[:] = finders
    for name in set(sys.modules) - modules:
        if name.startswith("packagify."):
            del sys.modules[name]


@pytest.fixture
def repository(tmp_path):
    """Write a repository that declares the folders it wants to import."""

    def write(declaration, folders):
        (tmp_path / "pyproject.toml").write_text(dedent(declaration).lstrip())
        for folder, files in folders.items():
            for path, content in files.items():
                file = tmp_path / folder / path
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(dedent(content).lstrip())
        return tmp_path

    return write


@pytest.fixture
def run():
    """Write a file into the repository and run it, as its author would."""

    def write_and_run(repository, path, source):
        file = repository / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(dedent(source).lstrip())
        spec = importlib.util.spec_from_file_location(f"consumer_{uuid4().hex}", file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return write_and_run


class TestDeclaredProjects:
    """The declaration is all the setup there is."""

    def test_imports_a_declared_project(self, repository, run):
        """The folder could not be named as a package, is not on `sys.path`,
        and was never installed. Its own modules still import each other."""
        written = repository(DECLARES_MY_APP, {"weird project 1.2": NOT_A_PACKAGE})

        app = run(written, "app.py", """
            from packagify.my_app.main import hello

            GREETING = hello()
        """)

        assert app.GREETING == "hello world"

    def test_looks_past_a_nearer_pyproject_that_declares_nothing(self, repository, run):
        """A repository publishing packages of its own holds a `pyproject.toml`
        per package, only one of which declares folders. A nearer file that
        declares nothing is skipped, not read as an empty declaration."""
        written = repository(DECLARES_MY_APP, {"weird project 1.2": NOT_A_PACKAGE})
        published = written / "packages" / "thing"
        published.mkdir(parents=True)
        (published / "pyproject.toml").write_text("[project]\nname = 'thing'\n")

        app = run(written, "packages/thing/app.py", """
            from packagify.my_app.main import hello

            GREETING = hello()
        """)

        assert app.GREETING == "hello world"

    def test_answers_a_name_the_machinery_looks_up_for_a_file(self, repository, run):
        """Asking whether the project exists goes through importlib, putting its
        frames between question and answer without making it the caller."""
        written = repository(DECLARES_MY_APP, {"weird project 1.2": NOT_A_PACKAGE})

        app = run(written, "app.py", """
            import importlib.util

            FOUND = importlib.util.find_spec("packagify.my_app") is not None
        """)

        assert app.FOUND is True

    def test_leaves_every_other_import_alone(self, repository, run):
        """The finder is asked last, so a name anything else answers for never
        reaches it, and a name nothing answers for still fails as usual."""
        written = repository(DECLARES_MY_APP, {"weird project 1.2": NOT_A_PACKAGE})

        app = run(written, "app.py", """
            import json

            STDLIB = json.__name__
            try:
                import not_a_module_anywhere
                MISSING = None
            except ModuleNotFoundError as error:
                MISSING = str(error)
        """)

        assert app.STDLIB == "json"
        assert app.MISSING == "No module named 'not_a_module_anywhere'"


class TestDeclarationsThatDoNotHold:
    """A declaration that does not say what the import asks for."""

    def test_refuses_a_name_the_declaration_does_not_hold(self, repository, run):
        written = repository(DECLARES_MY_APP, {"weird project 1.2": NOT_A_PACKAGE})

        with pytest.raises(ModuleNotFoundError, match="packagify.other_app"):
            run(written, "app.py", "from packagify.other_app.main import hello\n")

    def test_refuses_a_declaration_that_points_nowhere(self, repository, run):
        """A mistyped location is the declaration's fault, so the error names it
        rather than the import."""
        written = repository(
            """
            [tool.packagify]
            my_app = "not_where_it_says"
            """,
            {"weird project 1.2": NOT_A_PACKAGE},
        )

        with pytest.raises(ModuleNotFoundError, match="not_where_it_says"):
            run(written, "app.py", "from packagify.my_app.main import hello\n")

    def test_refuses_a_repository_that_declares_nothing(self, repository, run):
        written = repository("[project]\nname = 'nothing-declared'\n", {})

        with pytest.raises(ModuleNotFoundError, match="packagify.my_app"):
            run(written, "app.py", "from packagify.my_app.main import hello\n")

    def test_refuses_a_file_with_no_declaration_above_it_at_all(self, tmp_path, run):
        """Nothing above the file mentions packagify, so the name means nothing."""
        with pytest.raises(ModuleNotFoundError, match="packagify.my_app"):
            run(tmp_path, "app.py", "from packagify.my_app.main import hello\n")
