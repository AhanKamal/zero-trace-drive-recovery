from io import BytesIO
from pathlib import Path

from PIL import Image

from app.recovery import RecoveryEngine


def _valid_jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color=(7, 11, 19)).save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def test_recovery_pipeline_recovers_single_jpeg(tmp_path: Path) -> None:
    image_path = tmp_path / "single.img"
    jpeg = _valid_jpeg()
    image_path.write_bytes(jpeg)
    output_dir = tmp_path / "recovered"

    before = image_path.read_bytes()
    result = RecoveryEngine(image_path, output_dir).recover()

    assert result.recovered_files
    assert result.recovered_files[0].status == "RECONSTRUCTED"
    assert result.recovered_files[0].file_type == "JPEG"
    assert image_path.read_bytes() == before
    assert output_dir.exists()
    assert any(output_dir.iterdir())


def test_recovery_pipeline_recovers_multiple_jpegs(tmp_path: Path) -> None:
    image_path = tmp_path / "multiple.img"
    jpeg_a = _valid_jpeg()
    jpeg_b = _valid_jpeg()
    image_bytes = jpeg_a + b"\x00\x00" + jpeg_b
    image_path.write_bytes(image_bytes)
    output_dir = tmp_path / "multi-out"

    result = RecoveryEngine(image_path, output_dir).recover()

    assert len(result.recovered_files) >= 1
    assert all(item.status in {"RECONSTRUCTED", "PARTIAL", "REJECTED"} for item in result.recovered_files)
    assert all(Path(item.output_path).exists() for item in result.recovered_files)


def test_recovery_pipeline_handles_no_recoverable_jpeg(tmp_path: Path) -> None:
    image_path = tmp_path / "not-jpeg.img"
    image_path.write_bytes(b"hello world\nnot a valid image\n")
    output_dir = tmp_path / "empty-out"

    result = RecoveryEngine(image_path, output_dir).recover()

    assert result.recovered_files == []
    assert result.candidates_found == 0
    assert any("No recoverable JPEG signatures" in warning for warning in result.warnings)


def test_recovery_pipeline_handles_partial_jpeg(tmp_path: Path) -> None:
    image_path = tmp_path / "partial.img"
    partial = b"\xff\xd8\xff\xe0\x00\x10JFIF"
    image_path.write_bytes(partial)
    output_dir = tmp_path / "partial-out"

    result = RecoveryEngine(image_path, output_dir).recover()

    assert result.recovered_files
    assert result.recovered_files[0].status in {"PARTIAL", "REJECTED"}
    assert Path(result.recovered_files[0].output_path).exists()


def test_recovery_pipeline_recovers_jpeg_at_non_zero_offset(tmp_path: Path) -> None:
    image_path = tmp_path / "offset.img"
    prefix = b"\x00\x01\x02\x03\x04"
    jpeg = _valid_jpeg()
    image_bytes = prefix + jpeg + b"\x99\x88"
    image_path.write_bytes(image_bytes)
    output_dir = tmp_path / "offset-out"

    result = RecoveryEngine(image_path, output_dir).recover()

    assert result.recovered_files
    assert result.recovered_files[0].source_offset == len(prefix)
    assert result.recovered_files[0].status in {"RECONSTRUCTED", "PARTIAL"}


def test_recovery_pipeline_keeps_evidence_file_unchanged(tmp_path: Path) -> None:
    image_path = tmp_path / "evidence.img"
    jpeg = _valid_jpeg()
    image_path.write_bytes(jpeg)
    before = image_path.read_bytes()
    output_dir = tmp_path / "evidence-out"

    RecoveryEngine(image_path, output_dir).recover()

    assert image_path.read_bytes() == before
    assert output_dir.exists()
    assert any(Path(item.output_path).exists() for item in RecoveryEngine(image_path, output_dir).recover().recovered_files)
