"""StrictDoc 0.30.1 presentation configuration for the derived B0 view."""

from strictdoc.core.project_config import ProjectConfig


def create_config() -> ProjectConfig:
    return ProjectConfig(
        project_title="B0 joint requirement baseline — D2 candidate",
        custom_css_path="../presentation.css",
    )
