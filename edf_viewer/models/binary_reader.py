import struct
from typing import BinaryIO


class BinaryReader:
    def __init__(self, file: BinaryIO):
        self.f = file

    def read_bytes(self, n: int) -> bytes:
        data = self.f.read(n)
        if len(data) < n:
            raise EOFError(f"Expected {n} bytes, got {len(data)}")
        return data

    def read_ascii(self, n: int) -> str:
        return self.read_bytes(n).decode("ascii")

    def read_int16(self, byteorder="little") -> int:
        fmt = "<h" if byteorder == "little" else ">h"
        return struct.unpack(fmt, self.read_bytes(2))[0]

    def get_file_size(self) -> int:
        current = self.f.tell()
        self.f.seek(0, 2)
        size = self.f.tell()
        self.f.seek(current)
        return size

    def is_eof(self) -> bool:
        current = self.f.tell()
        file_size = self.get_file_size()
        return current >= file_size
