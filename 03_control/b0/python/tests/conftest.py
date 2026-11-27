"""CTest supplies the binding directory; direct per-track pytest uses the debug preset."""
import os
from pathlib import Path
import pytest

from uav_b0.paths import repository_root
from uav_b0.control.controller import _load_binding

binding_dir = Path(os.environ.get("B0_CONTROLLER_MODULE_DIR") or
                   repository_root(__file__) / "build/b0-controller/debug/03_control/b0").resolve()
# The native extension is a build output, not another Python source track.
_load_binding(binding_dir)


@pytest.fixture
def expected_binding_dir():
    return binding_dir
