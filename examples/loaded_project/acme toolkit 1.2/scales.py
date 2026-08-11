"""The toolkit's own entry point.

`import units` is written the way a script run from inside this folder writes
it, so the folder is only usable when something arranges for that to work.
"""

import units


def weigh(grams):
    return f"{grams}g is {units.ounces(grams):.2f}oz"
