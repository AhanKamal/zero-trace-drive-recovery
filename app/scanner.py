from __future__ import annotations

from dataclasses import dataclass

from app.image_reader import ImageReader
from app.signatures import SignatureRegistry


@dataclass(frozen=True)
class CandidateFragment:
    candidate_id: str
    file_type: str
    offset: int
    matched_signature: bytes


class SignatureScanner:
    def __init__(self, image_path: str, chunk_size: int = 4096) -> None:
        self.image_path = image_path
        self.chunk_size = chunk_size
        self.registry = SignatureRegistry()

        if chunk_size <= 0:
            raise ValueError("chunk_size must be > 0")

    def scan(self) -> list[CandidateFragment]:
        candidates: list[CandidateFragment] = []
        max_signature_length = max(len(sig.byte_signature) for sig in self.registry.definitions)
        seen: set[tuple[str, int, bytes]] = set()

        with ImageReader(self.image_path) as image:
            if image.size == 0:
                return []

            overlap = b""
            current_offset = 0

            for chunk in image.iter_chunks(self.chunk_size):
                data = overlap + chunk
                window_start = max(0, current_offset - len(overlap))

                for sig in self.registry.definitions:
                    pattern = sig.byte_signature
                    for position in range(len(data) - len(pattern) + 1):
                        if not data.startswith(pattern, position):
                            continue

                        if position + len(pattern) <= len(overlap):
                            continue

                        offset = window_start + position
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
