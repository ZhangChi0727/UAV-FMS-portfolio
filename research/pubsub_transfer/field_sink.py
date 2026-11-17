"""A single optional retained field; both paths share the call site."""
from struct import Struct


FIELD = Struct('<I')


def write_field(target: bytearray, value: int) -> None:
    FIELD.pack_into(target, 0, value)


def sham_field(target: bytearray, value: int) -> None:
    pass
