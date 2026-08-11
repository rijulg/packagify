"""Uses two vendored folders as though they were ordinary packages.

`legacy report tool v2` and `totals (unreleased)` sit two directories away and
could never be written as imports. Nothing in this repository calls packagify.
This file is a directory below the declaring `pyproject.toml`, which is found by
looking upwards and so works from anywhere in the repository.
"""

from packagify.reports.api import report
from packagify.totals.summing import total

QUARTER = ["north 120", "south 98", "east 143", "west 61"]


if __name__ == "__main__":
    print(report("Quarterly", QUARTER))
    print(f"total: {total(QUARTER)}")
