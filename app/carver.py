from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.image_reader import ImageReader
from app.scanner import SignatureScanner


@dataclass(frozen=True)
class RecoveredFile:
    recovery_id: str
    file_type: str
    source_offset: int
    recovered_size: int
    output_path: str
    status: str


class JPEGCarver:
    def __init__(self, image_path: str | Path, output_dir: str | Path = "recovered", chunk_size: int = 4096) -> None:
        self.image_path = Path(image_path)
        self.output_dir = Path(output_dir)
        self.chunk_size = chunk_size
        self.scanner = SignatureScanner(str(self.image_path), chunk_size=chunk_size)

    def recover(self) -> list[RecoveredFile]:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        candidates = sorted(
            (candidate for candidate in self.scanner.scan() if candidate.file_type == "JPEG"),
            key=lambda candidate: candidate.offset,
        )

        recovered: list[RecoveredFile] = []
        covered_ranges: list[tuple[int, int]] = []

        for offset_index, candidate in enumerate(candidates, start=1):
            start = candidate.offset
            end = self._find_jpeg_end(start)

            if end is not None and any(start < existing_end and existing_start < end for existing_start, existing_end in covered_ranges):
                continue

            if end is None:
                data = self._read_from_offset(start)
                status = "PARTIAL"
            else:
                data = self._read_from_offset(start, end)
                status = "RECOVERED"

            if not data:
                continue

            recovery_id = f"REC-{len(recovered) + 1:04d}"
            output_path = self.output_dir / f"{recovery_id}.jpg"
            output_path.write_bytes(data)

            recovered.append(
                RecoveredFile(
                    recovery_id=recovery_id,
                    file_type="JPEG",
                    source_offset=start,
                    recovered_size=len(data),
                    output_path=str(output_path),
                    status=status,
                )
            )
            covered_ranges.append((start, start + len(data)))

        return recovered

    def _find_jpeg_end(self, start_offset: int) -> int | None:
        with ImageReader(self.image_path) as image:
            marker = b"\xff\xd9"
            overlap = b""
            absolute_chunk_start = start_offset

            for chunk in image.iter_chunks(self.chunk_size, start_offset):
                window = overlap + chunk
                marker_position = window.find(marker)
                if marker_position != -1:
                    return absolute_chunk_start - len(overlap) + marker_position + len(marker)

                overlap = chunk[-(len(marker) - 1):] if len(marker) > 1 else b""
                absolute_chunk_start += len(chunk)

            return None

    def _read_from_offset(self, start_offset: int, end_offset: int | None = None) -> bytes:
        with ImageReader(self.image_path) as image:
            if end_offset is None:
                end_offset = image.size

            if end_offset <= start_offset:
                return b""

            target_length = end_offset - start_offset
            data = bytearray()
            read_size = self.chunk_size

            for chunk in image.iter_chunks(read_size, start_offset):
                remaining = target_length - len(data)
                if remaining <= 0:
                    break
                data.extend(chunk[:remaining])
                if len(data) >= target_length:
                    break

            return bytes(data)
