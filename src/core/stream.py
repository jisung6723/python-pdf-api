
from __future__ import annotations

from typing import List
from bitarray import bitarray
import zlib
from PIL import Image
from io import BytesIO
from ._utils import whitespace_chars, camel_to_snake
from .objects import *
from .file import PDFFile


class Stream:
    extent: PDFDict
    value: bytes
    file: PDFFile
    decoded_value: Optional[bytes] = None

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

    def decode(self):
        filters = self.Filter.to_python()
        if filters is None:
            self.decoded_value = self.value
            return self.decoded_value
        if isinstance(filters, bytes):
            filters = [filters]

        params = self.DecodeParams.to_python()
        if params is None:
            params = [dict() for _ in range(len(filters))]
        if isinstance(params, dict):
            params = [params]

        params = [{camel_to_snake(k.decode('utf-8')): v for k, v in param.items()} for param in params]

        dv = self.value
        for i in range(len(filters)):
            dv = Filter.decode(dv, filters[i], **params[i])

        self.decoded_value = dv
        return self.decoded_value


class Filter:
    @staticmethod
    def decode(value: bytes, _filter: bytes, **kwargs) -> bytes:
        return getattr(Filter, _filter.decode('ascii'))(value, **kwargs)

    @staticmethod
    def encode(value: bytes, _filter: bytes, **kwargs) -> bytes:
        if _filter.endswith(b'Decode'):
            _filter = _filter.replace(b'Decode', b'Encode')
        return getattr(Filter, _filter.decode('ascii'))(value, **kwargs)

    @staticmethod
    def ASCIIHexDecode(value: bytes) -> bytes:
        pos = 0
        ret = bytearray()
        value = bytes([b for b in value if b not in whitespace_chars])

        while pos < len(value):
            if value[pos] == ord('>'):
                break
            elif pos + 2 <= len(value) and value[pos+1] != ord('>'):
                ret.append(int(value[pos:pos + 2], 16))
                pos += 2
            else:
                ret.append(int(value[pos:pos+1]+b"0", 16))
                pos += 1

        return bytes(ret)

    @staticmethod
    def ASCIIHexEncode(value: bytes) -> bytes:
        ret = bytearray()
        for b in value:
            x = hex(b)[2:].upper().encode('ascii')
            for i in x:
                ret.append(i)
        return bytes(ret)

    @staticmethod
    def ASCII85Decode(value: bytes) -> bytes:
        pos = 0
        ret = bytearray()
        value = bytes([b for b in value if b not in whitespace_chars])
        eod = value.find(b'~>')
        if eod >= 0:
            value = value[:eod]

        while pos < len(value):
            if value[pos] == ord('z'):
                for _ in range(4):
                    ret.append(0)
                pos += 1
            elif pos + 5 <= len(value):
                x = 0
                for i in range(5):
                    x = x * 85 + value[pos+i]-33
                y = []
                for i in range(4):
                    y.append(x % 256)
                    x //= 256
                for i in y[::-1]:
                    ret.append(i)
                pos += 5
            else:
                N = len(value) - pos
                x = 0
                for i in range(5):
                    if i < N:
                        x = x*85 + value[pos+i]-33
                    else:
                        x = x*85 + 84
                y = []
                for i in range(4):
                    y.append(x % 256)
                    x //= 256
                for i in y[::-1][:N - 1]:
                    ret.append(i)
                pos += 5

        return bytes(ret)

    @staticmethod
    def ASCII85Encode(value: bytes) -> bytes:
        ret = bytearray()
        N = len(value)
        for i in range(0, N-N%4, 4):
            x = 0
            for j in range(4):
                x = x*256 + value[i+j]
            if x == 0:
                ret.append(ord('z'))
            else:
                y = []
                for j in range(5):
                    y.append((x % 85) + 33)
                    x //= 85
                for j in y[::-1]:
                    ret.append(j)
        if N%4 > 0:
            x = 0
            for j in range(N - (N % 4), N - (N % 4) + 4):
                if j < N:
                    x = x * 256 + value[j]
                else:
                    x = x * 256
            y = []
            for j in range(5):
                y.append((x % 85) + 33)
                x //= 85
            for j in y[:-(N % 4) - 2:-1]:
                ret.append(j)
        ret.append(ord('~'))
        ret.append(ord('>'))
        return bytes(ret)

    @staticmethod
    def LZWEncode(value: bytes) -> bytes:
        dictionary = {bytes([i]): i for i in range(256)}
        next_code = 258
        w = b""
        result = bitarray()
        word_size = 9

        def add(x: int):
            i = 0
            word = bitarray()
            while i < word_size:
                word.append(x % 2)
                x //= 2
                i += 1
            word.reverse()
            result.extend(word)

        add(256) # clear table

        for c in value:
            wc = w + bytes([c])
            if wc in dictionary:
                w = wc
            else:
                add(dictionary[w])
                dictionary[wc] = next_code
                next_code += 1
                if next_code >= (1 << word_size):
                    word_size += 1
                    if word_size > 12:
                        add(256)
                        dictionary = {bytes([i]): i for i in range(256)}
                        next_code = 258
                        word_size = 9
                        w = b""
                        continue
                w = bytes([c])
        if w:
            add(dictionary[w])
        add(257)  # EOD marker
        return bytes(result)

    @staticmethod
    def LZWDecode(
            value: bytes,
            predictor: int = 1,
            colors: int = 1,
            bits_per_component: int = 8,
            columns: int = 1,
            early_change: int = 1
    ) -> bytes:
        # 초기 테이블
        dictionary = {i: bytes([i]) for i in range(256)}
        clear_code = 256
        eod_code = 257
        next_code = 258
        bitstream = bitarray()
        bitstream.frombytes(value)
        word_size = 9
        pos = 0
        ret = b""
        bef = b""
        while pos < len(bitstream):
            code = 0
            x = bitstream[pos:pos+word_size]
            pos += word_size
            for i in x:
                code = code * 2 + i
            if pos > len(bitstream):
                break
            if code == clear_code:
                dictionary = {i: bytes([i]) for i in range(256)}
                next_code = 258
                word_size = 9
                bef = b""
            elif code == eod_code:
                break
            elif code in dictionary:
                ret += dictionary[code]
                if len(bef) > 0:
                    dictionary[next_code] = bef + dictionary[code][:1]
                    next_code += 1
                    word_size += 1 if next_code >= (1 << word_size) - early_change else 0
                    word_size = min(word_size, 12)
                bef = dictionary[code]
            elif code == next_code:
                dictionary[next_code] = bef + bef[:1]
                next_code += 1
                word_size += 1 if next_code >= (1 << word_size) - early_change else 0
                bef = dictionary[code]
            else:
                print(bef, pos, code, next_code, len(bitstream), word_size)
                raise Exception("Invalid code")
        return ret

    @staticmethod
    def FlateEncode(value: bytes) -> bytes:
        return zlib.compress(value)

    @staticmethod
    def FlateDecode(value: bytes) -> bytes:
        return zlib.decompress(value)

    @staticmethod
    def RunLengthEncode(value: bytes) -> bytes:
        ret = b""
        bef = value[:1]
        pos = 1
        cnt = 1
        while pos < len(value):
            curr = value[pos:pos+1]
            if bef == curr:
                cnt += 1
                pos += 1
            else:
                ret = ret + bytes([cnt - 1]) + bef
                bef = curr
                cnt = 0
        if cnt >= 1:
            ret = ret + bytes([cnt - 1]) + bef
            cnt = 1
        result = b""
        temp = b""
        pos = 0
        cnt = 0
        while pos < len(ret):
            N = ret[pos]
            B = ret[pos + 1: pos + 2]
            if N == 0 and cnt < 127:
                cnt += 1
                temp += B
                pos += 2
            else:
                if cnt > 1:
                    result = result + bytes([256-cnt]) + temp
                    temp = b""
                    cnt = 0
                elif cnt == 1:
                    result = result + bytes([0]) + temp
                    temp = b""
                    cnt = 0
                else:
                    result += ret[pos:pos + 2]
                    pos += 2
        if cnt > 1:
            result = result + bytes([256 - cnt]) + temp
        elif cnt == 1:
            result = result + bytes([0]) + temp
        result += bytes([128])
        return result

    @staticmethod
    def RunLengthDecode(value: bytes) -> bytes:
        ret = b""
        pos = 0
        while pos < len(value):
            header = value[pos]
            if header < 128:
                ret += bytes([value[pos+1]]*(header+1))
                pos += 2
            elif header == 128:
                break
            else:
                ret += value[pos + 1:pos + 257 - header]
                pos = pos + 257 - header
        return ret

