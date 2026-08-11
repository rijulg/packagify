"""The entry point this tool has always been used through.

It imports its sibling the way a script run from inside this folder would,
which together with the folder's name is what makes it unusable as a package.
Nothing here knows or cares that it is being imported as `packagify.reports`.
"""

from renderer import render


def report(title, rows):
    return f"{title}\n{render(rows)}"
