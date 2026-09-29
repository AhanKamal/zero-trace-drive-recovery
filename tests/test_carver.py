from io import BytesIO
from pathlib import Path

from PIL import Image

from app.carver import JPEGCarver, PNGCarver, FormatCarver
from app.synthetic_image_generator import make_valid_bmp, make_valid_gif, make_valid_mp3, make_valid_mp4, make_valid_pdf, make_valid_tiff, make_valid_webp


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


def test_one_complete_png(tmp_path: Path) -> None:
    image_path = tmp_path / "single.img"
    png = _make_png_bytes()
    image_path.write_bytes(png)

    recovered = PNGCarver(image_path, tmp_path / "recovered", chunk_size=16).recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "PNG"
    assert recovered[0].status == "RECOVERED"
    assert Path(recovered[0].output_path).suffix == ".png"
    assert Path(recovered[0].output_path).read_bytes() == png


def test_truncated_png_is_partial(tmp_path: Path) -> None:
    image_path = tmp_path / "partial.img"
    png = _make_png_bytes()[:-12]
    image_path.write_bytes(png)

    recovered = PNGCarver(image_path, tmp_path / "recovered", chunk_size=8).recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "PNG"
    assert recovered[0].status == "PARTIAL"


def _make_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGBA", (32, 32), color=(10, 20, 30, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_one_complete_pdf(tmp_path: Path) -> None:
    image_path = tmp_path / "single.img"
    pdf = make_valid_pdf()
    image_path.write_bytes(b"prefix" + pdf + b"suffix")

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="PDF").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "PDF"
    assert recovered[0].status == "RECOVERED"
    assert Path(recovered[0].output_path).suffix == ".pdf"
    assert Path(recovered[0].output_path).read_bytes() == pdf


def test_truncated_pdf_is_partial(tmp_path: Path) -> None:
    image_path = tmp_path / "partial.img"
    pdf = make_valid_pdf().replace(b"%%EOF\n", b"")
    image_path.write_bytes(pdf)

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="PDF").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "PDF"
    assert recovered[0].status == "PARTIAL"


def test_one_complete_mp3(tmp_path: Path) -> None:
    image_path = tmp_path / "single-mp3.img"
    mp3 = make_valid_mp3()
    image_path.write_bytes(b"prefix" + mp3 + b"suffix")

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=32, file_type="MP3").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "MP3"
    assert recovered[0].status == "RECOVERED"
    assert Path(recovered[0].output_path).suffix == ".mp3"
    assert Path(recovered[0].output_path).read_bytes() == mp3


def test_truncated_mp3_is_partial(tmp_path: Path) -> None:
    image_path = tmp_path / "partial-mp3.img"
    image_path.write_bytes(make_valid_mp3()[:-100])

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=32, file_type="MP3").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "MP3"
    assert recovered[0].status == "PARTIAL"


def test_one_complete_mp4(tmp_path: Path) -> None:
    image_path = tmp_path / "single-mp4.img"
    mp4 = make_valid_mp4()
    image_path.write_bytes(b"prefix" + mp4 + b"suffix")

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="MP4").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "MP4"
    assert recovered[0].status == "RECOVERED"
    assert Path(recovered[0].output_path).suffix == ".mp4"
    assert Path(recovered[0].output_path).read_bytes() == mp4


def test_truncated_mp4_is_partial(tmp_path: Path) -> None:
    image_path = tmp_path / "partial-mp4.img"
    image_path.write_bytes(make_valid_mp4()[:-8])

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="MP4").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "MP4"
    assert recovered[0].status == "PARTIAL"


def test_one_complete_gif(tmp_path: Path) -> None:
    image_path = tmp_path / "single-gif.img"
    gif = make_valid_gif()
    image_path.write_bytes(b"prefix" + gif + b"suffix")

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="GIF").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "GIF"
    assert recovered[0].status == "RECOVERED"
    assert Path(recovered[0].output_path).suffix == ".gif"
    assert Path(recovered[0].output_path).read_bytes() == gif


def test_truncated_gif_is_partial(tmp_path: Path) -> None:
    image_path = tmp_path / "partial-gif.img"
    image_path.write_bytes(make_valid_gif()[:-1])

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="GIF").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "GIF"
    assert recovered[0].status == "PARTIAL"


def test_one_complete_bmp(tmp_path: Path) -> None:
    image_path = tmp_path / "single-bmp.img"
    bmp = make_valid_bmp()
    image_path.write_bytes(b"prefix" + bmp + b"suffix")

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="BMP").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "BMP"
    assert recovered[0].status == "RECOVERED"
    assert Path(recovered[0].output_path).suffix == ".bmp"
    assert Path(recovered[0].output_path).read_bytes() == bmp


def test_truncated_bmp_is_partial(tmp_path: Path) -> None:
    image_path = tmp_path / "partial-bmp.img"
    image_path.write_bytes(make_valid_bmp()[:-4])

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="BMP").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "BMP"
    assert recovered[0].status == "PARTIAL"


def test_one_complete_tiff(tmp_path: Path) -> None:
    image_path = tmp_path / "single-tiff.img"
    tiff = make_valid_tiff()
    image_path.write_bytes(b"prefix" + tiff + b"suffix")

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="TIFF").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "TIFF"
    assert recovered[0].status == "RECOVERED"
    assert Path(recovered[0].output_path).suffix == ".tif"
    assert Path(recovered[0].output_path).read_bytes() == tiff


def test_truncated_tiff_is_partial(tmp_path: Path) -> None:
    image_path = tmp_path / "partial-tiff.img"
    image_path.write_bytes(make_valid_tiff()[:-2])

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="TIFF").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "TIFF"
    assert recovered[0].status == "PARTIAL"


def test_one_complete_webp(tmp_path: Path) -> None:
    image_path = tmp_path / "single-webp.img"
    webp = make_valid_webp()
    image_path.write_bytes(b"prefix" + webp + b"suffix")

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="WEBP").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "WEBP"
    assert recovered[0].status == "RECOVERED"
    assert Path(recovered[0].output_path).suffix == ".webp"
    assert Path(recovered[0].output_path).read_bytes() == webp


def test_truncated_webp_is_partial(tmp_path: Path) -> None:
    image_path = tmp_path / "partial-webp.img"
    image_path.write_bytes(make_valid_webp()[:-4])

    recovered = FormatCarver(image_path, tmp_path / "recovered", chunk_size=16, file_type="WEBP").recover()

    assert len(recovered) == 1
    assert recovered[0].file_type == "WEBP"
    assert recovered[0].status == "PARTIAL"
