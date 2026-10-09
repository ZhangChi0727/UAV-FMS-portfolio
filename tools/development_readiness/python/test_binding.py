"""CTest-owned test for the pybind11 toolchain probe, not B0 behavior."""

import os
import sys
from pathlib import Path


def _load_probe():
    module_directory = os.environ.get("DEVELOPMENT_READINESS_MODULE_DIR")
    if not module_directory:
        raise RuntimeError("CTest did not provide DEVELOPMENT_READINESS_MODULE_DIR")
    sys.path.insert(0, str(Path(module_directory)))
    import development_readiness_probe  # pylint: disable=import-outside-toplevel

    return development_readiness_probe


def test_python_calls_the_linux_or_native_cxx_extension():
    probe = _load_probe()
    assert probe.add_for_probe(20, 22) == 42
    assert probe.cxx_language_level() >= 201703
