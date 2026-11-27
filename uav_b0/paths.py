from pathlib import Path


def repository_root(start: str | Path = __file__) -> Path:
    """Locate the nearest checkout (or isolated contract fixture) by its authority."""
    start = Path(start).resolve()
    for candidate in ((start, *start.parents) if start.is_dir() else start.parents):
        if (candidate / "05_integration/b0/validate_config.py").is_file():
            return candidate
    raise FileNotFoundError(f"No B0 contract authority above {start}")
