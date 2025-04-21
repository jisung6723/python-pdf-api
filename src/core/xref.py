
from __future__ import annotations

from typing import Dict, Optional, Tuple
import io

from .objects import *
from .reader import Tokenizer, Parser
from .stream import Stream


class RefSrc:
    ref: IndRef
    obj: Optional[PDFObject]

    def __init__(self, ref: IndRef, obj: PDFObject):
        self.ref = ref
        self.obj = obj

    def read(self) -> PDFObject:
        return self.obj


class RefSrcFromTk(RefSrc):
    tk: Tokenizer
    offset: int
    obj_wrap: bool

    def __init__(self, ref: IndRef, tk: Tokenizer, offset: int, obj_wrap=True):
        super().__init__(ref, None)
        self.tk = tk
        self.offset = offset
        self.obj_wrap = obj_wrap

    def read(self) -> PDFObject:
        tk = self.tk
        ref = self.ref

        if self.obj is None:
            self.tk.seek(self.offset)
            if self.obj_wrap:
                N, G = int(tk.next()), int(tk.next())
                if N != ref.N or G != ref.G:
                    raise SyntaxError("IndRef is different from expected")
                if tk.next() != b'obj':
                    raise SyntaxError("Expected obj but not found")
                self.obj = Parser.parse_object(tk, self.ref._file)
                if tk.next() != b'endobj':
                    raise SyntaxError("Expected endobj but not found")
        return self.obj


class XRef:
    table: Dict[int, RefSrc]
    file: PDFFile

    def __init__(self, file: PDFFile):
        self.file = file
        self.table = {0: RefSrc(IndRef(file, 0, 65535), PDFNull(file))}

    def update(self, num: int, src: RefSrc, equal_update: bool = False) -> bool:
        if num not in self.table:
            self.table[num] = src
            return True
        else:
            if src.ref.G > self.table[num].ref.G:
                self.table[num] = src
                return True
            if equal_update and src.ref.G == self.table[num].ref.G:
                self.table[num] = src
                return True
        return False

    def resolve(self, ref: IndRef) -> PDFObject:
        if ref.N in self.table:
            if ref.G == self.table[ref.N].ref.G:
                return self.table[ref.N].read()
        return PDFNull(self.file)


class XRefStream(Stream):
    def __init__(self, stream: PDFStream):
        super().__init__(stream)

    @property
    def Type(self) -> bytes:
        return self.extent.get_expected('Type', PDFName).to_python()

    @property
    def Size(self) -> int:
        return self.extent.get_expected('Size', PDFInt).to_python()

    @Size.setter
    def Size(self, size: int) -> None:
        self.extent[b'Size'] = PDFInt(self.file, size)

    @property
    def Index(self) -> list:
        return self.extent.get_expected('Index', PDFArray).to_python()

    @Index.setter
    def Index(self, index: list) -> None:
        self.extent[b'Index'] = PDFArray(self.file, index)

    @property
    def Prev(self) -> int:
        return self.extent.get_expected('Prev', PDFInt).to_python()

    @Prev.setter
    def Prev(self, index: int) -> None:
        self.extent[b'Prev'] = PDFInt(self.file, index)


class XRefParser:
    @staticmethod
    def parse_xref(tk: Tokenizer, file: PDFFile, offset: int) -> Tuple[XRef, PDFDict]:
        tk.seek(offset)
        if tk.peek() == b"xref":
            return XRefParser.parse_xref_table(tk, file)
        return XRefParser.parse_xref_stream(tk, file)

    @staticmethod
    def parse_xref_table(tk: Tokenizer, file: PDFFile) -> Tuple[XRef, PDFDict]:
        tk.next()
        xref = XRef(file)

        while not tk.is_end():
            if tk.peek() == b'trailer':
                break
            start, length = int(tk.next()), int(tk.next())
            for i in range(start, start + length):
                off = int(tk.next())
                gen = int(tk.next())
                nf = tk.next() == b'n'
                if nf:
                    xref.update(i, RefSrcFromTk(IndRef(file, i, gen), tk, off))
                else:
                    xref.update(i, RefSrc(IndRef(file, i, gen), PDFNull(file)))
        tk.next()
        trailer = Parser.parse_object(tk, file)
        return xref, trailer

    @staticmethod
    def parse_xref_stream(tk: Tokenizer, file: PDFFile) -> Tuple[XRef, PDFDict]:
        xref = XRef(file)

        tk.next()
        tk.next()
        if tk.next() != b"obj":
            raise SyntaxError("Expected obj, but not found")

        stream = XRefStream(Parser.parse_object(tk, file))
        if tk.next() != b'endobj':
            raise SyntaxError("Expected endobj but not found")
        
