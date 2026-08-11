import builtins
import importlib.abc
import sys

from .SysPath import SysPath

class Loader(importlib.abc.Loader):
    """Runs a module of the project the way the module expects to be run.

    Everything but running the module is left to the loader the module would
    have been given otherwise.
    """

    def __init__(self,
        loader: importlib.abc.Loader,
        new_path: SysPath,
        import_func: any,
    ):
        self.__loader = loader
        self.__builtins = dict(vars(builtins), __import__=import_func)
        self.__new_path = new_path

    def __getattr__(self, attribute):
        return getattr(self.__loader, attribute)

    def exec_module(self, module):
        # override sys.path and module.__builtins__ and load the module
        # then return sys.path to original
        path = sys.path
        try:
            sys.path = self.__new_path
            module.__dict__["__builtins__"] = self.__builtins
            self.__loader.exec_module(module)
        finally:
            sys.path = path