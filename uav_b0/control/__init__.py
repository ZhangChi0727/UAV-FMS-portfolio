"""Python adapters for the native controller; the binding is built by CMake."""
from ..paths import repository_root

__path__.append(str(repository_root() / "03_control/b0/python"))
