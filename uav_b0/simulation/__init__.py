"""Alias the original G1 package: legacy b0.contract message identities must not fork."""
import sys
from importlib import import_module

_public = import_module("b0")
for _name in ("contract", "actuator", "imu", "plant", "quaternion"):
    sys.modules[f"{__name__}.{_name}"] = import_module(f"b0.{_name}")
sys.modules[__name__] = _public
