"""Uses a folder that is not in this repository at all.

Nothing here says where the folder is, and nothing here could: it is outside
the repository, on a path that belongs to this machine rather than to the code.
The declaration holds that path, and this file just writes the import.
"""

from packagify.shared.formatting import banner


if __name__ == "__main__":
    print(banner("from a shared drive"))
