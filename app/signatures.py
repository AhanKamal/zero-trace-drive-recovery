from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SignatureDefinition:
    file_type: str
    name: str
    byte_signature: bytes
    extension: str = ""
    footer_signature: bytes | None = None
    supported: bool = False
    alternate_signatures: tuple[bytes, ...] = ()
    signature_offset: int = 0

    @property
    def signatures(self) -> tuple[bytes, ...]:
        return (self.byte_signature, *self.alternate_signatures)


class SignatureRegistry:
    """Registry for raw signature detection definitions."""

    def __init__(self) -> None:
        self._definitions: list[SignatureDefinition] = [
            SignatureDefinition("JPEG", "JPEG image", b"\xFF\xD8\xFF", ".jpg", b"\xFF\xD9", True),
            SignatureDefinition("PNG", "PNG image", b"\x89PNG\r\n\x1a\n", ".png", b"IEND\xaeB`\x82", True),
            SignatureDefinition("PDF", "PDF document", b"%PDF-", ".pdf", b"%%EOF", True),
            SignatureDefinition(
                "MP3",
                "MP3 audio",
                b"ID3",
                ".mp3",
                supported=True,
                alternate_signatures=(b"\xff\xfa", b"\xff\xfb", b"\xff\xf2", b"\xff\xf3", b"\xff\xe2", b"\xff\xe3"),
            ),
            SignatureDefinition("MP4", "MP4 video", b"ftyp", ".mp4", supported=True),
            SignatureDefinition("GIF", "GIF image", b"GIF87a", ".gif", b"\x3b", True, (b"GIF89a",)),
            SignatureDefinition("BMP", "BMP image", b"BM", ".bmp", supported=True),
            SignatureDefinition("TIFF", "TIFF image", b"II*\x00", ".tif", supported=True, alternate_signatures=(b"MM\x00*",)),
            SignatureDefinition("WEBP", "WebP image", b"WEBP", ".webp", supported=True, signature_offset=8),
            SignatureDefinition("ZIP", "ZIP archive", b"PK\x03\x04", ".zip"),
        ]

    @property
    def definitions(self) -> list[SignatureDefinition]:
        return list(self._definitions)

    def get(self, file_type: str) -> SignatureDefinition:
        for definition in self._definitions:
            if definition.file_type == file_type:
                return definition
        raise KeyError(f"Unsupported file type: {file_type}")

    @property
    def supported_definitions(self) -> list[SignatureDefinition]:
        return [definition for definition in self._definitions if definition.supported]
