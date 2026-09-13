from __future__ import annotations

from pathlib import Path
from typing import Iterator, Union


class ImageReader:
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
