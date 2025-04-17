
from __future__ import annotations

from ._utils import delimiter_chars, whitespace_chars
from .objects import *


class Tokenizer:
    doc: memoryview
    pos: int

    def __init__(self, doc: memoryview):
        self.doc = doc
        self.pos = 0

    def seek(self, offset: int) -> None:
        if 0 <= offset < len(self.doc):
            self.pos = offset
        elif -len(self.doc) <= offset < 0:
            self.pos = len(self.doc) - offset
        else:
            self.pos = len(self.doc)

    def seek_from_curr(self, offset: int) -> None:
        self.seek(self.pos + offset)

    def is_end(self) -> bool:
        return self.pos >= len(self.doc)

    def skip_whitespace(self) -> None:
        while self.pos < len(self.doc):
            curr = self.doc[self.pos]
            if curr in whitespace_chars:
                self.pos += 1
            elif curr == ord("%"):
                while self.pos < len(self.doc):
                    curr = self.doc[self.pos]
                    if curr in b"\r\n":
                        break
                    self.pos += 1
            else:
                break

    def parse_string(self) -> bytes:
        start_pos = self.pos
        self.pos += 1
        pair = 1

        while self.pos < len(self.doc) and pair > 0:
            curr = self.doc[self.pos]
            self.pos += 1
            if curr == ord("("):
                pair += 1
            elif curr == ord(")"):
                pair -= 1
            elif curr == ord("\\"):
                self.pos += 1

        return self.doc[start_pos:self.pos].tobytes()

    def next(self) -> bytes:
        self.skip_whitespace()

        start_pos = self.pos
        while self.pos < len(self.doc):
            curr = self.doc[self.pos]
            if curr in whitespace_chars:
                break
            elif curr in delimiter_chars:
                if start_pos < self.pos or curr == ord("%"):
                    break
                if curr in b"[]{}":
                    self.pos += 1
                    break
                if curr == ord("("):
                    return self.parse_string()
                if curr == ord("<"):
                    if self.pos + 1 < len(self.doc) and self.doc[self.pos + 1] == ord("<"):
                        self.pos += 2
                        break
                    else:
                        while self.pos < len(self.doc):
                            curr = self.doc[self.pos]
                            self.pos += 1
                            if curr == ord(">"):
                                break
                        break
                if curr == ord(">"):
                    if self.pos + 1 < len(self.doc) and self.doc[self.pos + 1] == ord(">"):
                        self.pos += 2
                        break
                self.pos += 1
                break
            else:
                self.pos += 1

        return self.doc[start_pos:self.pos].tobytes()

    def peek(self) -> bytes:
        pos = self.pos
        ret = self.next()
        self.pos = pos
        return ret


class Parser:
    @staticmethod
    def parse_object(tk: Tokenizer, file: PDFFile) -> PDFObject:
        token = tk.next()
        if token == b"null":
            return PDFNull(file)
        elif token == b"true":
            return PDFBool(file, True)
        elif token == b"false":
            return PDFBool(file, False)
        elif token.startswith(b"("):
            token = token[1:-1]
            ret = bytearray()
            i = 0
            while i < len(token):
                if token[i] == ord("\\"):
                    i += 1
                    start = i
                    while i < len(token) and ord('0') <= token[i] <= ord('7'):
                        i += 1
                        if i >= start + 3:
                            break
                    if i > start:
                        ret.append(int(token[start:i], 8))
                    else:
                        if token[i] in b"\n\r\t\b\f()\\":
                            ret.append(token[i])
                            i += 1
                        else:
                            ret.append(token[start])
                else:
                    ret.append(token[i])
                    i += 1
            return PDFString(file, bytes(ret))
        elif token.startswith(b"<") and token.endswith(b">"):
            return PDFString(file, bytes.fromhex(token[1:-1].decode('ascii')), show_hex=True)
        elif token == b"/":
            token = tk.next()
            ret = bytearray()
            i = 0
            while i < len(token):
                if token[i] == ord('#') and i + 3 < len(token):
                    ret.append(int(token[i+1:i+3], 16))
                    i += 3
                else:
                    ret.append(token[i])
                    i += 1
            return PDFName(file, bytes(ret))
        elif token == b"[":
            ret = PDFArray(file)
            while not tk.is_end():
                if tk.peek() == b"]":
                    tk.next()
                    break
                obj = Parser.parse_object(tk, file)
                ret.append(obj)
            return ret
        elif token == b"<<":
            ret = PDFDict(file)
            while not tk.is_end():
                if tk.peek() == b">>":
                    tk.next()
                    break
                key = Parser.parse_object(tk, file)
                val = Parser.parse_object(tk, file)
                ret[key] = val
            if tk.peek() == b"stream":
                tk.next()
                length = ret[PDFName(file, b"Length")].value
                start_pos = tk.pos + 1
                if tk.doc[tk.pos] == ord('\r') and tk.pos + 1 < len(tk.doc):
                    if tk.doc[tk.pos + 1] == ord('\n'):
                        start_pos += 1
                value = tk.doc[start_pos:start_pos + length].tobytes()
                tk.seek(start_pos + length)
                if tk.next() != b"endstream":
                    raise SyntaxError("Unterminated stream")
                return PDFStream(file, value, ret)
            return ret
        else:
            try:
                x = int(token)
                pos = tk.pos
                try:
                    y = int(tk.next())
                    if tk.next() == b"R":
                        return IndRef(file, N=x, G=y)
                    raise ValueError
                except ValueError:
                    tk.seek(pos)
                    return PDFInt(file, x)
            except ValueError:
                try:
                    x = float(token)
                    return PDFFloat(file, x)
                except ValueError:
                    return PDFNull(file)
