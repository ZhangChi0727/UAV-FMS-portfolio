"""Minimal StrictDoc configuration for the isolated G1.5-B presentation trial."""

from strictdoc.core.project_config import ProjectConfig


def create_config() -> ProjectConfig:
    """Return the source-owned configuration supported by StrictDoc 0.30.1."""
    return ProjectConfig(
        project_title="B0 G1.5-B pilot",
        custom_css_path="presentation.css",
    )
