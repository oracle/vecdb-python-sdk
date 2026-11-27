##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

import importlib
import inspect
import pkgutil
from pathlib import Path

# Identify the current package's path
__path__ = [str(Path(__file__).parent)]


def _recursive_import():
    # walk_packages explores subdirectories recursively
    for loader, module_name, is_pkg in pkgutil.walk_packages(
        __path__, prefix=__name__ + "."
    ):
        try:
            # Dynamically import the module
            module = importlib.import_module(module_name)

            # Iterate through everything defined in that module
            for name, obj in inspect.getmembers(module):
                # Check if the member is a class defined in that module (not imported)
                if inspect.isclass(obj) and obj.__module__ == module_name:
                    # Add the class to the package's global namespace
                    globals()[name] = obj
        except Exception as e:
            print(f"Failed to import {module_name}: {e}")


_recursive_import()
