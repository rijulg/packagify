"""Uses two vendored folders as though they were ordinary packages.

They are called `legacy report tool v2` and `totals (unreleased)`, sit two
directories away, and could never be written as imports. There is no call to
packagify anywhere in this repository, and this file is a directory below the
`pyproject.toml` that declares them: the declaration is found by looking up
from here, so it is reached from anywhere in the repository.
"""

from packagify.reports.api import report
from packagify.totals.summing import total

QUARTER = ["north 120", "south 98", "east 143", "west 61"]


if __name__ == "__main__":
    print(report("Quarterly", QUARTER))
    print(f"total: {total(QUARTER)}")
