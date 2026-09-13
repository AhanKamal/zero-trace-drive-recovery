from pathlib import Path

import pytest

from app.scanner import SignatureScanner
from app.signatures import SignatureRegistry


@pytest.fixture
def registry() -> SignatureRegistry:
    return SignatureRegistry()


def test_jpeg_signature_detection(tmp_path: Path) -> None:
    image_path = tmp_path / "jpeg.img"
    jpeg = b"\xff\xd8\xff\xe0\x00\x10JFIF\xff\xd9"
    image_path.write_bytes(jpeg)

    scanner = SignatureScanner(str(image_path), chunk_size=8)
    candidates = scanner.scan()

    assert len(candidates) == 1
    assert candidates[0].file_type == "JPEG"
    assert candidates[0].offset == 0
    assert candidates[0].matched_signature == b"\xff\xd8\xff"


def test_png_signature_detection(tmp_path: Path) -> None:
    image_path = tmp_path / "png.img"
    png = b"\x89PNG\r\n\x1a\n" + b"data"
    image_path.write_bytes(png)

    scanner = SignatureScanner(str(image_path), chunk_size=16)
    candidates = scanner.scan()

    assert len(candidates) == 1
    assert candidates[0].file_type == "PNG"
    assert candidates[0].offset == 0
    assert candidates[0].matched_signature == b"\x89PNG\r\n\x1a\n"


def test_pdf_signature_detection(tmp_path: Path) -> None:
    image_path = tmp_path / "pdf.img"
    pdf = b"%PDF-1.7\n1 0 obj\n<<>>\nendobj"
    image_path.write_bytes(pdf)

    scanner = SignatureScanner(str(image_path), chunk_size=32)
    candidates = scanner.scan()

    assert len(candidates) == 1
    assert candidates[0].file_type == "PDF"
    assert candidates[0].offset == 0
    assert candidates[0].matched_signature == b"%PDF-"


def test_zip_signature_detection(tmp_path: Path) -> None:
    image_path = tmp_path / "zip.img"
    zip_data = b"PK\x03\x04" + b"zip-content"
    image_path.write_bytes(zip_data)

    scanner = SignatureScanner(str(image_path), chunk_size=16)
    candidates = scanner.scan()

    assert len(candidates) == 1
    assert candidates[0].file_type == "ZIP"
    assert candidates[0].offset == 0
    assert candidates[0].matched_signature == b"PK\x03\x04"


def test_multiple_signatures_and_offsets(tmp_path: Path) -> None:
    image_path = tmp_path / "mixed.img"
    data = b"\x00\x00" + b"%PDF-1.4" + b"\x00\x00" + b"PK\x03\x04" + b"\x00" + b"\x89PNG\r\n\x1a\n"
    image_path.write_bytes(data)

    scanner = SignatureScanner(str(image_path), chunk_size=6)
    candidates = scanner.scan()

    assert {candidate.file_type for candidate in candidates} == {"PDF", "ZIP", "PNG"}
    offsets = {candidate.file_type: candidate.offset for candidate in candidates}
    assert offsets["PDF"] == 2
    assert offsets["ZIP"] == 12
    assert offsets["PNG"] == 17


def test_no_false_detection_when_bytes_do_not_match(tmp_path: Path) -> None:
    image_path = tmp_path / "no_match.img"
    image_path.write_bytes(b"hello world\nnot a valid signature here")

    scanner = SignatureScanner(str(image_path), chunk_size=8)
    assert scanner.scan() == []


def test_signature_split_across_chunk_boundary(tmp_path: Path) -> None:
    image_path = tmp_path / "split.img"
    data = b"ABC\xff\xd8\xff" + b"XYZ"
    image_path.write_bytes(data)

    scanner = SignatureScanner(str(image_path), chunk_size=4)
    candidates = scanner.scan()

    assert len(candidates) == 1
    assert candidates[0].file_type == "JPEG"
    assert candidates[0].offset == 3
    assert candidates[0].matched_signature == b"\xff\xd8\xff"


def test_very_small_chunk_sizes(tmp_path: Path) -> None:
    image_path = tmp_path / "tiny_chunks.img"
    data = b"\x89PNG\r\n\x1a\n" + b"tail"
    image_path.write_bytes(data)

    scanner = SignatureScanner(str(image_path), chunk_size=1)
    candidates = scanner.scan()

    assert len(candidates) == 1
    assert candidates[0].offset == 0
    assert candidates[0].file_type == "PNG"


def test_empty_image(tmp_path: Path) -> None:
    image_path = tmp_path / "empty.img"
    image_path.write_bytes(b"")

    scanner = SignatureScanner(str(image_path), chunk_size=16)
    assert scanner.scan() == []


def test_image_smaller_than_chunk_size(tmp_path: Path) -> None:
    image_path = tmp_path / "small.img"
    data = b"PK\x03\x04data"
    image_path.write_bytes(data)

    scanner = SignatureScanner(str(image_path), chunk_size=4096)
    candidates = scanner.scan()

    assert len(candidates) == 1
    assert candidates[0].offset == 0
    assert candidates[0].file_type == "ZIP"


def test_registry_contains_expected_types(registry: SignatureRegistry) -> None:
    definitions = registry.definitions
    names = {entry.file_type for entry in definitions}

    assert names == {"JPEG", "PNG", "PDF", "ZIP"}
