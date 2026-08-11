"""Adds up the rows the report tool renders.

A second folder, vendored separately, so the repository has two to declare.
"""


def total(rows):
    return sum(int(row.rsplit(" ", 1)[1]) for row in rows)
