import os

class SysPath(list):
    """A `sys.path` that reads an appended relative path as the project's."""

    def __init__(self, entries, location):
        super().__init__(entries)
        self.__location = location

    def append(self, entry):
        if not os.path.isabs(entry):
            entry = os.path.join(self.__location, entry)
        super().append(entry)