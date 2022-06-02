import builtins
import sys


class Packagify:
    """
    Used to load python projects that aren't suitable to be used as packages
    You can use this class as following:

    ```
    from packagify import Packagify
    package = Packagify("/home/workspace/my_package")
    object = package.import_module("module", ["object"])
    object1, object2 = package.import_module("module", ["object1", "object2"])
    ```
    This will allow you to import modules and objects from my_package as and where it exists.


    How this works:
    1. This class overrides the import functionality of python while importing the module.

        1.1. When the package tries to import certain modules from it's directory assuming
        the script ran from there, we change the level of import from absolute to relative.

        1.2. If a module adds a system path (using sys.path.append) we change the path to reflect
        the location of the module relative to the location from where we are loading the entire
        pacakage.

    2. After importing we revert back the functions to originals so that rest of the importing can work as is
    """

    def __init__(self, location):
        self.location = location
        parts = location.rsplit('/', 1)
        sys.path.append(parts[0])
        self.__package = __import__(parts[1])
        sys.path.remove(parts[0])
        self.__save_originals()

    def import_module(self, module, from_list=[]):
        self.__hijack()
        locs = locals()
        locs[self.__package.__name__] = self.__package
        name = f"{self.__package.__name__}.{module}"
        tmp = self.module_import_name(module, name, locs, from_list)
        self.__unhijack()
        if from_list:
            modules = ()
            for fl in from_list:
                modules += (getattr(tmp, fl),)
            if len(modules) > 1:
                return modules
            else:
                return modules[0]
        return tmp

    def module_import_name(self, module, name, locs, from_list):
        if tmp := self._try_import(name, locs, from_list):
            return tmp
        else:
            relative_path = self.location
            relative_subpath = module.split(".")[:-1]
            for subpath in relative_subpath:
                relative_path += f"/{subpath}"
                sys.path.append(relative_path)
                if tmp := self._try_import(name, locs, from_list):
                    delattr(self, "_end_exception")
                    self._end_exception = None
                    return tmp
        raise self._end_exception

    def _try_import(self, name, locs, from_list):
        try:
            return __import__(name=name, locals=locs, fromlist=from_list)
        except ModuleNotFoundError as exception:
            self._end_exception = exception
            return None

    def __save_originals(self):
        self.original_import = builtins.__import__
        self.original_syspath = sys.path

    def __hijack(self):
        builtins.__import__ = self.__import__
        sys.path = self.SysPath(sys.path, self.location)

    def __unhijack(self):
        builtins.__import__ = self.original_import
        sys.path = self.original_syspath

    def __import__(self, name, globals=None, locals=None, fromlist=None, level=None):
        params = {'level': 0}
        if globals is not None:
            params['globals'] = globals
        if locals is not None:
            params['locals'] = locals
        if fromlist is not None:
            params['fromlist'] = fromlist
        if level is not None:
            params['level'] = level

        try:
            module = self.original_import(name, **params)
        except:

            if name and locals and '__package__' in locals and '__file__' in locals and name in locals['__package__'] and self.__package.__name__ in locals['__file__']:
                locals['__package__'] = locals['__package__'].replace(
                    f'.{name}', '')
            if self.__package.__name__ not in name and self.__package.__name__ in locals['__package__']:
                params['level'] += 1
            module = self.original_import(name, **params)
        return module

    class SysPath(list):
        def __init__(self, args, location):
            list.__init__(self, args)
            self.location = location

        def append(self, item):
            if item[0] == '/':
                list.append(self, item)
            else:
                list.append(self, f"{self.location}/{item}")
