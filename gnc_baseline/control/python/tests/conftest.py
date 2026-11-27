"""CTest supplies the binding directory; direct per-track pytest uses the debug preset."""
import os
from pathlib import Path
import pytest

from gnc_baseline.paths import repository_root
from gnc_baseline.control.controller import _load_binding

binding_dir = Path(os.environ.get("GNC_CONTROLLER_MODULE_DIR") or
                   repository_root(__file__) / "build/gnc-controller/debug/gnc_baseline/control").resolve()
# The native extension is a build output, not another Python source track.
_load_binding(binding_dir)


@pytest.fixture
def expected_binding_dir():
    return binding_dir
