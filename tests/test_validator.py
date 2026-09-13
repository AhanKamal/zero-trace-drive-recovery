from io import BytesIO

from PIL import Image

from app.validator import JPEGValidator


def _valid_jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color=(12, 34, 56)).save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def test_valid_jpeg_header_and_eoi() -> None:
    result = JPEGValidator(_valid_jpeg()).validate()

    assert result.is_valid is True
    assert result.status == "VALID"
    assert result.has_valid_header is True
    assert result.has_eoi_marker is True
    assert result.file_type == "JPEG"


def test_missing_header() -> None:
    result = JPEGValidator(b"hello world").validate()

    assert result.is_valid is False
    assert result.status == "INVALID"
    assert result.has_valid_header is False
    assert "Missing JPEG SOI marker" in result.errors[0]


def test_missing_eoi() -> None:
    partial = _valid_jpeg()[:-20]
    result = JPEGValidator(partial).validate()

    assert result.is_valid is False
    assert result.status == "PARTIAL"
    assert result.has_valid_header is True
    assert result.has_eoi_marker is False


def test_empty_file() -> None:
    result = JPEGValidator(b"").validate()

    assert result.is_valid is False
    assert result.status == "INVALID"
    assert result.size == 0
    assert result.has_valid_header is False
    assert result.has_eoi_marker is False


def test_very_small_file() -> None:
    result = JPEGValidator(b"\xff\xd8\xff").validate()

    assert result.is_valid is False
    assert result.status == "PARTIAL"
    assert result.has_valid_header is True


def test_corrupted_invalid_data() -> None:
    result = JPEGValidator(b"\x00\x01\x02\x03\x04").validate()

    assert result.is_valid is False
    assert result.status == "INVALID"
    assert result.has_valid_header is False
    assert result.has_eoi_marker is False


def test_partial_jpeg() -> None:
    partial = _valid_jpeg()[:-10]
    result = JPEGValidator(partial).validate()

    assert result.is_valid is False
    assert result.status == "PARTIAL"
    assert result.has_valid_header is True
    assert result.has_eoi_marker is False


def test_valid_jpeg_with_arbitrary_payload_bytes() -> None:
    payload = _valid_jpeg() + b"\x00\x00junk-trailing-data"
    result = JPEGValidator(payload).validate()

    assert result.is_valid is True
    assert result.status == "VALID"
    assert result.has_valid_header is True
    assert result.has_eoi_marker is True


def test_marker_only_payload_is_not_valid() -> None:
    payload = b"\xff\xd8\xff\xe0\x00\x10JFIF\xff\xd9"
    result = JPEGValidator(payload).validate()

    assert result.is_valid is False
    assert result.status == "INVALID"
    assert result.has_valid_header is True
    assert result.has_eoi_marker is True
    assert any("not a decodable image" in error.lower() for error in result.errors)
