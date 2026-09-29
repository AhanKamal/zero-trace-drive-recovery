from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from app.image_reader import ImageReader
from app.image_reader import RawDataSource
from app.scanner import SignatureScanner
from app.signatures import SignatureRegistry
from app.validator import parse_bmp, parse_gif, parse_mp3_frames, parse_mp4_boxes, parse_tiff, parse_webp


@dataclass(frozen=True)
class RecoveredFile:
    recovery_id: str
    file_type: str
    source_offset: int
    recovered_size: int
    output_path: str
    status: str


class FormatCarver:
    def __init__(self, image_path: str | Path, output_dir: str | Path = "recovered", chunk_size: int = 4096, file_type: str = "JPEG", recovery_id_offset: int = 0, reader_factory: Callable[[], RawDataSource] | None = None) -> None:
        self.image_path = Path(image_path)
        self.output_dir = Path(output_dir)
        self.chunk_size = chunk_size
        self.file_type = file_type
        self.recovery_id_offset = recovery_id_offset
        self.definition = SignatureRegistry().get(file_type)
        self.reader_factory = reader_factory or (lambda: ImageReader(self.image_path))
        self.scanner = SignatureScanner(str(self.image_path), chunk_size=chunk_size, reader_factory=self.reader_factory)

    def recover(self) -> list[RecoveredFile]:
        self.output_dir.mkdir(parents=True, exist_ok=True)

        candidates = sorted(
            (candidate for candidate in self.scanner.scan() if candidate.file_type == self.file_type),
            key=lambda candidate: candidate.offset,
        )

        recovered: list[RecoveredFile] = []
        covered_ranges: list[tuple[int, int]] = []

        for offset_index, candidate in enumerate(candidates, start=1):
            start = self._candidate_start(candidate.offset)
            end = self._find_file_end(start)

            if any(existing_start <= start < existing_end for existing_start, existing_end in covered_ranges):
                continue

            if end is not None and any(start < existing_end and existing_start < end for existing_start, existing_end in covered_ranges):
                continue

            if end is None:
                partial_end = self._find_partial_end(start)
                data = self._read_from_offset(start, partial_end)
                status = "PARTIAL"
            else:
                data = self._read_from_offset(start, end)
                status = "RECOVERED"

            if not data:
                continue

            recovery_id = f"REC-{self.recovery_id_offset + len(recovered) + 1:04d}"
            output_path = self.output_dir / f"{recovery_id}{self.definition.extension}"
            output_path.write_bytes(data)

            recovered.append(
                RecoveredFile(
                    recovery_id=recovery_id,
                    file_type=self.file_type,
                    source_offset=start,
                    recovered_size=len(data),
                    output_path=str(output_path),
                    status=status,
                )
            )
            covered_ranges.append((start, start + len(data)))

        return recovered

    def _find_file_end(self, start_offset: int) -> int | None:
        if self.file_type == "PNG":
            return self._find_png_end(start_offset)
        if self.file_type == "PDF":
            return self._find_pdf_end(start_offset)
        if self.file_type == "MP3":
            return self._find_mp3_end(start_offset)
        if self.file_type == "MP4":
            return self._find_mp4_end(start_offset)
        if self.file_type == "GIF":
            return self._find_gif_end(start_offset)
        if self.file_type == "BMP":
            return self._find_bmp_end(start_offset)
        if self.file_type == "TIFF":
            return self._find_tiff_end(start_offset)
        if self.file_type == "WEBP":
            return self._find_webp_end(start_offset)

        return self._find_jpeg_end(start_offset)

    def _find_partial_end(self, start_offset: int) -> int | None:
        if self.file_type == "MP3":
            return self._find_next_non_mp3_candidate_offset(start_offset)
        if self.file_type == "MP4":
            return self._find_next_non_mp4_candidate_offset(start_offset)
        if self.file_type == "GIF":
            return self._find_next_non_gif_candidate_offset(start_offset)
        if self.file_type == "BMP":
            return self._find_next_candidate_offset(start_offset)
        if self.file_type == "TIFF":
            return self._find_next_candidate_offset(start_offset)
        if self.file_type == "WEBP":
            return self._find_next_candidate_offset(start_offset)
        if self.file_type != "PDF":
            return None
        return self._find_next_candidate_offset(start_offset)

    def _find_png_end(self, start_offset: int) -> int | None:
        data = self._read_from_offset(start_offset)
        position = 8

        while position + 12 <= len(data):
            length = int.from_bytes(data[position:position + 4], "big")
            chunk_end = position + 12 + length
            if chunk_end > len(data):
                return None
            if data[position + 4:position + 8] == b"IEND":
                return start_offset + chunk_end
            position = chunk_end

        return None

    def _find_pdf_end(self, start_offset: int) -> int | None:
        next_offset = self._find_next_candidate_offset(start_offset)
        data = self._read_from_offset(start_offset, next_offset)
        eof_positions: list[int] = []
        search_start = 0

        while True:
            position = data.find(b"%%EOF", search_start)
            if position == -1:
                break
            prefix = data[:position]
            if b"trailer" in prefix and b"startxref" in prefix:
                eof_positions.append(position)
            search_start = position + 1

        if not eof_positions:
            return None

        end = eof_positions[-1] + len(b"%%EOF")
        while end < len(data) and data[end] in b" \t\r\n":
            end += 1
        return start_offset + end

    def _find_next_candidate_offset(self, start_offset: int) -> int | None:
        offsets = [candidate.offset for candidate in self.scanner.scan() if candidate.offset > start_offset]
        return min(offsets) if offsets else None

    def _find_next_non_mp3_candidate_offset(self, start_offset: int) -> int | None:
        offsets = [
            candidate.offset
            for candidate in self.scanner.scan()
            if candidate.offset > start_offset and candidate.file_type != "MP3"
        ]
        return min(offsets) if offsets else None

    def _find_next_non_mp4_candidate_offset(self, start_offset: int) -> int | None:
        offsets = [
            self._candidate_start(candidate.offset)
            for candidate in self.scanner.scan()
            if candidate.offset > start_offset + 4 and candidate.file_type != "MP4"
        ]
        return min(offsets) if offsets else None

    def _find_next_non_gif_candidate_offset(self, start_offset: int) -> int | None:
        offsets = [
            candidate.offset
            for candidate in self.scanner.scan()
            if candidate.offset > start_offset and candidate.file_type != "GIF"
        ]
        return min(offsets) if offsets else None

    def _find_mp3_end(self, start_offset: int) -> int | None:
        data = self._read_from_offset(start_offset)
        frames, incomplete, stream_end = parse_mp3_frames(data)
        if not frames or incomplete:
            return None
        return start_offset + stream_end

    def _find_mp4_end(self, start_offset: int) -> int | None:
        next_offset = self._find_next_candidate_offset(start_offset + 4)
        data = self._read_from_offset(start_offset, next_offset)
        parsed = parse_mp4_boxes(data)
        box_types = {box.box_type for box in parsed.boxes}
        if not parsed.boxes or parsed.boxes[0].box_type != b"ftyp":
            return None
        if parsed.complete:
            return start_offset + parsed.end_offset
        if parsed.error and {b"moov", b"mdat"}.issubset(box_types) and (
            "printable ASCII" in parsed.error
            or "extends beyond" in parsed.error
            or "shorter than" in parsed.error
        ):
            return start_offset + parsed.end_offset
        return None

    def _find_gif_end(self, start_offset: int) -> int | None:
        data = self._read_from_offset(start_offset)
        parsed = parse_gif(data)
        if parsed.complete and parsed.image_count > 0:
            return start_offset + parsed.end_offset
        return None

    def _find_bmp_end(self, start_offset: int) -> int | None:
        data = self._read_from_offset(start_offset)
        parsed = parse_bmp(data)
        if parsed.complete:
            return start_offset + parsed.file_size
        return None

    def _find_tiff_end(self, start_offset: int) -> int | None:
        data = self._read_from_offset(start_offset)
        parsed = parse_tiff(data)
        if parsed.complete:
            return start_offset + parsed.end_offset
        return None

    def _find_webp_end(self, start_offset: int) -> int | None:
        data = self._read_from_offset(start_offset)
        parsed = parse_webp(data)
        if parsed.complete:
            return start_offset + parsed.end_offset
        return None

    def _candidate_start(self, candidate_offset: int) -> int:
        if self.file_type == "MP4" and candidate_offset >= 4:
            return candidate_offset - 4
        return candidate_offset

    def _find_jpeg_end(self, start_offset: int) -> int | None:
        with self.reader_factory() as image:
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
        with self.reader_factory() as image:
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


class JPEGCarver(FormatCarver):
    def __init__(self, image_path: str | Path, output_dir: str | Path = "recovered", chunk_size: int = 4096) -> None:
        super().__init__(image_path, output_dir, chunk_size, file_type="JPEG")


class PNGCarver(FormatCarver):
    def __init__(self, image_path: str | Path, output_dir: str | Path = "recovered", chunk_size: int = 4096) -> None:
        super().__init__(image_path, output_dir, chunk_size, file_type="PNG")
