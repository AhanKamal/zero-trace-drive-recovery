from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from app.carver import FormatCarver
from app.image_reader import ImageReader, RawDataSource
from app.reconstruction import Fragment, ReconstructionEngine
from app.scanner import SignatureScanner
from app.signatures import SignatureRegistry
from app.validator import BMPValidator, GIFValidator, JPEGValidator, MP3Validator, MP4Validator, PDFValidator, PNGValidator, TIFFValidator, WebPValidator


@dataclass
class RecoveryArtifact:
    recovery_id: str
    file_type: str
    source_offset: int
    output_path: str
    status: str
    size: int
    confidence: float = 0.0
    validation_status: str = "UNKNOWN"
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


@dataclass
class RecoveryResult:
    source_image: str
    output_dir: str
    recovered_files: list[RecoveryArtifact] = field(default_factory=list)
    candidates_found: int = 0
    raw_signature_hits: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class RecoveryEngine:
    def __init__(self, image_path: str | Path, output_dir: str | Path, chunk_size: int = 4096, max_gap_size: int = 256, reader_factory: Callable[[], RawDataSource] | None = None) -> None:
        self.image_path = Path(image_path)
        self.output_dir = Path(output_dir)
        self.chunk_size = chunk_size
        self.max_gap_size = max_gap_size
        self.registry = SignatureRegistry()
        self._custom_reader = reader_factory is not None
        self.reader_factory = reader_factory or (lambda: ImageReader(self.image_path))

    def recover(self) -> RecoveryResult:
        if not self._custom_reader:
            if not self.image_path.exists():
                raise FileNotFoundError(f"Image file not found: {self.image_path}")
            if not self.image_path.is_file():
                raise ValueError(f"Not a file: {self.image_path}")

        with self.reader_factory() as image:
            if image.size == 0:
                return RecoveryResult(
                    source_image=str(self.image_path),
                    output_dir=str(self.output_dir),
                    warnings=["Source image is empty; no supported file data found."],
                    errors=[],
                )

        scanner = SignatureScanner(str(self.image_path), chunk_size=self.chunk_size, reader_factory=self.reader_factory)
        candidates = scanner.scan()
        supported_types = {definition.file_type for definition in self.registry.supported_definitions}
        supported_candidates = [candidate for candidate in candidates if candidate.file_type in supported_types]

        if not supported_candidates:
            return RecoveryResult(
                source_image=str(self.image_path),
                output_dir=str(self.output_dir),
                candidates_found=0,
                raw_signature_hits=len(candidates),
                warnings=["No recoverable JPEG signatures or other supported signatures found in the source image."],
                errors=[],
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        carved_files = []
        for file_type in sorted(supported_types):
            carver = FormatCarver(
                self.image_path,
                self.output_dir,
                chunk_size=self.chunk_size,
                file_type=file_type,
                recovery_id_offset=len(carved_files),
                reader_factory=self.reader_factory,
            )
            carved_files.extend(carver.recover())

        if not carved_files:
            return RecoveryResult(
                source_image=str(self.image_path),
                output_dir=str(self.output_dir),
                candidates_found=len(supported_candidates),
                raw_signature_hits=len(supported_candidates),
                warnings=["Supported signatures were present, but no complete or partial files could be carved."],
                errors=[],
            )

        recovered_files: list[RecoveryArtifact] = []
        warnings: list[str] = []
        errors: list[str] = []

        for carved_file in carved_files:
            if carved_file.recovered_size <= 0:
                warnings.append(f"Skipping empty carved candidate at offset {carved_file.source_offset}.")
                continue

            file_path = Path(carved_file.output_path)
            if not file_path.exists():
                errors.append(f"Recovered file missing on disk: {file_path}")
                continue

            payload = file_path.read_bytes()
            if len(payload) == 0:
                warnings.append(f"Skipping zero-length carved candidate at offset {carved_file.source_offset}.")
                continue

            validator = _make_validator(carved_file.file_type, payload)
            validation = validator.validate()

            if validation.has_valid_header:
                reconstruction = ReconstructionEngine(
                    self.image_path,
                    self.output_dir,
                    chunk_size=self.chunk_size,
                    max_gap_size=self.max_gap_size,
                    file_type=carved_file.file_type,
                )
                fragment = Fragment(
                    fragment_id=carved_file.recovery_id,
                    source_offset=carved_file.source_offset,
                    size=len(payload),
                    data=payload,
                    file_type=carved_file.file_type,
                )
                result = reconstruction.reconstruct([fragment], recovery_id=carved_file.recovery_id)
                status = result.status
                confidence = result.confidence
                warnings.extend(result.warnings)
                errors.extend(result.errors)
                output_path = result.output_path
            else:
                status = validation.status
                confidence = 0.0
                warnings.extend(validation.warnings)
                errors.extend(validation.errors)
                output_path = str(file_path)

            recovered_files.append(
                RecoveryArtifact(
                    recovery_id=carved_file.recovery_id,
                    file_type=carved_file.file_type,
                    source_offset=carved_file.source_offset,
                    output_path=output_path,
                    status=status,
                    size=len(payload),
                    confidence=confidence,
                    validation_status=validation.status,
                    warnings=list(dict.fromkeys(warnings)),
                    errors=list(dict.fromkeys(errors)),
                )
            )

        return RecoveryResult(
            source_image=str(self.image_path),
            output_dir=str(self.output_dir),
            recovered_files=recovered_files,
            candidates_found=len(carved_files),
            raw_signature_hits=len(supported_candidates),
            warnings=list(dict.fromkeys(warnings)),
            errors=list(dict.fromkeys(errors)),
        )


def _make_validator(file_type: str, data: bytes):
    if file_type == "PNG":
        return PNGValidator(data)
    if file_type == "PDF":
        return PDFValidator(data)
    if file_type == "MP3":
        return MP3Validator(data)
    if file_type == "MP4":
        return MP4Validator(data)
    if file_type == "GIF":
        return GIFValidator(data)
    if file_type == "BMP":
        return BMPValidator(data)
    if file_type == "TIFF":
        return TIFFValidator(data)
    if file_type == "WEBP":
        return WebPValidator(data)
    return JPEGValidator(data)
