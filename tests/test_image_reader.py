from pathlib import Path

import pytest

from app.image_reader import ImageReader


def test_open_image_and_size(tmp_path: Path) -> None:
    payload = b"\x00\x01\x02\x03\x04\x05\x06\x07" * 16
    image_path = tmp_path / "disk.img"
    image_path.write_bytes(payload)

    with ImageReader(image_path) as image:
        assert image.size == len(payload)
        assert image.closed is False


def test_read_from_offset(tmp_path: Path) -> None:
    payload = b"abcdefghijklmnopqrstuvwxyz"
    image_path = tmp_path / "disk.img"
    image_path.write_bytes(payload)

    with ImageReader(image_path) as image:
        assert image.read(5, 8) == b"fghijklm"
        assert image.read(0, 3) == b"abc"


def test_read_chunks(tmp_path: Path) -> None:
    payload = b"A" * 150
    image_path = tmp_path / "disk.img"
    image_path.write_bytes(payload)

    with ImageReader(image_path) as image:
        chunks = list(image.iter_chunks(64))

    assert chunks == [b"A" * 64, b"A" * 64, b"A" * 22]
    assert b"".join(chunks) == payload


def test_invalid_offsets_and_sizes(tmp_path: Path) -> None:
    payload = b"\x00\x01\x02\x03\x04"
    image_path = tmp_path / "disk.img"
    image_path.write_bytes(payload)

    with ImageReader(image_path) as image:
        with pytest.raises(ValueError):
            image.read(-1, 1)

        with pytest.raises(ValueError):
            image.read(len(payload), 1)

        with pytest.raises(ValueError):
            image.read(0, 0)

        with pytest.raises(ValueError):
            image.read(0, len(payload) + 1)

        with pytest.raises(ValueError):
            list(image.iter_chunks(0))


def test_missing_file() -> None:
    missing = Path("not_here.img")

    with pytest.raises(FileNotFoundError):
        ImageReader(missing)


def test_close_behavior(tmp_path: Path) -> None:
    image_path = tmp_path / "disk.dd"
    image_path.write_bytes(b"abcdef")

    image = ImageReader(image_path)
    assert image.closed is False
    image.close()
    assert image.closed is True

    with pytest.raises(ValueError):
        image.read(0, 1)
