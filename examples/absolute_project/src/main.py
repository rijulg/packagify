"""Uses a folder that is not in this repository at all.

Its path belongs to this machine rather than to the code, so the declaration
holds it and this file just writes the import.
"""

from packagify.shared.formatting import banner


if __name__ == "__main__":
    print(banner("from a shared drive"))
