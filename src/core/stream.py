
from __future__ import annotations

from typing import List
from .objects import *
from .file import PDFFile


class Stream:
    extent: PDFDict
    value: bytes
    file: PDFFile

    def __init__(self, stream: PDFStream):
        self.extent = stream.extent
        self.value = stream.value
        self.file = stream.extent._file

    def __setattr__(self, key, value):
        if key == 'value' and hasattr(self, key):
            super().__setattr__(key, value)
            self.extent[b'Length'] = PDFInt(self.file, len(value))
        else:
            super().__setattr__(key, value)

    @property
    def Length(self) -> int:
        return self.extent[b'Length'].to_python()

    @property
    def Filter(self) -> Nullable[PDFName | PDFArray]:
        return self.extent.get_expected(b'Filter', Nullable[Union[PDFName, PDFArray]])

    @Filter.setter
    def Filter(self, value: Nullable[PDFName | PDFArray]):
        self.extent[b'Filter'] = value

    @property
    def DecodeParams(self) -> Nullable[PDFDict | PDFArray]:
        return self.extent.get_expected(b'DecodeParams', Nullable[Union[PDFDict, PDFArray]])

    @DecodeParams.setter
    def DecodeParams(self, value: Nullable[PDFDict | PDFArray]):
        self.extent[b'DecodeParams'] = value

    @property
    def DL(self) -> Nullable[PDFInt]:
        return self.extent.get_expected(b'DL', Nullable[PDFInt])
