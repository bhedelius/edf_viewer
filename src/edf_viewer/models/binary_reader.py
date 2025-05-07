"""
A class for reading and interpreting binary data streams.

This class provides methods for reading various data types (e.g., bytes, ASCII strings, 16-bit integers) from a binary stream. It also includes utilities for checking the end of the file, determining the size of the stream, and working with streams in a context manager.

Key Methods:
- read_bytes(n): Reads `n` raw bytes from the stream.
- read_ascii(n): Reads `n` bytes and decodes them into an ASCII string.
- read_int16(byteorder): Reads a 16-bit signed integer with the specified byte order.
- get_file_size(): Returns the total size of the stream in bytes.
- is_eof(): Checks if the stream pointer is at or beyond the end of the file.

Usage Example:
    with BinaryReader(open("file.dat", "rb")) as reader:
        data = reader.read_bytes(10)
        integer = reader.read_int16()
"""

import struct
from typing import BinaryIO, Literal


class BinaryReader:
    """
    A binary stream reader with methods for reading structured binary data.

    Attributes:
        stream (BinaryIO): A binary stream object to read from.
    """

    def __init__(self, stream: BinaryIO):
        """
        Initialize the BinaryReader with a binary stream.

        Args:
            stream (BinaryIO): A binary stream object (e.g., a file or BytesIO).
        """
        self.stream = stream

    def read_bytes(self, n: int) -> bytes:
        """
        Read `n` bytes from the stream.

        Args:
            n (int): Number of bytes to read.

        Returns:
            bytes: The raw bytes read.

        Raises:
            EOFError: If fewer than `n` bytes are available.
        """
        data = self.stream.read(n)
        if len(data) < n:
            raise EOFError(f"Expected {n} bytes, got {len(data)}")
        return data

    def read_ascii(self, n: int) -> str:
        """
        Read `n` bytes and decode them as an ASCII string.

        Args:
            n (int): Number of bytes to read.

        Returns:
            str: ASCII-decoded string.
        """
        return self.read_bytes(n).decode("ascii")

    def read_int16(self, byteorder: Literal["little", "big"] = "little") -> int:
        """
        Read a 16-bit signed integer.

        Args:
            byteorder (Literal["little", "big"]): Byte order to use.

        Returns:
            int: The decoded 16-bit integer.
        """
        fmt = "<h" if byteorder == "little" else ">h"
        return struct.unpack(fmt, self.read_bytes(2))[0]

    def get_file_size(self) -> int:
        """
        Get the total size of the stream in bytes.

        Returns:
            int: Size of the stream in bytes.
        """
        current = self.stream.tell()
        self.stream.seek(0, 2)
        size = self.stream.tell()
        self.stream.seek(current)
        return size

    def is_eof(self) -> bool:
        """
        Check if the stream pointer is at or beyond the end.

        Returns:
            bool: True if at EOF, False otherwise.
        """
        return self.stream.tell() >= self.get_file_size()

    def __enter__(self):
        """
        Enter context manager (e.g., with BinaryReader(...) as reader).

        Returns:
            BinaryReader: The current instance.
        """
        return self

    def __exit__(self, _exc_type, _exc_value, _traceback):
        """
        Exit context manager and close the stream if closable.

        Returns:
            bool: False to propagate exceptions.
        """
        close = getattr(self.stream, "close", None)
        if callable(close):
            close()
        return False
