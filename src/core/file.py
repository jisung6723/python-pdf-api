
from __future__ import annotations
import os
import io
from typing import TYPE_CHECKING
from typing import Set, Optional, List
from ._utils import find_from_memoryview, rfind_from_memoryview

from .reader import Tokenizer
from .xref import XRef, XRefParser, RefSrc
from .objects import *


class PDFFile:
    filename: str
    doc: memoryview
    header_pos: int = -1
    eof_pos: int = -1
    tk: Tokenizer
    xref: XRef
    last_xref_offset: int = -1
    trailer: Trailer
    updated_ref: Set[IndRef]

    def __init__(self, filename: str):
        self.filename = filename

        if filename.endswith('.pdf'):
            if os.path.exists(filename):
                self.read()
        self.updated_ref = set()

    def _read_body(self):
        doc = self.doc
        eof = self.eof_pos
        header = self.header_pos
        self.xref = XRef(self)
        self.trailer = Trailer(PDFDict(self))

        while True:
            start_xref = rfind_from_memoryview(b"startxref", doc, header, eof)
            if start_xref == -1:
                raise Exception("Can not find offset of XRef")
            xref_offset = int(Tokenizer(doc[start_xref+9:eof]).next())
            if self.last_xref_offset == -1:
                self.last_xref_offset = xref_offset
            xref, trailer = XRefParser.parse_xref(self.tk, self, xref_offset)
            for k, v in xref.table.items():
                self.xref.update(k, v)
            for k, v in trailer.value.items():
                self.trailer.extent.value.setdefault(k, v)
            break

    def read(self):
        with open(self.filename, "rb") as f:
            self.doc = memoryview(f.read())
        doc = self.doc
        self.header_pos = find_from_memoryview(b"%PDF-", doc)
        if self.header_pos == -1:
            raise Exception("Can not find pdf header (%PDF-)")

        self.eof_pos = rfind_from_memoryview(b"%%EOF", doc)
        if self.eof_pos == -1:
            raise Exception("Can not find pdf eof (%%EOF)")

        self.tk = Tokenizer(doc[self.header_pos:self.eof_pos])
        self._read_body()
        self.updated_ref = set()

    def save(self, filename: Optional[str] = None):
        if filename is None:
            filename = self.filename
        buffer = io.BytesIO()
        buffer.write(b"%PDF-2.0\n%\xdd\xdd\xdd\xdd\n")
        ref_list = sorted([src.ref for src in self.xref.table.values()])
        self._write_body(buffer, ref_list)

        if os.path.exists(filename):
            Q = input(f"You are trying to override {filename}. (Y/n) ")
            if Q.strip() != "Y":
                return

        with open(filename, "wb") as f:
            f.write(buffer.getvalue())

    def incremental_update(self, filename: Optional[str] = None):
        if filename is None:
            filename = self.filename
        buffer = io.BytesIO()
        buffer.write(self.doc)

        if len(self.updated_ref) > 0:
            self._write_body(buffer, sorted(self.updated_ref), self.last_xref_offset)

        if os.path.exists(filename):
            Q = input(f"You are trying to override {filename}. (Y/n) ")
            if Q.strip() != "Y":
                return

        with open(filename, "wb") as f:
            f.write(buffer.getvalue())

    def _write_body(self, buffer: io.BytesIO, ref_list: List[IndRef], prev_offset: int = -1):
        new_offsets = dict()
        new_ref_list = []
        for ref in ref_list:
            obj = self.xref.resolve(ref)
            if obj == PDFNull(self):
                if ref.N == 0:
                    new_ref_list.append(ref)
                continue
            new_offsets[ref.N] = buffer.tell()
            new_ref_list.append(ref)
            buffer.write(f"{ref.N} {ref.G} obj\n".encode('ascii'))
            buffer.write(obj.to_bytes())
            buffer.write(b"\nendobj\n")

        self._write_table(buffer, new_ref_list, new_offsets, prev_offset)

    def _write_table(self, buffer: io.BytesIO, ref_list: List[IndRef],
                     new_offsets: dict, prev_offset: int = -1):
        xref_offset = buffer.tell()
        buffer.write(b"xref\n")
        start = ref_list[0].N
        length = ref_list[-1].N - start + 1
        buffer.write(f"{start} {length}\n".encode('ascii'))
        pointer = 0
        for i in range(start, start+length):
            if i == 0:
                buffer.write(f"{0:010} {65535:05} f\r\n".encode('ascii'))
                pointer += 1
            elif ref_list[pointer].N == i:
                ref = ref_list[pointer]
                buffer.write(f"{new_offsets[i]:010} {ref.G:05} n\r\n".encode('ascii'))
                pointer += 1
            else:
                buffer.write(f"{0:010} {65535:05} f\r\n".encode('ascii'))

        buffer.write(b"trailer\n")
        self.trailer.update()
        if prev_offset != -1:
            self.trailer.Prev = prev_offset
        buffer.write(self.trailer.extent.to_bytes())
        buffer.write(f"\nstartxref\n{xref_offset}\n%%EOF\n".encode('ascii'))

    def resolve(self, ref: IndRef) -> PDFObject:
        return self.xref.resolve(ref)

    def mark_updated(self, ref: IndRef, obj: PDFObject):
        if self.xref.update(ref.N, RefSrc(ref, obj), equal_update=True):
            self.updated_ref.add(ref)

    def add_new_ref(self, obj: PDFObject) -> IndRef:
        ref = IndRef(self, max(self.xref.table.keys())+1, 0)
        self.mark_updated(ref, obj)
        return ref


class Trailer:
    extent: PDFDict
    file: PDFFile

    def __init__(self, extent: PDFDict):
        self.extent = extent
        self.file = extent._file

    def update(self):
        self.Size = max(self.file.xref.table.keys()) + 1

    @property
    def Size(self) -> int:
        return self.extent[b"Size"].to_python()

    @Size.setter
    def Size(self, size: int) -> None:
        self.extent[b"Size"] = PDFInt(self.file, size)

    @property
    def Prev(self) -> Optional[int]:
        return self.extent[b"Prev"].to_python()

    @Prev.setter
    def Prev(self, offset: Optional[int]) -> None:
        if offset is None and b"Prev" in self.extent:
            del self.extent[b"Prev"]
        self.extent[b"Prev"] = PDFInt(self.file, offset)

    @property
    def Root(self) -> PDFDict:
        return self.extent.get_expected(b"Root", PDFDict)

    @Root.setter
    def Root(self, root: PDFDict | IndRef) -> None:
        if isinstance(root, PDFDict):
            root = self.file.add_new_ref(root)
        self.extent[b"Root"] = root

    @property
    def Encrypt(self) -> Nullable[PDFDict]:
        return self.extent.get_expected(b"Encrypt", Nullable[PDFDict])

    @Encrypt.setter
    def Encrypt(self, encrypt: Nullable[PDFDict]) -> None:
        self.extent[b"Encrypt"] = encrypt

    @property
    def Info(self) -> Nullable[PDFDict]:
        return self.extent.get_expected(b"Info", Nullable[PDFDict])

    @Info.setter
    def Info(self, info: Nullable[IndRef]) -> None:
        self.extent[b"Info"] = info

    @property
    def ID(self) -> Nullable[PDFArray]:
        return self.extent.get_expected(b"ID", Nullable[PDFArray])

    @ID.setter
    def ID(self, ids: Optional[List[bytes]] | Nullable[PDFArray]) -> None:
        if (ids is None) or ids == PDFNull(self.file):
            del self.extent[b"ID"]
        elif isinstance(ids, list):
            ids = [PDFString(self.file, b) for b in ids]
            ids = PDFArray(self.file, ids)
        self.extent[b"ID"] = ids
