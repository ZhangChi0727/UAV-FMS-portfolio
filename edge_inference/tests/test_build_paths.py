import os
from pathlib import Path

from edge_inference.scripts import build_paths, compress_pruning, train_baseline


def test_edge_scratch_is_track_local():
    edge = Path(__file__).resolve().parents[1]
    assert build_paths.BUILD_DIR == edge / "build"
    assert compress_pruning.SCRATCH == edge / "build/day23-recovery-data"
    assert train_baseline.configure_ultralytics is compress_pruning.configure_ultralytics


def test_settings_are_created_outside_the_launch_directory(tmp_path, monkeypatch):
    scratch = tmp_path / "edge_inference/build"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(build_paths, "BUILD_DIR", scratch)
    monkeypatch.setenv("YOLO_CONFIG_DIR", str(tmp_path / "build/old-settings"))
    monkeypatch.setenv("YOLO_AUTOINSTALL", "true")
    build_paths.configure_ultralytics()
    assert Path(os.environ["YOLO_CONFIG_DIR"]) == scratch / "ultralytics-settings"
    assert (scratch / "ultralytics-settings").is_dir()
    assert os.environ["YOLO_AUTOINSTALL"] == "false"
    assert not (tmp_path / "build").exists()
