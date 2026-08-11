"""Folders imported out of a git repository rather than off this machine.

Every repository here is a real one, made in a temp directory and fetched over
`file://`, which is a transport like any other as far as the fetching goes. So
the tests do the work a real fetch does without a network to depend on, and the
cache is a temp directory too, so nothing already on the machine is read and
nothing a test fetches is left behind.
"""

import importlib.util
import os
import shutil
import subprocess
import sys
from textwrap import dedent
from types import SimpleNamespace
from uuid import uuid4

import pytest

from packagify import packagify
from packagify.Repository import Repository

# the folder a repository is fetched for: modules that import each other as
# though the interpreter ran from inside them, in a directory named as nothing
# python could import
TOOLKIT = {
    "tools/text tools/borders.py": """
        def line(width):
            return "=" * width
    """,
    "tools/text tools/formatting.py": """
        from borders import line

        def banner(text):
            return f"{line(len(text))}\\n{text}\\n{line(len(text))}"
    """,
    # a second folder of the same repository, so that what a checkout is keyed
    # on can be told apart from what is imported out of it
    "tools/numbers/counting.py": """
        def total(numbers):
            return sum(numbers)
    """,
}

BANNER = "==\nhi\n=="


@pytest.fixture(autouse=True)
def cache(tmp_path, monkeypatch):
    """Fetch into a cache of this test's own."""
    directory = tmp_path / "cache"
    monkeypatch.setenv(Repository.CACHE, str(directory))
    return directory


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
def origin(tmp_path):
    """A repository holding the folders, tagged and committed as a real one is."""
    directory = tmp_path / "acme toolkit.git"
    for path, content in TOOLKIT.items():
        file = directory / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(dedent(content).lstrip())

    def git(*arguments):
        return subprocess.run(
            ("git", *arguments), cwd=directory, check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "--quiet", "--initial-branch", "main")
    git("config", "user.email", "test@example.com")
    git("config", "user.name", "test")
    # a version can be a commit, which a server only hands one out of when it is
    # configured to, the same as the hosts that allow it
    git("config", "uploadpack.allowAnySHA1InWant", "true")
    git("add", "--all")
    git("commit", "--quiet", "--message", "the toolkit")
    git("tag", "v1.0")
    return SimpleNamespace(
        directory=directory,
        url=f"git+file://{directory}",
        commit=git("rev-parse", "HEAD"),
        text_tools="#subdirectory=tools/text tools",
        numbers="#subdirectory=tools/numbers",
    )


@pytest.fixture
def repository(tmp_path):
    """Write a repository that declares the folders it wants to import."""

    def write(declaration):
        written = tmp_path / "consumer"
        written.mkdir(exist_ok=True)
        (written / "pyproject.toml").write_text(dedent(declaration).lstrip())
        return written

    return write


@pytest.fixture
def run():
    """Write a file into the repository and run it, as its author would."""

    def write_and_run(written, source):
        file = written / "app.py"
        file.write_text(dedent(source).lstrip())
        spec = importlib.util.spec_from_file_location(f"consumer_{uuid4().hex}", file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    return write_and_run


@pytest.fixture
def fetches(monkeypatch):
    """Every fetch there was, so that a test can tell one from a checkout that was
    already here."""
    fetched = []
    run = subprocess.run

    def counting(arguments, **keywords):
        if "fetch" in arguments:
            fetched.append(arguments)
        return run(arguments, **keywords)

    monkeypatch.setattr(subprocess, "run", counting)
    return fetched


class TestFoldersOutOfARepository:
    """The location is a requirement of the kind pip takes, and that is all the
    setup there is: the folder is fetched by the import that wants it.

    Each test uses a name of its own, since a name is only loaded once per
    process — a later caller gets the module cached for whoever took it first.
    """

    def test_imports_a_folder_pinned_to_a_tag(self, origin):
        packagify(f"{origin.url}@v1.0{origin.text_tools}", "from_a_tag")

        from from_a_tag.formatting import banner

        # the sibling the folder imports by its own name was fetched with it
        assert banner("hi") == BANNER

    def test_imports_a_folder_pinned_to_a_commit(self, origin):
        packagify(f"{origin.url}@{origin.commit}{origin.text_tools}", "from_a_commit")

        from from_a_commit.formatting import banner

        assert banner("hi") == BANNER

    def test_imports_the_default_branch_when_nothing_pins_it(self, origin):
        """A location with no version means what a clone of it would check out."""
        packagify(f"{origin.url}{origin.text_tools}", "from_the_default_branch")

        from from_the_default_branch.formatting import banner

        assert banner("hi") == BANNER

    def test_imports_the_repository_itself_when_nothing_names_a_folder(self, origin):
        """No subdirectory means the whole of it, which is a folder like any other."""
        packagify(f"{origin.url}@v1.0", "the_whole_repository")

        from the_whole_repository.tools.numbers.counting import total

        assert total([1, 2]) == 3

    def test_imports_a_declared_folder(self, origin, repository, run):
        """What a repository declares rather than what a call names: the shape a
        consumer writes, with nothing to install and nothing to call.

        A location that names a repository is left as it was written rather than
        resolved against the declaring file, since it is not a path on this
        machine at all."""
        written = repository(f"""
            [tool.packagify]
            text = "{origin.url}@v1.0{origin.text_tools}"
        """)

        app = run(written, """
            from packagify.text.formatting import banner

            BANNER = banner("hi")
        """)

        assert app.BANNER == BANNER

    def test_expands_a_variable_out_of_the_environment(self, origin, monkeypatch):
        """A token for a private repository belongs in the environment rather than
        in a declaration that is committed, so `${NAME}` is read out of it.

        The variable stands where a host does, since that is where a credential
        for one goes."""
        monkeypatch.setenv("ORIGIN_HOST", str(origin.directory.parent))
        packagify(
            f"git+file://${{ORIGIN_HOST}}/{origin.directory.name}@v1.0{origin.text_tools}",
            "from_a_variable",
        )

        from from_a_variable.formatting import banner

        assert banner("hi") == BANNER

    def test_fetches_once_and_imports_out_of_the_checkout_after(self, origin, fetches):
        """A pinned version cannot change, so the second import of a process, and
        of every process after it, costs no fetch."""
        packagify(f"{origin.url}@v1.0{origin.text_tools}", "fetched_once")
        from fetched_once.formatting import banner

        packagify(f"{origin.url}@v1.0{origin.text_tools}", "fetched_once_again")

        from fetched_once_again.formatting import banner as also_banner

        assert banner("hi") == also_banner("hi") == BANNER
        assert len(fetches) == 1

    def test_shares_one_checkout_between_folders_of_the_same_repository(
        self, origin, fetches
    ):
        """The checkout is keyed on the repository and version and not on the
        folder, so a second folder out of the same one is already here."""
        packagify(f"{origin.url}@v1.0{origin.text_tools}", "shared_text_tools")
        packagify(f"{origin.url}@v1.0{origin.numbers}", "shared_numbers")

        from shared_numbers.counting import total
        from shared_text_tools.formatting import banner

        assert banner("hi") == BANNER
        assert total([1, 2, 3]) == 6
        assert len(fetches) == 1


class TestRepositoriesThatDoNotHold:
    """A location that names a repository, a version, or a folder that is not
    there. The declaration is at fault, so the error names what it asked for."""

    def test_refuses_a_version_that_is_not_there(self, origin):
        with pytest.raises(ModuleNotFoundError, match="version: v9.9"):
            packagify(f"{origin.url}@v9.9{origin.text_tools}", "a_missing_version")

    def test_refuses_a_repository_that_is_not_there(self, tmp_path):
        with pytest.raises(ModuleNotFoundError, match="nowhere"):
            packagify(f"git+file://{tmp_path / 'nowhere'}@v1.0", "a_missing_repository")

    def test_refuses_a_folder_the_repository_does_not_hold(self, origin):
        with pytest.raises(ModuleNotFoundError, match="tools/not there"):
            packagify(f"{origin.url}@v1.0#subdirectory=tools/not there", "a_missing_folder")

    def test_refuses_a_variable_the_environment_does_not_hold(self, monkeypatch):
        monkeypatch.delenv("NOT_IN_THE_ENVIRONMENT", raising=False)
        with pytest.raises(ModuleNotFoundError, match="NOT_IN_THE_ENVIRONMENT"):
            packagify("git+file://${NOT_IN_THE_ENVIRONMENT}/toolkit@v1.0", "an_unset_variable")

    def test_keeps_what_a_variable_held_out_of_what_it_reports(self, monkeypatch, tmp_path):
        """git quotes the url it could not reach, which is the url with the token
        in it, so what the environment held is put back as its name."""
        secret = f"t0ken-{uuid4().hex}"
        monkeypatch.setenv("A_TOKEN", secret)
        with pytest.raises(ModuleNotFoundError) as refused:
            packagify(f"git+file://{tmp_path}/${{A_TOKEN}}/toolkit@v1.0", "a_token")

        assert secret not in str(refused.value)
        assert "${A_TOKEN}" in str(refused.value)

    def test_leaves_a_message_alone_for_a_variable_that_held_nothing(
        self, monkeypatch, tmp_path
    ):
        """Putting an empty value back would put the name between every character
        of the message, so nothing is put back for it."""
        monkeypatch.setenv("AN_EMPTY_TOKEN", "")
        with pytest.raises(ModuleNotFoundError) as refused:
            packagify(f"git+file://{tmp_path}/${{AN_EMPTY_TOKEN}}nowhere@v1.0", "an_empty")

        # what git said about the url it was given, still readable
        assert str(tmp_path / "nowhere") in str(refused.value)

    def test_says_so_when_the_machine_has_no_git(self, origin, monkeypatch):
        def no_git(*arguments, **keywords):
            raise FileNotFoundError(2, "No such file or directory", "git")

        monkeypatch.setattr(subprocess, "run", no_git)
        with pytest.raises(ModuleNotFoundError, match="No git found"):
            packagify(f"{origin.url}@v1.0{origin.text_tools}", "no_git_at_all")

    def test_leaves_nothing_behind_when_a_fetch_does_not_finish(self, origin, cache):
        """A half fetched checkout that stayed would be read as a finished one by
        the next import, which would then import half a folder."""
        with pytest.raises(ModuleNotFoundError):
            packagify(f"{origin.url}@v9.9{origin.text_tools}", "an_unfinished_fetch")

        assert list(cache.iterdir()) == []


class TestCheckoutsThatRaceEachOther:
    """Two processes importing the same folder at once each fetch it, and one of
    them puts it in place second."""

    def test_imports_the_checkout_the_other_process_finished_first(
        self, origin, monkeypatch
    ):
        def lose_the_race(staging, checkout):
            shutil.copytree(staging, checkout)
            raise OSError(39, "Directory not empty")

        monkeypatch.setattr(os, "replace", lose_the_race)
        packagify(f"{origin.url}@v1.0{origin.text_tools}", "the_slower_of_the_two")

        from the_slower_of_the_two.formatting import banner

        assert banner("hi") == BANNER

    def test_refuses_a_checkout_it_could_not_put_in_place_at_all(self, origin, monkeypatch):
        """Nothing is there to have lost the race to, so the failure is real."""
        def fail(staging, checkout):
            raise OSError(13, "Permission denied")

        monkeypatch.setattr(os, "replace", fail)
        with pytest.raises(OSError, match="Permission denied"):
            packagify(f"{origin.url}@v1.0{origin.text_tools}", "never_in_place")


class TestWhereCheckoutsAreKept:
    """A checkout is machine state rather than something a repository holds, so
    it is kept with the machine's other caches. `PACKAGIFY_CACHE`, which the rest
    of these tests set, moves it."""

    def test_keeps_them_under_the_cache_home(self, origin, monkeypatch, tmp_path):
        monkeypatch.delenv(Repository.CACHE)
        monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
        packagify(f"{origin.url}@v1.0{origin.text_tools}", "in_the_cache_home")

        from in_the_cache_home import formatting

        assert formatting.__file__.startswith(str(tmp_path / "xdg" / "packagify"))

    def test_falls_back_to_the_home_cache(self, origin, monkeypatch, tmp_path):
        """A machine with no `XDG_CACHE_HOME` set has the directory it stands for
        all the same."""
        monkeypatch.delenv(Repository.CACHE)
        monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        packagify(f"{origin.url}@v1.0{origin.text_tools}", "in_the_home_cache")

        from in_the_home_cache import formatting

        assert formatting.__file__.startswith(
            str(tmp_path / "home" / ".cache" / "packagify")
        )
