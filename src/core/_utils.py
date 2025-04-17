
from __future__ import annotations

from typing import Protocol


whitespace_chars = set(b"\0\t\n\f\r ")
delimiter_chars = set(b"()<>[]{}/%")


def two_digit_hex_code(b: int, upper=True) -> str:
    if upper:
        return f"{hex(b)[2:].upper():02}"
    return f"{hex(b)[2:]:02}"


def find_from_memoryview(x: bytes, src: memoryview, start_pos=0, end_pos=-1) -> int:
    if end_pos < 0:
        end_pos += len(src)

    for i in range(start_pos, end_pos - len(x)):
        if src[i:i + len(x)].tobytes() == x:
            return i
    return -1


def rfind_from_memoryview(x: bytes, src: memoryview, start_pos=0, end_pos=-1) -> int:
    if end_pos < 0:
        end_pos += len(src)

    for i in range(end_pos-len(x), start_pos-1, -1):
        if src[i:i + len(x)].tobytes() == x:
            return i
    return -1


class Singleton(object):
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not isinstance(cls._instance, cls):
            cls._instance = object.__new__(cls)
        return cls._instance


class PDFWritable(Protocol):
    def to_bytes(self, *args, **kwargs) -> bytes:
        pass

