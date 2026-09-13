import subprocess
import sys
from io import BytesIO
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]


def _valid_jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (24, 24), color=(12, 34, 56)).save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "app", *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
        check=False,
    )


def test_cli_recover_command_with_synthetic_img(tmp_path: Path) -> None:
    image_path = tmp_path / "sample.img"
    image_path.write_bytes(_valid_jpeg())
    output_dir = tmp_path / "output"

    result = run_cli("recover", str(image_path), "--output", str(output_dir))

    assert result.returncode == 0
    assert "Drive Recovery" in result.stdout
    assert "Source:" in result.stdout
    assert "Output:" in result.stdout
    assert "Scanning..." in result.stdout
    assert any(path.exists() for path in output_dir.iterdir())


def test_cli_recover_uses_custom_output_directory(tmp_path: Path) -> None:
    image_path = tmp_path / "custom.img"
    image_path.write_bytes(_valid_jpeg())
    output_dir = tmp_path / "custom-out"

    result = run_cli("recover", str(image_path), "--output", str(output_dir))

    assert result.returncode == 0
    assert str(output_dir) in result.stdout
    assert output_dir.exists()
    assert any(output_dir.iterdir())


def test_cli_recover_uses_default_output_directory(tmp_path: Path) -> None:
    image_path = tmp_path / "default.img"
    image_path.write_bytes(_valid_jpeg())

    result = run_cli("recover", str(image_path))

    assert result.returncode == 0
    assert "Output: recovered" in result.stdout
    assert (ROOT / "recovered").exists()


def test_cli_missing_source_image_returns_error(tmp_path: Path) -> None:
    missing = tmp_path / "missing.img"

    result = run_cli("recover", str(missing))

    assert result.returncode != 0
    assert "Error:" in result.stderr
    assert "Source image not found" in result.stderr


def test_cli_invalid_command_returns_error() -> None:
    result = run_cli("not-a-command")

    assert result.returncode != 0
    assert "invalid choice" in result.stderr.lower()


def test_cli_missing_command_returns_error() -> None:
    result = run_cli()

    assert result.returncode != 0
    assert "usage:" in result.stderr.lower()


def test_cli_exit_codes_are_non_zero_for_expected_errors(tmp_path: Path) -> None:
    invalid_output = tmp_path / "bad-out-file.txt"
    invalid_output.write_text("not a directory")
    image_path = tmp_path / "sample.img"
    image_path.write_bytes(_valid_jpeg())

    result = run_cli("recover", str(image_path), "--output", str(invalid_output))

    assert result.returncode != 0
    assert "Error:" in result.stderr


def test_cli_recovery_summary_is_displayed_after_success(tmp_path: Path) -> None:
    image_path = tmp_path / "summary.img"
    image_path.write_bytes(_valid_jpeg())
    output_dir = tmp_path / "summary-out"

    result = run_cli("recover", str(image_path), "--output", str(output_dir))

    assert result.returncode == 0
    assert "Files/candidates found:" in result.stdout
    assert "Successfully recovered:" in result.stdout
    assert "Partial recoveries:" in result.stdout
    assert "Rejected:" in result.stdout
    assert "Output directory:" in result.stdout
