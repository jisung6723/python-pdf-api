from __future__ import annotations

from typing import Protocol, TypeVar, TYPE_CHECKING, ClassVar, Generic
from typing import List, Dict, Optional, Tuple, Set, Any, Union, Type
from dataclasses import dataclass
from abc import ABC, abstractmethod
from ._utils import Singleton
from ._utils import delimiter_chars, whitespace_chars, two_digit_hex_code

if TYPE_CHECKING:
    from .file import PDFFile


class PDFObject(ABC):
    _ref: Optional[IndRef] = None
    _file: PDFFile
    value: Any

    def __init__(self, file: PDFFile):
        self._file = file

    def mark_modified(self):
        if self._ref:
            self._file.mark_updated(self._ref, self)

    def resolve(self) -> PDFObject:
        return self

    @abstractmethod
    def to_bytes(self) -> bytes:
        raise Exception("Abstract method")


class PDFNull(Singleton, PDFObject):
    value = None

    def __init__(self, file: PDFFile):
        super().__init__(file)

    def to_bytes(self) -> bytes:
        return b'null'


@dataclass
class PDFBool(PDFObject):
    value: bool

    def __init__(self, file: PDFFile, value: bool):
        super().__init__(file)
        self.value = value

    def to_bytes(self) -> bytes:
        return b'true' if self.value else b'false'


@dataclass
class PDFInt(PDFObject):
    value: int

    def __init__(self, file: PDFFile, value: int):
        super().__init__(file)
        self.value = value

    def to_bytes(self) -> bytes:
        return str(self.value).encode('ascii')


@dataclass
class PDFFloat(PDFObject):
    value: float

    def __init__(self, file: PDFFile, value: float):
        super().__init__(file)
        self.value = value

    def to_bytes(self) -> bytes:
        return str(self.value).encode('ascii')


PDFNumber = TypeVar('PDFNumber', PDFInt, PDFFloat)


class PDFString(PDFObject):
    value: bytes
    show_hex: bool = False

    def __init__(self, file: PDFFile, value: bytes, show_hex: bool = False):
        super().__init__(file)
        self.value = value
        self.show_hex = show_hex

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.value == other.value

    def to_bytes(self) -> bytes:
        if self.show_hex:
            return b"<" + "".join(map(two_digit_hex_code, self.value)).encode('ascii') + b">"
        return b"(" + (self.value
                .replace(b'\\', b'\\\\')
                .replace(b'(', b'\\(')
                .replace(b')', b'\\)')
                .replace(b'\n', b'\\n')
                .replace(b'\r', b'\\r')
                .replace(b'\t', b'\\t')
                .replace(b'\b', b'\\b')
                .replace(b'\f', b'\\f')) + b")"


@dataclass
class PDFName(PDFObject):
    value: bytes

    def __init__(self, file: PDFFile, value: bytes):
        super().__init__(file)
        self.value = value

    def __hash__(self):
        return hash(self.value)

    def __eq__(self, other):
        return hash(self) == hash(other)

    def to_bytes(self) -> bytes:
        ret = b"/"
        for b in self.value:
            if b < 32 or b > 126:
                ret = ret + b"#" + two_digit_hex_code(b).encode('ascii')
            elif b in whitespace_chars | delimiter_chars:
                ret = ret + b"#" + two_digit_hex_code(b).encode('ascii')
            else:
                ret += bytes([b])
        return ret


class PDFArray(PDFObject):
    value: List[PDFObject]

    def __init__(self, file: PDFFile, value: Optional[List[PDFObject]] = None):
        super().__init__(file)
        if value is None:
            value = []
        self.value = value

    def append(self, value: PDFObject) -> None:
        self.value.append(value)

    def to_bytes(self) -> bytes:
        return b"[ " + b" ".join(map(lambda obj: obj.to_bytes(), self.value)) + b" ]"


class PDFDict(PDFObject):
    value: Dict[bytes, PDFObject]

    def __init__(self, file: PDFFile, value: Optional[Dict[PDFName, PDFObject]] = None):
        super().__init__(file)
        if value is None:
            value = {}
        self.value = value

    def __getitem__(self, key: PDFName | bytes) -> PDFObject:
        return self.value[key]

    def __setitem__(self, key: PDFName | bytes, value: PDFObject) -> None:
        self.value[key] = value

    def __delitem__(self, key: PDFName | bytes) -> None:
        del self.value[key]

    def __contains__(self, key: PDFName | bytes) -> bool:
        return key in self.value

    def to_bytes(self) -> bytes:
        return (b"<<\n" +
                b"\n".join(map(lambda key: key.to_bytes() + b" " + self.value[key].to_bytes(), self.value))
                + b">>")

    def get(self, key: PDFName | str | bytes) -> PDFObject:
        if isinstance(key, str):
            key = key.encode('utf-8')
        if key in self:
            val = self[key]
            return val.resolve()
        return PDFNull(self._file)

    def get_expected(self, key: PDFName | str | bytes, _type: Type[T]) -> T:
        val = self.get(key)
        if isinstance(val, _type):
            return val
        raise Exception(f"Expect {_type.__name__} but got {type(val).__name__}")


class PDFStream(PDFObject):
    value: bytes
    extent: PDFDict

    def __init__(self, file: PDFFile, value: bytes, extent: PDFDict):
        super().__init__(file)
        self.value = value
        self.extent = extent

    def to_bytes(self) -> bytes:
        return self.extent.to_bytes() + b"\nstream\n" + self.value + b"\nendstream"


@dataclass
class IndRef(PDFObject):
    N: int
    G: int

    def __init__(self, file: PDFFile, N: int, G: int):
        super().__init__(file)
        self.N = N
        self.G = G

    def to_bytes(self) -> bytes:
        return f"{self.N} {self.G} R".encode('ascii')

    def resolve(self) -> PDFObject:
        obj = self._file.resolve(self)
        obj._ref = self
        return obj

    def __gt__(self, other):
        return self.N > other.N or (self.N == other.N and self.G > other.G)

    def __hash__(self):
        return hash((self.N, self.G))

    def __eq__(self, other):
        return isinstance(other, self.__class__) and self.N == other.N and self.G == other.G


T = TypeVar("T")
IType = Union[T, IndRef]  # may be an indirect reference
Nullable = Union[T, PDFNull]  # optional
NIType = Union[T, IndRef, PDFNull] # optional and may be an indirect Reference

