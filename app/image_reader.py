from __future__ import annotations

from pathlib import Path
from typing import Iterator, Protocol, Union


class RawDataSource(Protocol):
    @property
    def size(self) -> int:
        ...

    def read(self, offset: int, size: int) -> bytes:
        ...

    def iter_chunks(self, chunk_size: int, offset: int = 0) -> Iterator[bytes]:
        ...

    def close(self) -> None:
        ...


class DiskImageReader:
    """Read-only disk image reader for .img and .dd files."""

    def __init__(self, path: Union[str, Path]) -> None:
        self._path = Path(path)
        self._file = None

        if not self._path.exists():
            raise FileNotFoundError(f"Image file not found: {self._path}")

        if not self._path.is_file():
            raise ValueError(f"Not a file: {self._path}")

        self._file = open(self._path, "rb")

    @property
    def closed(self) -> bool:
        return self._file is None or self._file.closed

    @property
    def size(self) -> int:
        if self.closed:
            raise ValueError("Image is closed.")
        self._file.seek(0, 2)
        size = self._file.tell()
        self._file.seek(0)
        return size

    def read(self, offset: int, size: int) -> bytes:
        if self.closed:
            raise ValueError("Image is closed.")
        if offset < 0:
            raise ValueError("Offset must be >= 0.")
        if size <= 0:
            raise ValueError("Size must be > 0.")

        image_size = self.size
        if offset >= image_size:
            raise ValueError("Offset is beyond the end of the image.")
        if offset + size > image_size:
            raise ValueError("Read exceeds the end of the image.")

        self._file.seek(offset)
        return self._file.read(size)

    def iter_chunks(self, chunk_size: int, offset: int = 0) -> Iterator[bytes]:
        if self.closed:
            raise ValueError("Image is closed.")
        if chunk_size <= 0:
            raise ValueError("Chunk size must be > 0.")
        if offset < 0:
            raise ValueError("Offset must be >= 0.")

        image_size = self.size
        if offset >= image_size:
            raise ValueError("Offset is beyond the end of the image.")

        for start in range(offset, image_size, chunk_size):
            remaining = image_size - start
            length = min(chunk_size, remaining)
            yield self.read(start, length)

    def close(self) -> None:
        if self._file is not None and not self._file.closed:
            self._file.close()

    def __enter__(self) -> "ImageReader":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


class PhysicalDeviceReader:
    """Read a Windows physical device without requesting write access."""

    def __init__(self, device_path: str) -> None:
        import os
        import sys

        if sys.platform != "win32":
            raise OSError("Physical device access is only supported on Windows.")
        if not device_path.startswith("\\\\.\\PhysicalDrive"):
            raise ValueError("Physical device path must use the \\\\.\\PhysicalDriveN form.")

        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
        self._file = open(device_path, "rb", buffering=0)
        self._device_path = device_path
        self._size = self._query_size()

    @property
    def closed(self) -> bool:
        return self._file.closed

    @property
    def size(self) -> int:
        if self.closed:
            raise ValueError("Device is closed.")
        return self._size

    def _query_size(self) -> int:
        import ctypes
        import msvcrt

        size = ctypes.c_longlong()
        handle = msvcrt.get_osfhandle(self._file.fileno())
        get_file_size_ex = ctypes.windll.kernel32.GetFileSizeEx
        if not get_file_size_ex(handle, ctypes.byref(size)):
            error = ctypes.get_last_error()
            raise OSError(error, f"Unable to query physical device size: {self._device_path}")
        if size.value <= 0:
            raise OSError("Physical device reported an invalid size.")
        return size.value

    def read(self, offset: int, size: int) -> bytes:
        if self.closed:
            raise ValueError("Device is closed.")
        if offset < 0:
            raise ValueError("Offset must be >= 0.")
        if size <= 0:
            raise ValueError("Size must be > 0.")
        if offset >= self._size or offset + size > self._size:
            raise ValueError("Read exceeds the physical device boundary.")
        self._file.seek(offset)
        data = self._file.read(size)
        if len(data) != size:
            raise OSError("Physical device returned a short read.")
        return data

    def iter_chunks(self, chunk_size: int, offset: int = 0) -> Iterator[bytes]:
        if chunk_size <= 0:
            raise ValueError("Chunk size must be > 0.")
        if offset < 0 or offset >= self._size:
            raise ValueError("Offset is beyond the physical device.")
        for start in range(offset, self._size, chunk_size):
            yield self.read(start, min(chunk_size, self._size - start))

    def close(self) -> None:
        if not self.closed:
            self._file.close()

    def __enter__(self) -> "PhysicalDeviceReader":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()


ImageReader = DiskImageReader
