
from __future__ import annotations

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

