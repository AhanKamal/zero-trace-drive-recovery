from io import BytesIO
from pathlib import Path

from PIL import Image

from app.carver import JPEGCarver


def _make_jpeg_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (48, 48), color=(10, 20, 30)).save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def test_one_complete_jpeg(tmp_path: Path) -> None:
    image_path = tmp_path / "single.img"
    jpeg = _make_jpeg_bytes()
    image_path.write_bytes(jpeg)

    recovered_dir = tmp_path / "recovered"
    carver = JPEGCarver(image_path, recovered_dir, chunk_size=16)
    recovered = carver.recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "JPEG"
    assert recovered[0].source_offset == 0
    assert recovered[0].status == "RECOVERED"
    assert recovered[0].recovered_size == len(jpeg)
    assert Path(recovered[0].output_path).read_bytes() == jpeg


def test_multiple_jpegs(tmp_path: Path) -> None:
    image_path = tmp_path / "many.img"
    jpeg_one = _make_jpeg_bytes()
    jpeg_two = b"\xff\xd8\xff\xe1\x00\x16Exif\x00\x00\xff\xd9"
    image_path.write_bytes(jpeg_one + b"noise" + jpeg_two)

    recovered_dir = tmp_path / "recovered"
    carver = JPEGCarver(image_path, recovered_dir, chunk_size=16)
    recovered = carver.recover()

    assert len(recovered) == 2
    assert [item.source_offset for item in recovered] == [0, len(jpeg_one) + len(b"noise")]
    assert all(item.status == "RECOVERED" for item in recovered)


def test_jpeg_at_non_zero_offset(tmp_path: Path) -> None:
    image_path = tmp_path / "offset.img"
    prefix = b"abcde"
    jpeg = _make_jpeg_bytes()
    image_path.write_bytes(prefix + jpeg)

    carver = JPEGCarver(image_path, tmp_path / "recovered", chunk_size=8)
    recovered = carver.recover()

    assert len(recovered) == 1
    assert recovered[0].source_offset == len(prefix)


def test_jpeg_split_across_scanner_chunks(tmp_path: Path) -> None:
    image_path = tmp_path / "split.img"
    jpeg = _make_jpeg_bytes()
    image_path.write_bytes(b"abc" + jpeg[:-2] + b"\xff\xd9")

    carver = JPEGCarver(image_path, tmp_path / "recovered", chunk_size=4)
    recovered = carver.recover()

    assert len(recovered) == 1
    assert recovered[0].source_offset == 3
    assert recovered[0].status == "RECOVERED"


def test_truncated_jpeg_without_end_marker(tmp_path: Path) -> None:
    image_path = tmp_path / "partial.img"
    partial = _make_jpeg_bytes()[:-20]
    image_path.write_bytes(partial)

    carver = JPEGCarver(image_path, tmp_path / "recovered", chunk_size=8)
    recovered = carver.recover()

    assert len(recovered) == 1
    assert recovered[0].status == "PARTIAL"
    assert recovered[0].source_offset == 0
    assert recovered[0].recovered_size == len(partial)


def test_random_bytes_with_no_jpeg(tmp_path: Path) -> None:
    image_path = tmp_path / "random.img"
    image_path.write_bytes(b"hello world\nthis is not a jpeg")

    recovered_dir = tmp_path / "recovered"
    carver = JPEGCarver(image_path, recovered_dir, chunk_size=16)
    recovered = carver.recover()

    assert recovered == []


def test_two_jpeg_candidates(tmp_path: Path) -> None:
    image_path = tmp_path / "two.img"
    jpeg_a = b"\xff\xd8\xff\xe0\x00\x10JFIF\xff\xd9"
    jpeg_b = b"\xff\xd8\xff\xe0\x00\x10JFIF\xff\xd9"
    image_path.write_bytes(jpeg_a + b"X" + jpeg_b)

    recovered = JPEGCarver(image_path, tmp_path / "recovered", chunk_size=8).recover()

    assert len(recovered) == 2
    assert [item.source_offset for item in recovered] == [0, len(jpeg_a) + 1]


def test_duplicate_overlapping_candidates_are_skipped(tmp_path: Path) -> None:
    image_path = tmp_path / "duplicate.img"
    jpeg = _make_jpeg_bytes()
    image_path.write_bytes(b"A" + jpeg)

    carver = JPEGCarver(image_path, tmp_path / "recovered", chunk_size=8)
    recovered = carver.recover()

    assert len(recovered) == 1
    assert recovered[0].source_offset == 1
