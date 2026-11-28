"""Disposable EDGE workspaces, independent of the caller's working directory."""
import os
from pathlib import Path


BUILD_DIR = Path(__file__).resolve().parents[1] / "build"


def configure_ultralytics():
    """Set the track-local settings directory before importing Ultralytics."""
    settings = BUILD_DIR / "ultralytics-settings"
    settings.mkdir(parents=True, exist_ok=True)
    os.environ["YOLO_CONFIG_DIR"] = str(settings)
    os.environ["YOLO_AUTOINSTALL"] = "false"
