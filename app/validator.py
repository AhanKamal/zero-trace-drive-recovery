from __future__ import annotations

from dataclasses import dataclass, field

try:
    from PIL import Image
    from PIL import UnidentifiedImageError
except ImportError:  # pragma: no cover - Pillow is a dependency for production JPEG validation
    Image = None
    UnidentifiedImageError = Exception


@dataclass
class ValidationResult:
    is_valid: bool
    status: str
    file_type: str
    size: int
    has_valid_header: bool
    has_eoi_marker: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class JPEGValidator:
    def __init__(self, file_bytes: bytes) -> None:
        self.file_bytes = file_bytes

    def validate(self) -> ValidationResult:
        data = self.file_bytes
        errors: list[str] = []
        warnings: list[str] = []

        if not data:
            return ValidationResult(
                is_valid=False,
                status="INVALID",
                file_type="JPEG",
                size=0,
                has_valid_header=False,
                has_eoi_marker=False,
                errors=["File is empty."],
                warnings=[],
            )

        has_valid_header = data.startswith(b"\xff\xd8\xff")
        has_eoi_marker = b"\xff\xd9" in data

        if not has_valid_header:
            errors.append("Missing JPEG SOI marker (FF D8 FF).")

        if len(data) < 3:
            errors.append("File is too small to be a valid JPEG header.")

        if len(data) < 10 and has_valid_header:
            warnings.append("JPEG header present but payload is extremely small.")

        if not has_eoi_marker and has_valid_header:
            warnings.append("Missing JPEG EOI marker (FF D9); file may be partial.")

        decodable = False
        if has_valid_header and Image is not None:
            try:
                from io import BytesIO

                with Image.open(BytesIO(data)) as image:
                    image.verify()
                decodable = True
            except (OSError, ValueError, TypeError, UnidentifiedImageError):
                errors.append("JPEG starts with a valid marker but is not a decodable image.")

        if has_valid_header and not has_eoi_marker:
            status = "PARTIAL"
            is_valid = False
        elif has_valid_header and has_eoi_marker and decodable:
            status = "VALID"
            is_valid = True
        elif has_valid_header and has_eoi_marker and not decodable:
            status = "INVALID"
            is_valid = False
            errors.append("JPEG markers are present but the payload is not a decodable image.")
        else:
            status = "INVALID"
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            status=status,
            file_type="JPEG",
            size=len(data),
            has_valid_header=has_valid_header,
            has_eoi_marker=has_eoi_marker,
            errors=errors,
            warnings=warnings,
        )
