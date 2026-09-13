from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.carver import JPEGCarver
from app.image_reader import ImageReader
from app.reconstruction import Fragment, ReconstructionEngine
from app.scanner import SignatureScanner
from app.validator import JPEGValidator


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
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


class RecoveryEngine:
    def __init__(self, image_path: str | Path, output_dir: str | Path, chunk_size: int = 4096, max_gap_size: int = 256) -> None:
        self.image_path = Path(image_path)
        self.output_dir = Path(output_dir)
        self.chunk_size = chunk_size
        self.max_gap_size = max_gap_size

    def recover(self) -> RecoveryResult:
        if not self.image_path.exists():
            raise FileNotFoundError(f"Image file not found: {self.image_path}")
        if not self.image_path.is_file():
            raise ValueError(f"Not a file: {self.image_path}")

        with ImageReader(self.image_path) as image:
            if image.size == 0:
                return RecoveryResult(
                    source_image=str(self.image_path),
                    output_dir=str(self.output_dir),
                    warnings=["Source image is empty; no recoverable JPEG data found."],
                    errors=[],
                )

        scanner = SignatureScanner(str(self.image_path), chunk_size=self.chunk_size)
        candidates = scanner.scan()
        jpeg_candidates = [candidate for candidate in candidates if candidate.file_type == "JPEG"]

        if not jpeg_candidates:
            return RecoveryResult(
                source_image=str(self.image_path),
                output_dir=str(self.output_dir),
                candidates_found=0,
                warnings=["No recoverable JPEG signatures found in the source image."],
                errors=[],
            )

        self.output_dir.mkdir(parents=True, exist_ok=True)
        carver = JPEGCarver(self.image_path, self.output_dir, chunk_size=self.chunk_size)
        carved_files = carver.recover()

        if not carved_files:
            return RecoveryResult(
                source_image=str(self.image_path),
                output_dir=str(self.output_dir),
                candidates_found=len(jpeg_candidates),
                warnings=["JPEG signatures were present, but no complete or partial JPEGs could be carved."],
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

            validator = JPEGValidator(payload)
            validation = validator.validate()

            if validation.has_valid_header:
                reconstruction = ReconstructionEngine(
                    self.image_path,
                    self.output_dir,
                    chunk_size=self.chunk_size,
                    max_gap_size=self.max_gap_size,
                )
                fragment = Fragment(
                    fragment_id=carved_file.recovery_id,
                    source_offset=carved_file.source_offset,
                    size=len(payload),
                    data=payload,
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
            candidates_found=len(jpeg_candidates),
            warnings=list(dict.fromkeys(warnings)),
            errors=list(dict.fromkeys(errors)),
        )
