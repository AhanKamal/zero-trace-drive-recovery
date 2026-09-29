from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.image_reader import ImageReader, RawDataSource
from app.signatures import SignatureRegistry


@dataclass(frozen=True)
class CandidateFragment:
    candidate_id: str
    file_type: str
    offset: int
    matched_signature: bytes


class SignatureScanner:
    def __init__(self, image_path: str, chunk_size: int = 4096, reader_factory: Callable[[], RawDataSource] | None = None) -> None:
        self.image_path = image_path
        self.chunk_size = chunk_size
        self.registry = SignatureRegistry()
        self.reader_factory = reader_factory or (lambda: ImageReader(self.image_path))

        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")

    def scan(self) -> list[CandidateFragment]:
        candidates: list[CandidateFragment] = []
        max_signature_length = max(
            len(pattern)
            for signature in self.registry.definitions
            for pattern in signature.signatures
        )
        seen: set[tuple[str, int, bytes]] = set()

        with self.reader_factory() as image:
            if image.size == 0:
                return []

            overlap = b""
            current_offset = 0

            for chunk in image.iter_chunks(self.chunk_size):
                data = overlap + chunk
                window_start = max(0, current_offset - len(overlap))

                for sig in self.registry.definitions:
                    for pattern in sig.signatures:
                        for position in range(len(data) - len(pattern) + 1):
                            if not data.startswith(pattern, position):
                                continue

                            if position + len(pattern) <= len(overlap):
                                continue

                            offset = window_start + position - sig.signature_offset
                            if offset < 0:
                                continue
                            key = (sig.file_type, offset, pattern)
                            if key in seen:
                                continue

                            seen.add(key)
                            candidates.append(
                                CandidateFragment(
                                    candidate_id=f"{sig.file_type}-{offset}",
                                    file_type=sig.file_type,
                                    offset=offset,
                                    matched_signature=pattern,
                                )
                            )

                overlap = data[-(max_signature_length - 1):] if max_signature_length > 1 else b""
                current_offset += len(chunk)

        return candidates
