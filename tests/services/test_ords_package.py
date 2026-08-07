##
## Copyright (c) 2026 Oracle and/or its affiliates.
## Licensed under the Universal Permissive License v 1.0 as shown at https://oss.oracle.com/licenses/upl/
##

import runpy
from pathlib import Path

import oracle_vecdb.services.ords as ords_pkg


def test_generated_ords_package_script_fallback_loads_runtime_compat():
    namespace = runpy.run_path(Path(ords_pkg.__file__))

    assert callable(namespace["apply_runtime_compatibility"])  # nosec B101


def test_generated_ords_package_recursive_import_reports_import_failures(
    monkeypatch, capsys
):
    def fake_walk_packages(path, prefix):
        yield None, "oracle_vecdb.services.ords.bad_module", False

    def fake_import_module(name):
        raise RuntimeError("boom")

    monkeypatch.setattr(ords_pkg.pkgutil, "walk_packages", fake_walk_packages)
    monkeypatch.setattr(ords_pkg.importlib, "import_module", fake_import_module)

    ords_pkg._recursive_import()

    assert (  # nosec B101
        "Failed to import oracle_vecdb.services.ords.bad_module: boom"
        in capsys.readouterr().out
    )
