"""The behaviours of a declared project that an example cannot show.

What using a declaration looks like is in [examples/declared_project], which is
a repository that really works and is really run by `test_examples.py`. What is
left here is what an example is the wrong shape for: the ways a declaration
fails, and the promise that everything else imports exactly as it did before.

The one thing here that an example does cover is the plain success case, kept
because an example runs in a process of its own and so measures nothing.
"""

import sys
import importlib.util
from textwrap import dedent
from uuid import uuid4

import pytest

# a folder of the kind this package is for: its modules import each other as
# though the interpreter were run from inside it, which no path on `sys.path`
# and no name in a declaration can fix on their own
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
    """A declared project is cached under its name like any other module, so
    each test hands back the names it claimed for the next one to use."""
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
        """A repository that publishes packages of its own holds a
        `pyproject.toml` per package, and only one of them declares the folders
        the repository imports. A nearer file that declares nothing is passed
        over rather than taken as an empty declaration."""
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
        """A file that asks whether the project is there, rather than importing
        it, asks through importlib - which puts importlib's own frames between
        the question and the answer without making importlib the one asking."""
        written = repository(DECLARES_MY_APP, {"weird project 1.2": NOT_A_PACKAGE})

        app = run(written, "app.py", """
            import importlib.util

            FOUND = importlib.util.find_spec("packagify.my_app") is not None
        """)

        assert app.FOUND is True

    def test_leaves_every_other_import_alone(self, repository, run):
        """The finder is the last one asked, so a name anything else can answer
        for never reaches it, and a name nothing can still fails as usual."""
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
        """A location that was mistyped is one the declaration is answerable
        for, so it is named in what comes back rather than the import."""
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
        """Nothing above the file says anything about packagify, so there is
        nothing the name could have meant."""
        with pytest.raises(ModuleNotFoundError, match="packagify.my_app"):
            run(tmp_path, "app.py", "from packagify.my_app.main import hello\n")
