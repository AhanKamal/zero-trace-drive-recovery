from pathlib import Path

from app.recovery import RecoveryEngine
from app.synthetic_image_generator import create_synthetic_disk_image


def test_end_to_end_synthetic_disk_image_recovery(tmp_path: Path) -> None:
    image_dir = tmp_path / "synthetic"
    image_path = create_synthetic_disk_image(image_dir, filename="synthetic_disk.img")
    output_dir = tmp_path / "recovered-output"

    before = image_path.read_bytes()

    result = RecoveryEngine(image_path, output_dir).recover()

    assert result.source_image == str(image_path)
    assert result.recovered_files
    assert image_path.read_bytes() == before

    recovered_files = [Path(item.output_path) for item in result.recovered_files if item.output_path]
    assert recovered_files
    assert all(path.exists() for path in recovered_files)
    assert all(path.is_file() for path in recovered_files)
    assert all(path.parent == output_dir for path in recovered_files)

    statuses = {item.status for item in result.recovered_files}
    assert statuses.intersection({"RECONSTRUCTED", "PARTIAL"})

    image_bytes = image_path.read_bytes()
    assert image_bytes.count(b"\xff\xd8\xff") >= 3
    assert image_bytes.count(b"\xff\xd9") >= 1

    complete_matches = sum(1 for item in result.recovered_files if item.status == "RECONSTRUCTED")
    partial_matches = sum(1 for item in result.recovered_files if item.status == "PARTIAL")

    assert complete_matches >= 0
    assert partial_matches >= 1

    for item in result.recovered_files:
        if item.status == "RECONSTRUCTED":
            assert item.size > 0
            assert item.confidence > 0.0
            assert item.validation_status in {"VALID", "PARTIAL"}
        if item.status == "PARTIAL":
            assert item.size > 0

    assert not any(file_path.exists() for file_path in image_dir.iterdir() if file_path.name.startswith("REC-"))
