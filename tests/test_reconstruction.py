from io import BytesIO
from pathlib import Path

from PIL import Image

from app.reconstruction import Fragment, ReconstructionEngine, calculate_confidence


def _valid_jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (40, 40), color=(9, 14, 21)).save(buffer, format="JPEG", quality=92)
    return buffer.getvalue()


def test_one_contiguous_jpeg_as_one_fragment(tmp_path: Path) -> None:
    image_path = tmp_path / "single.img"
    jpeg = _valid_jpeg()
    image_path.write_bytes(jpeg)

    engine = ReconstructionEngine(image_path, tmp_path / "output", chunk_size=16)
    fragments = [Fragment("FRAG-0001", 0, len(jpeg), jpeg)]
    result = engine.reconstruct(fragments, recovery_id="REC-0001")

    assert result.status == "RECONSTRUCTED"
    assert result.confidence > 0.8
    assert result.fragments_used == 1
    assert result.total_size == len(jpeg)
    assert result.errors == []


def test_jpeg_split_into_two_fragments(tmp_path: Path) -> None:
    jpeg = _valid_jpeg()
    first = jpeg[:30]
    second = jpeg[30:]

    engine = ReconstructionEngine(tmp_path / "disk.img", tmp_path / "output", chunk_size=16)
    fragments = [
        Fragment("FRAG-0001", 0, len(first), first),
        Fragment("FRAG-0002", len(first), len(second), second),
    ]
    result = engine.reconstruct(fragments, recovery_id="REC-0002")

    assert result.status == "RECONSTRUCTED"
    assert result.fragments_used == 2
    assert result.total_size == len(jpeg)


def test_jpeg_split_into_three_fragments(tmp_path: Path) -> None:
    jpeg = _valid_jpeg()
    parts = [jpeg[:10], jpeg[10:40], jpeg[40:]]

    engine = ReconstructionEngine(tmp_path / "disk.img", tmp_path / "output", chunk_size=16)
    fragments = [
        Fragment("FRAG-0001", 0, len(parts[0]), parts[0]),
        Fragment("FRAG-0002", len(parts[0]), len(parts[1]), parts[1]),
        Fragment("FRAG-0003", len(parts[0]) + len(parts[1]), len(parts[2]), parts[2]),
    ]
    result = engine.reconstruct(fragments, recovery_id="REC-0003")

    assert result.status == "RECONSTRUCTED"
    assert result.fragments_used == 3


def test_fragments_in_correct_disk_order() -> None:
    jpeg = _valid_jpeg()
    first = jpeg[:20]
    second = jpeg[20:]

    engine = ReconstructionEngine("disk.img", "output", chunk_size=8, max_gap_size=4096)
    fragments = [
        Fragment("FRAG-0001", 10, len(first), first),
        Fragment("FRAG-0002", 30, len(second), second),
    ]
    result = engine.reconstruct(fragments, recovery_id="REC-0004")

    assert result.status == "RECONSTRUCTED"
    assert result.fragments_used == 2
    assert result.source_offsets == [10, 30]


def test_fragments_supplied_in_shuffled_order() -> None:
    jpeg = _valid_jpeg()
    first = jpeg[:25]
    second = jpeg[25:]

    engine = ReconstructionEngine("disk.img", "output", chunk_size=8)
    fragments = [
        Fragment("FRAG-0002", 25, len(second), second),
        Fragment("FRAG-0001", 0, len(first), first),
    ]
    result = engine.reconstruct(fragments, recovery_id="REC-0005")

    assert result.status == "RECONSTRUCTED"
    assert result.fragments_used == 2


def test_missing_fragment_rejected() -> None:
    jpeg = _valid_jpeg()
    first = jpeg[:20]

    engine = ReconstructionEngine("disk.img", "output", chunk_size=8)
    fragments = [Fragment("FRAG-0001", 0, len(first), first)]
    result = engine.reconstruct(fragments, recovery_id="REC-0006")

    assert result.status in {"PARTIAL", "REJECTED"}
    assert result.confidence < 1.0


def test_invalid_jpeg_fragment_rejected() -> None:
    engine = ReconstructionEngine("disk.img", "output", chunk_size=8)
    fragments = [Fragment("FRAG-0001", 0, 10, b"not a jpeg")]
    result = engine.reconstruct(fragments, recovery_id="REC-0007")

    assert result.status == "REJECTED"
    assert result.errors


def test_wrong_unrelated_fragment_rejected() -> None:
    engine = ReconstructionEngine("disk.img", "output", chunk_size=8)
    fragments = [Fragment("FRAG-0001", 0, 12, b"hello world\n")]
    result = engine.reconstruct(fragments, recovery_id="REC-0008")

    assert result.status == "REJECTED"
    assert result.confidence == 0.0


def test_reconstruction_validated_by_jpeg_validator() -> None:
    jpeg = _valid_jpeg()
    engine = ReconstructionEngine("disk.img", "output", chunk_size=8)
    fragments = [Fragment("FRAG-0001", 0, len(jpeg), jpeg)]
    result = engine.reconstruct(fragments, recovery_id="REC-0009")

    assert result.status == "RECONSTRUCTED"
    assert result.confidence >= 0.8


def test_reconstruction_marked_partial() -> None:
    partial = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    engine = ReconstructionEngine("disk.img", "output", chunk_size=8)
    fragments = [Fragment("FRAG-0001", 0, len(partial), partial)]
    result = engine.reconstruct(fragments, recovery_id="REC-0010")

    assert result.status == "PARTIAL"
    assert result.confidence < 0.8


def test_reconstruction_marked_rejected() -> None:
    engine = ReconstructionEngine("disk.img", "output", chunk_size=8)
    fragments = [Fragment("FRAG-0001", 0, 5, b"abcde")]
    result = engine.reconstruct(fragments, recovery_id="REC-0011")

    assert result.status == "REJECTED"


def test_confidence_score_behavior() -> None:
    score_valid = calculate_confidence(
        has_valid_header=True,
        has_eoi_marker=True,
        ordered=True,
        fragment_count=2,
        continuity_ratio=1.0,
    )
    score_partial = calculate_confidence(
        has_valid_header=True,
        has_eoi_marker=False,
        ordered=True,
        fragment_count=2,
        continuity_ratio=0.8,
    )

    assert score_valid > score_partial
    assert 0.0 <= score_valid <= 1.0
    assert 0.0 <= score_partial <= 1.0


def test_non_contiguous_jpeg_fragments_can_reconstruct() -> None:
    jpeg = _valid_jpeg()
    part_a = jpeg[:25]
    part_b = jpeg[25:60]
    part_c = jpeg[60:]

    engine = ReconstructionEngine("disk.img", "output", chunk_size=16, max_gap_size=128)
    fragments = [
        Fragment("FRAG-0001", 1000, len(part_a), part_a),
        Fragment("FRAG-0002", 1100, len(part_b), part_b),
        Fragment("FRAG-0003", 1300, len(part_c), part_c),
    ]

    result = engine.reconstruct(fragments, recovery_id="REC-0012")

    assert result.status == "RECONSTRUCTED"
    assert result.fragments_used == 3
    assert result.source_offsets == [1000, 1100, 1300]
    assert result.gaps[0] >= 0
    assert result.gaps[1] >= 0


def test_non_contiguous_fragments_in_shuffled_order() -> None:
    jpeg = _valid_jpeg()
    part_a = jpeg[:18]
    part_b = jpeg[18:50]
    part_c = jpeg[50:]

    engine = ReconstructionEngine("disk.img", "output", chunk_size=16, max_gap_size=128)
    fragments = [
        Fragment("FRAG-0003", 1200, len(part_c), part_c),
        Fragment("FRAG-0001", 1000, len(part_a), part_a),
        Fragment("FRAG-0002", 1100, len(part_b), part_b),
    ]

    result = engine.reconstruct(fragments, recovery_id="REC-0013")

    assert result.status == "RECONSTRUCTED"
    assert result.fragments_selected == ["FRAG-0001", "FRAG-0002", "FRAG-0003"]


def test_non_contiguous_missing_middle_fragment_partial() -> None:
    jpeg = _valid_jpeg()
    part_a = jpeg[:20]
    part_c = jpeg[40:]

    engine = ReconstructionEngine("disk.img", "output", chunk_size=16, max_gap_size=128)
    fragments = [
        Fragment("FRAG-0001", 1000, len(part_a), part_a),
        Fragment("FRAG-0003", 1300, len(part_c), part_c),
    ]

    result = engine.reconstruct(fragments, recovery_id="REC-0014")

    assert result.status in {"PARTIAL", "REJECTED"}
    assert result.fragments_used >= 1


def test_non_contiguous_unrelated_fragment_rejected() -> None:
    engine = ReconstructionEngine("disk.img", "output", chunk_size=16, max_gap_size=128)
    unrelated = b"\xff\xd8\xff\xe0fake-jpeg-data"
    fragments = [Fragment("FRAG-0001", 1000, len(unrelated), unrelated)]

    result = engine.reconstruct(fragments, recovery_id="REC-0015")

    assert result.status in {"PARTIAL", "REJECTED"}
    assert result.confidence < 1.0


def test_non_contiguous_corrupted_fragment_rejected() -> None:
    jpeg = _valid_jpeg()
    part_a = jpeg[:20]
    corrupted = b"\xff\xd8\xffbad\\x00data"
    part_c = jpeg[40:]

    engine = ReconstructionEngine("disk.img", "output", chunk_size=16, max_gap_size=128)
    fragments = [
        Fragment("FRAG-0001", 1000, len(part_a), part_a),
        Fragment("FRAG-0002", 1100, len(corrupted), corrupted),
        Fragment("FRAG-0003", 1300, len(part_c), part_c),
    ]

    result = engine.reconstruct(fragments, recovery_id="REC-0016")

    assert result.status in {"PARTIAL", "REJECTED"}


def test_non_contiguous_ambiguous_fragment_rejected() -> None:
    jpeg = _valid_jpeg()
    part_a = jpeg[:18]
    ambiguous = b"\xff\xd8\xff\xe0second-soi-data\xff\xd9"

    engine = ReconstructionEngine("disk.img", "output", chunk_size=16, max_gap_size=128)
    fragments = [
        Fragment("FRAG-0001", 1000, len(part_a), part_a),
        Fragment("FRAG-0002", 1200, len(ambiguous), ambiguous),
    ]

    result = engine.reconstruct(fragments, recovery_id="REC-0017")

    assert result.status == "REJECTED"
    assert any("ambiguous" in message.lower() for message in result.errors)
