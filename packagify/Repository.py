import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from urllib.parse import parse_qsl, urlsplit


class Repository:
    """A folder that lives in a git repository rather than on this machine.

    Named the way pip names one, so a declaration reads like a requirement:

    ```
    [tool.packagify]
    reports = "git+https://github.com/acme/toolkit.git@v1.2#subdirectory=tools/reports"
    ```

    The version is a tag, a branch, or a commit, and defaults to the default
    branch. `${NAME}` is read out of the environment, so a token for a private
    repository is not part of what gets committed. See the README for what is
    fetched when, and where it is kept.
    """

    PREFIX = "git+"
    CACHE = "PACKAGIFY_CACHE"
    # what git calls the default branch, and so what an unpinned location means
    DEFAULT_VERSION = "HEAD"
    # `${NAME}`, the form pip expands in a requirements file
    __VARIABLE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

    @classmethod
    def is_named_by(cls, location):
        """Whether `location` names a repository rather than a directory."""
        return location.startswith(cls.PREFIX)

    @classmethod
    def folder(cls, location):
        """The directory `location` names, fetching a repository if it names one.

        Every location goes through here and one that is already a directory is
        handed back as it is, so a declaration only reaches git for the folder an
        import actually asks for.
        """
        if not cls.is_named_by(location):
            return location
        return cls(location).__folder()

    def __init__(self, location):
        url, _, fragment = location[len(self.PREFIX) :].partition("#")
        self.__url, self.__version = self.__pinned(url)
        # a fragment holds fields rather than one value, as pip's does
        self.__subdirectory = dict(parse_qsl(fragment)).get("subdirectory", "")

    @staticmethod
    def __pinned(url):
        """The url, and the `@version` at the end of it that pins it.

        Split at the last `@` of the path rather than of the whole url, since a
        transport that carries a user, `ssh://git@host/project`, holds one of its
        own that pins nothing.
        """
        split = urlsplit(url)
        path, separator, version = split.path.rpartition("@")
        if not separator:
            return url, Repository.DEFAULT_VERSION
        return split._replace(path=path).geturl(), version

    def __folder(self):
        """The declared folder of the checkout, fetched if it is not here yet."""
        checkout = os.path.join(self.__cache(), self.__key())
        if not os.path.isdir(checkout):
            self.__fetch(checkout)
        folder = os.path.join(checkout, self.__subdirectory)
        if not os.path.isdir(folder):
            raise ModuleNotFoundError(
                f"Invalid subdirectory: {self.__subdirectory or '.'} of repository: "
                f"{self.__url} at version: {self.__version}"
            )
        return folder

    def __cache(self):
        """Where checkouts are kept.

        A checkout is machine state rather than something the repository holds,
        so it lives with the machine's other caches and not under the file that
        declared it. `PACKAGIFY_CACHE` moves it, which is also how one build gets
        a cache of its own.
        """
        override = os.environ.get(self.CACHE)
        if override:
            return override
        home = os.environ.get("XDG_CACHE_HOME") or os.path.join(
            os.path.expanduser("~"), ".cache"
        )
        return os.path.join(home, __package__)

    def __key(self):
        """The checkout's directory name, one per repository and version.

        Taken from the url as declared rather than as expanded, so a token never
        reaches the filesystem, and from no subdirectory, so one checkout serves
        every folder declared out of the same repository.
        """
        digest = hashlib.sha256(f"{self.__url}@{self.__version}".encode()).hexdigest()
        stem = os.path.basename(urlsplit(self.__url).path).removesuffix(".git")
        return f"{stem}-{digest[:16]}".lstrip("-")

    def __fetch(self, checkout):
        """Fetch the one version wanted, whole or not at all.

        Only that version is asked for and only its latest commit, since a folder
        to import is all that is wanted from the repository. It is fetched beside
        the checkout and moved in, so an interrupted fetch leaves nothing a later
        import would read as a finished one; a checkout that appears meanwhile is
        another process fetching the same version, whose copy is as good as this.
        """
        cache = os.path.dirname(checkout)
        os.makedirs(cache, exist_ok=True)
        staging = tempfile.mkdtemp(dir=cache, prefix=".fetching-")
        try:
            self.__git(staging, "init", "--quiet")
            self.__git(staging, "remote", "add", "origin", self.__expanded(self.__url))
            self.__git(
                staging, "fetch", "--quiet", "--depth", "1", "origin", self.__version
            )
            self.__git(staging, "checkout", "--quiet", "--detach", "FETCH_HEAD")
            self.__move(staging, checkout)
        finally:
            # whatever is left of a fetch that did not finish, and nothing at all
            # after one that did
            shutil.rmtree(staging, ignore_errors=True)

    @staticmethod
    def __move(staging, checkout):
        """Move a finished fetch to where the checkout belongs.

        Losing the move to another process means that process fetched the same
        version, so its checkout is this one and there is nothing left to do.
        """
        try:
            os.replace(staging, checkout)
        except OSError:
            if not os.path.isdir(checkout):
                raise

    def __git(self, directory, *arguments):
        """Run git in `directory`, and say what it was for if it fails."""
        try:
            finished = subprocess.run(
                ("git", *arguments),
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
                # an import has nobody to ask, so a repository the environment
                # holds no credentials for fails here rather than stopping to ask
                env={**os.environ, "GIT_TERMINAL_PROMPT": "0"},
            )
        except FileNotFoundError as error:
            raise ModuleNotFoundError(
                f"No git found to fetch repository: {self.__url} with"
            ) from error
        if finished.returncode != 0:
            raise ModuleNotFoundError(
                f"Could not fetch version: {self.__version} of repository: {self.__url}: "
                f"{self.__scrubbed(finished.stderr.strip())}"
            )

    def __expanded(self, url):
        """The url with `${NAME}` replaced by what the environment holds.

        A credential belongs in the environment rather than in a declaration that
        is committed, which is how pip reads a requirement too. A name the
        environment does not hold is the declaration's fault, so it is named.
        """

        def value(match):
            name = match.group(1)
            if name not in os.environ:
                raise ModuleNotFoundError(
                    f"Undefined variable: {name} in repository: {url}"
                )
            return os.environ[name]

        return self.__VARIABLE.sub(value, url)

    def __scrubbed(self, message):
        """Whatever git said, with an expanded variable put back as its name.

        A token reaches git as part of the url, so git quoting the url back is
        enough to carry the token into a traceback.
        """
        for name in self.__VARIABLE.findall(self.__url):
            value = os.environ.get(name)
            if value:
                message = message.replace(value, f"${{{name}}}")
        return message
