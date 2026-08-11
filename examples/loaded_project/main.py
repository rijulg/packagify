"""Loads a folder that has no repository of its own to declare it.

Not every folder worth importing sits inside a project you control. Naming it in
a call reaches wherever a declaration cannot.
"""

import os

from packagify import packagify

TOOLKIT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "acme toolkit 1.2")

packagify(TOOLKIT, "acme")

# written after the call, since the name does not exist until the call is made
from acme.scales import weigh  # noqa: E402

if __name__ == "__main__":
    print(weigh(500))
