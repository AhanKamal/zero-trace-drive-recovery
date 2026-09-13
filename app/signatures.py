from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignatureDefinition:
    file_type: str
    name: str
    byte_signature: bytes


class SignatureRegistry:
    """Registry for raw signature detection definitions."""

    def __init__(self) -> None:
        self._definitions: list[SignatureDefinition] = [
            SignatureDefinition("JPEG", "JPEG image", b"\xFF\xD8\xFF"),
            SignatureDefinition("PNG", "PNG image", b"\x89PNG\r\n\x1a\n"),
            SignatureDefinition("PDF", "PDF document", b"%PDF-"),
            SignatureDefinition("ZIP", "ZIP archive", b"PK\x03\x04"),
        ]

    @property
    def definitions(self) -> list[SignatureDefinition]:
        return list(self._definitions)
