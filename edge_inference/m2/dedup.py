"""Mechanical exact and dHash candidate detection; not a grouping verdict.

Thresholds are supplied in a frozen, development-derived declaration before a
target scan. This module does not select a threshold, assign splits, delete or
modify images, inspect annotations, or decide whether two images are related.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterator

from PIL import Image, ImageOps, UnidentifiedImageError

ALGORITHM = "dhash64"
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"})
def private_build_root(module_path: Path) -> Path:
    """Return this checkout's ignored build directory in any worktree layout."""
    return module_path.resolve().parents[2] / "build"


WORKTREE = Path(__file__).resolve().parents[2]
PRIVATE_BUILD = private_build_root(Path(__file__))


def load_threshold_declaration(path: Path) -> tuple[dict[str, Any], str]:
    """Read an external frozen declaration; its scientific basis is not audited."""
    raw = path.read_bytes()
    declaration = json.loads(raw.decode("utf-8"))
    if not isinstance(declaration, dict):
        raise ValueError("threshold declaration must be an object")
    radius = declaration.get("hamming_threshold")
    if (declaration.get("algorithm") != ALGORITHM
        or type(radius) is not int or not 0 <= radius <= 64
        or declaration.get("source_split") != "development"
        or declaration.get("frozen_before_target_scan") is not True
        or not isinstance(declaration.get("development_evidence"), str)
        or not declaration["development_evidence"].strip()):
        raise ValueError("expected a frozen development-derived dhash64 threshold declaration")
    return declaration, hashlib.sha256(raw).hexdigest()


def image_paths(root: Path) -> list[Path]:
    """Discover local image filenames only; never follow symbolic links."""
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("image root must be a directory")
    found = []
    for directory, subdirs, files in os.walk(root, followlinks=False):
        base = Path(directory)
        for name in subdirs:
            if (base / name).is_symlink():
                raise ValueError("symbolic-link directories are not allowed")
        for name in files:
            path = base / name
            if path.is_symlink():
                raise ValueError("symbolic-link files are not allowed")
            if path.suffix.lower() in IMAGE_SUFFIXES:
                found.append(path)
    return sorted(found, key=lambda path: path.relative_to(root).as_posix())


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _dhash64(path: Path) -> int:
    with Image.open(path) as image:
        gray = ImageOps.exif_transpose(image).convert("L").resize((9, 8), Image.Resampling.LANCZOS)
        pixels = gray.tobytes()
    value = 0
    for y in range(8):
        for x in range(8):
            value = (value << 1) | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return value


def fingerprint(path: Path, root: Path) -> dict[str, Any]:
    """Hash the bytes and compute dHash; retain decode failures as unknown."""
    before = path.stat()
    byte_digest = _sha256(path)
    try:
        perceptual = f"{_dhash64(path):016x}"
        error = None
    except (OSError, ValueError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        perceptual = None
        error = type(exc).__name__
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise RuntimeError("an input changed during hashing")
    return {"path": path.relative_to(root).as_posix(), "sha256": byte_digest,
            "dhash64": perceptual, "dhash_error": error}


def candidate_pairs(records: list[dict[str, Any]], threshold: int) -> Iterator[dict[str, Any]]:
    """Yield pairwise candidates only; dHash is not evidence of shared origin."""
    if type(threshold) is not int or not 0 <= threshold <= 64:
        raise ValueError("hamming threshold must be an integer in [0, 64]")
    for i, left in enumerate(records):
        for right in records[i + 1:]:
            exact = left["sha256"] == right["sha256"]
            a, b = left["dhash64"], right["dhash64"]
            distance = (int(a, 16) ^ int(b, 16)).bit_count() if a is not None and b is not None else None
            perceptual = distance is not None and distance <= threshold
            if exact or perceptual:
                reasons = (["exact_sha256"] if exact else []) + (["dhash64"] if perceptual else [])
                yield {"left": left["path"], "right": right["path"], "candidate_reasons": reasons,
                       "hamming_distance": distance, "status": "candidate_unconfirmed"}


def run(root: Path, declaration_path: Path, output: Path) -> dict[str, int]:
    """Write a new private JSONL audit; do not overwrite files or alter inputs."""
    declaration, declaration_hash = load_threshold_declaration(declaration_path)
    root = root.resolve(strict=True)
    output = output.resolve(strict=False)
    if not output.is_relative_to(PRIVATE_BUILD.resolve()) or output.is_relative_to(root):
        raise ValueError("output must be in the checkout's private build, outside the image tree")
    if not output.parent.is_dir():
        raise ValueError("output parent must already exist")
    paths = image_paths(root)
    records = [fingerprint(path, root) for path in paths]
    counts = {"images": len(records), "decode_failures": sum(r["dhash64"] is None for r in records),
              "candidate_pairs": 0, "candidate_groups": 0}
    parents = {record["path"]: record["path"] for record in records}

    def find(key: str) -> str:
        while key != parents[key]:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key

    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps({"type": "metadata", "algorithm": ALGORITHM,
                                 "declaration": declaration, "declaration_sha256": declaration_hash,
                                 "declaration_is_user_attestation": True,
                                 "note": "Candidates require review; not proof of duplication or grouping independence."}) + "\n")
        for record in records:
            stream.write(json.dumps({"type": "image", **record}) + "\n")
        for pair in candidate_pairs(records, declaration["hamming_threshold"]):
            stream.write(json.dumps({"type": "candidate", **pair}) + "\n")
            counts["candidate_pairs"] += 1
            parents[find(pair["left"])] = find(pair["right"])
        components: dict[str, list[str]] = {}
        for name in parents:
            components.setdefault(find(name), []).append(name)
        for members in components.values():
            if len(members) > 1:
                stream.write(json.dumps({"type": "candidate_group", "members": members,
                                         "status": "candidate_unconfirmed",
                                         "note": "Transitive candidate component; not proof every pair matches or shares origin."}) + "\n")
                counts["candidate_groups"] += 1
        stream.write(json.dumps({"type": "summary", **counts}) + "\n")
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--threshold-declaration", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True, help="new JSONL file inside this checkout's build, outside the input tree")
    args = parser.parse_args()
    print(json.dumps(run(args.image_root, args.threshold_declaration, args.output)))


if __name__ == "__main__":
    main()
