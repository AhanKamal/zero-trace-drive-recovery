from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.image_reader import ImageReader
from app.validator import JPEGValidator


@dataclass(frozen=True)
class Fragment:
    fragment_id: str
    source_offset: int
    size: int
    data: bytes


@dataclass
class ReconstructionResult:
    recovery_id: str
    file_type: str
    fragments_used: int
    total_size: int
    status: str
    confidence: float
    output_path: str
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    fragments_considered: list[str] = field(default_factory=list)
    fragments_selected: list[str] = field(default_factory=list)
    source_offsets: list[int] = field(default_factory=list)
    gaps: list[int] = field(default_factory=list)


def calculate_confidence(
    *,
    has_valid_header: bool,
    has_eoi_marker: bool,
    ordered: bool,
    fragment_count: int,
    continuity_ratio: float,
) -> float:
    """Transparent confidence scoring for reconstructed JPEG candidates.

    Weighting is intentionally simple and deterministic:
    - valid JPEG header: 0.35
    - valid JPEG EOI marker: 0.35
    - fragments in ascending offset order: 0.10
    - multiple fragments accepted: 0.10
    - continuity score (0.0 to 1.0): 0.10
    """

    if not has_valid_header and not has_eoi_marker:
        return 0.0

    score = 0.0
    score += 0.35 if has_valid_header else 0.0
    score += 0.35 if has_eoi_marker else 0.0
    score += 0.10 if ordered else 0.0
    score += 0.10 if fragment_count > 1 else 0.0
    score += 0.10 * continuity_ratio

    return round(max(0.0, min(1.0, score)), 3)


class ReconstructionEngine:
    def __init__(self, image_path: str | Path, output_dir: str | Path = "reconstructed", chunk_size: int = 4096, max_gap_size: int = 256) -> None:
        self.image_path = Path(image_path)
        self.output_dir = Path(output_dir)
        self.chunk_size = chunk_size
        self.max_gap_size = max_gap_size

    def reconstruct(self, fragments: list[Fragment], recovery_id: str = "REC-0001") -> ReconstructionResult:
        if not fragments:
            return ReconstructionResult(
                recovery_id=recovery_id,
                file_type="JPEG",
                fragments_used=0,
                total_size=0,
                status="REJECTED",
                confidence=0.0,
                output_path=str(self.output_dir / f"{recovery_id}.jpg"),
                warnings=["No fragments supplied."],
                errors=["Reconstruction refused: no candidate fragments available."],
            )

        considered = [fragment.fragment_id for fragment in fragments]
        ordered_fragments = sorted(fragments, key=lambda f: f.source_offset)
        selected, gaps, warnings, errors = self._select_candidate_fragments(ordered_fragments)

        if errors:
            return ReconstructionResult(
                recovery_id=recovery_id,
                file_type="JPEG",
                fragments_used=len(selected),
                total_size=0,
                status="REJECTED",
                confidence=0.0,
                output_path=str(self.output_dir / f"{recovery_id}.jpg"),
                warnings=warnings,
                errors=errors,
                fragments_considered=considered,
                fragments_selected=[fragment.fragment_id for fragment in selected],
                source_offsets=[fragment.source_offset for fragment in selected],
                gaps=gaps,
            )

        assembled = b"".join(fragment.data for fragment in selected)
        validator = JPEGValidator(assembled)
        validation = validator.validate()

        if validation.is_valid:
            if len(selected) <= 2 and any(gap > self.max_gap_size for gap in gaps):
                status = "PARTIAL"
                errors = []
                warnings = warnings + ["Large gaps suggest the reconstruction is too sparse to be a trustworthy complete JPEG."]
            else:
                status = "RECONSTRUCTED"
                errors = []
                warnings = warnings or []
        elif validation.status == "PARTIAL":
            status = "PARTIAL"
            errors = []
            warnings = warnings + ["Reconstruction exists but is incomplete."]
        else:
            status = "REJECTED"
            errors = validation.errors or ["Reconstructed bytes are not a valid JPEG."]
            warnings = warnings + (validation.warnings or ["Reconstruction did not validate."])

        confidence = calculate_confidence(
            has_valid_header=validation.has_valid_header,
            has_eoi_marker=validation.has_eoi_marker,
            ordered=self._validate_fragment_order(selected),
            fragment_count=len(selected),
            continuity_ratio=self._gap_ratio(gaps, selected),
        )

        output_path = self.output_dir / f"{recovery_id}.jpg"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if status in {"RECONSTRUCTED", "PARTIAL"}:
            output_path.write_bytes(assembled)

        return ReconstructionResult(
            recovery_id=recovery_id,
            file_type="JPEG",
            fragments_used=len(selected),
            total_size=len(assembled),
            status=status,
            confidence=confidence,
            output_path=str(output_path),
            warnings=warnings,
            errors=errors,
            fragments_considered=considered,
            fragments_selected=[fragment.fragment_id for fragment in selected],
            source_offsets=[fragment.source_offset for fragment in selected],
            gaps=gaps,
        )

    def _select_candidate_fragments(self, fragments: list[Fragment]) -> tuple[list[Fragment], list[int], list[str], list[str]]:
        if not fragments:
            return [], [], [], ["No fragments available."]

        seed = None
        for fragment in fragments:
            if fragment.data.startswith(b"\xff\xd8\xff"):
                seed = fragment
                break

        if seed is None:
            return [], [], [], ["Reconstruction requires an explicit JPEG SOI marker at the start of the candidate stream."]

        selected: list[Fragment] = [seed]
        warnings: list[str] = []
        gaps: list[int] = []
        errors: list[str] = []

        last_end = seed.source_offset + seed.size
        for fragment in fragments:
            if fragment.fragment_id == seed.fragment_id:
                continue

            if fragment.data.startswith(b"\xff\xd8\xff"):
                errors.append(f"Fragment {fragment.fragment_id} starts with a second JPEG SOI marker; ambiguous candidate rejected.")
                continue

            if not self._looks_like_jpeg_fragment(fragment.data):
                errors.append(f"Fragment {fragment.fragment_id} lacks explicit JPEG structural evidence and was rejected.")
                continue

            if fragment.source_offset < last_end:
                warnings.append(f"Fragment {fragment.fragment_id} overlaps a previously selected region and was ignored.")
                continue

            gap = fragment.source_offset - last_end
            if gap > self.max_gap_size:
                warnings.append(
                    f"Fragment {fragment.fragment_id} is separated by a large gap of {gap} bytes; preserving non-contiguous forensic evidence."
                )

            selected.append(fragment)
            gaps.append(gap)
            last_end = fragment.source_offset + fragment.size

        if len(selected) > 1 and selected[0].data.startswith(b"\xff\xd8\xff") and selected[-1].data.endswith(b"\xff\xd9"):
            pass

        if len(selected) >= 2 and not self._has_completion_evidence(selected):
            warnings.append("Selected fragments do not include enough explicit JPEG-end evidence to confirm a complete reconstruction.")

        if not selected:
            return [], [], warnings, ["No valid fragments selected."]

        if not any(b"\xff\xd9" in fragment.data for fragment in selected):
            warnings.append("No EOI marker was found in the selected fragments; reconstruction remains partial.")

        if len(selected) > 1 and sum(gaps) > 0:
            warnings.append("Selected fragments are non-contiguous; gaps are preserved as forensic metadata only.")

        return selected, gaps, warnings, errors

    def _looks_like_jpeg_fragment(self, data: bytes) -> bool:
        if not data:
            return False

        jpeg_markers = (
            b"\xff\xe0",
            b"\xff\xe1",
            b"\xff\xe2",
            b"\xff\xdb",
            b"\xff\xc0",
            b"\xff\xc4",
            b"\xff\xda",
            b"\xff\xd9",
        )
        if any(marker in data for marker in jpeg_markers):
            return True

        if data.startswith(b"\xff\xd8\xff"):
            return True

        printable = sum(1 for byte in data if 32 <= byte < 127 or byte in (9, 10, 13))
        printable_ratio = printable / len(data)
        if printable_ratio > 0.85:
            return False

        return True

    def _has_completion_evidence(self, selected: list[Fragment]) -> bool:
        if not selected:
            return False
        if len(selected) == 1:
            return selected[0].data.startswith(b"\xff\xd8\xff") and b"\xff\xd9" in selected[0].data

        first = selected[0]
        last = selected[-1]
        return first.data.startswith(b"\xff\xd8\xff") and b"\xff\xd9" in last.data

    def _gap_ratio(self, gaps: list[int], selected: list[Fragment]) -> float:
        if not selected:
            return 0.0
        if len(selected) == 1:
            return 1.0
        total_gap = sum(gaps)
        total_span = max(1, selected[-1].source_offset + selected[-1].size - selected[0].source_offset)
        return round(max(0.0, 1.0 - (total_gap / total_span)), 3)

    def _validate_fragment_order(self, fragments: list[Fragment]) -> bool:
        if len(fragments) <= 1:
            return True
        offsets = [fragment.source_offset for fragment in fragments]
        return offsets == sorted(offsets)

    def read_candidate_fragments(self, image_path: str | Path, candidate_offsets: list[int]) -> list[Fragment]:
        fragments: list[Fragment] = []

        with ImageReader(image_path) as image:
            for index, offset in enumerate(candidate_offsets):
                chunk = image.read(offset, self.chunk_size)
                fragments.append(
                    Fragment(
                        fragment_id=f"FRAG-{index + 1:04d}",
                        source_offset=offset,
                        size=len(chunk),
                        data=chunk,
                    )
                )

        return fragments
