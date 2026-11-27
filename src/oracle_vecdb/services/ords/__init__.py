##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

import pkgutil
import importlib
import inspect
from pathlib import Path

if __package__:
    from .runtime_compat import apply_runtime_compatibility
else:
    import importlib.util

    _runtime_compat_path = Path(__file__).with_name("runtime_compat.py")
    _runtime_compat_spec = importlib.util.spec_from_file_location(
        "_vecdb_dev_tools_runtime_compat", _runtime_compat_path
    )
    if _runtime_compat_spec is None or _runtime_compat_spec.loader is None:
        raise ImportError(f"Unable to load {_runtime_compat_path}")
    _runtime_compat = importlib.util.module_from_spec(_runtime_compat_spec)
    _runtime_compat_spec.loader.exec_module(_runtime_compat)
    apply_runtime_compatibility = _runtime_compat.apply_runtime_compatibility

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


if __package__:
    _recursive_import()
apply_runtime_compatibility()
