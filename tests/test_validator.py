from io import BytesIO

from PIL import Image

from app.synthetic_image_generator import make_valid_bmp, make_valid_gif, make_valid_mp3, make_valid_mp4, make_valid_pdf, make_valid_tiff, make_valid_webp
from app.validator import BMPValidator, GIFValidator, JPEGValidator, MP3Validator, MP4Validator, PDFValidator, PNGValidator, TIFFValidator, WebPValidator, parse_bmp, parse_mp4_boxes, parse_gif, parse_tiff, parse_webp


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


def test_valid_png_is_decodable() -> None:
    buffer = BytesIO()
    Image.new("RGBA", (16, 16), color=(1, 2, 3, 255)).save(buffer, format="PNG")

    result = PNGValidator(buffer.getvalue()).validate()

    assert result.is_valid is True
    assert result.status == "VALID"
    assert result.file_type == "PNG"
    assert result.has_valid_header is True
    assert result.has_eoi_marker is True


def test_truncated_png_is_partial() -> None:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=(1, 2, 3)).save(buffer, format="PNG")

    result = PNGValidator(buffer.getvalue()[:-12]).validate()

    assert result.is_valid is False
    assert result.status == "PARTIAL"
    assert result.has_valid_header is True
    assert result.has_eoi_marker is False


def test_png_with_invalid_chunk_crc_is_rejected() -> None:
    payload = bytearray(b"\x89PNG\r\n\x1a\n")
    payload.extend((0).to_bytes(4, "big") + b"IEND" + b"\x00\x00\x00\x00")

    result = PNGValidator(bytes(payload)).validate()

    assert result.is_valid is False
    assert result.status == "INVALID"
    assert any("CRC" in error for error in result.errors)


def test_valid_pdf_is_structurally_usable() -> None:
    result = PDFValidator(make_valid_pdf()).validate()

    assert result.is_valid is True
    assert result.status == "VALID"
    assert result.file_type == "PDF"
    assert result.has_valid_header is True
    assert result.has_eoi_marker is True


def test_truncated_pdf_is_partial() -> None:
    result = PDFValidator(make_valid_pdf().replace(b"%%EOF\n", b"")).validate()

    assert result.is_valid is False
    assert result.status == "PARTIAL"
    assert result.has_valid_header is True
    assert result.has_eoi_marker is False


def test_structurally_invalid_pdf_is_rejected() -> None:
    result = PDFValidator(b"%PDF-1.7\n%%EOF\n").validate()

    assert result.is_valid is False
    assert result.status == "INVALID"
    assert result.errors


def test_valid_mp3_has_audio_frame_structure() -> None:
    result = MP3Validator(make_valid_mp3()).validate()

    assert result.is_valid is True
    assert result.status == "VALID"
    assert result.file_type == "MP3"
    assert result.has_valid_header is True
    assert result.has_eoi_marker is True


def test_truncated_mp3_is_partial() -> None:
    result = MP3Validator(make_valid_mp3()[:-100]).validate()

    assert result.is_valid is False
    assert result.status == "PARTIAL"
    assert result.has_valid_header is True


def test_id3_only_mp3_is_rejected() -> None:
    result = MP3Validator(b"ID3\x04\x00\x00\x00\x00\x00\x00").validate()

    assert result.is_valid is False
    assert result.status == "INVALID"
    assert any("audio frames" in error for error in result.errors)


def test_invalid_id3_size_is_rejected() -> None:
    result = MP3Validator(b"ID3\x04\x00\x00\x80\x00\x00\x00").validate()

    assert result.is_valid is False
    assert result.status == "INVALID"
    assert any("sync-safe" in error for error in result.errors)


def test_valid_mp4_boxes_are_parsed_and_validated() -> None:
    data = make_valid_mp4()
    parsed = parse_mp4_boxes(data)
    result = MP4Validator(data).validate()

    assert parsed.complete is True
    assert [box.box_type for box in parsed.boxes] == [b"ftyp", b"moov", b"mdat"]
    assert result.is_valid is True
    assert result.status == "VALID"
    assert result.file_type == "MP4"


def test_mp4_invalid_box_size_is_rejected() -> None:
    data = bytearray(make_valid_mp4())
    data[0:4] = (0xFFFFFFFF).to_bytes(4, "big")

    result = MP4Validator(bytes(data)).validate()

    assert result.is_valid is False
    assert result.status == "INVALID"
    assert result.errors


def test_mp4_truncated_box_is_partial() -> None:
    result = MP4Validator(make_valid_mp4()[:-8]).validate()

    assert result.is_valid is False
    assert result.status == "PARTIAL"


def test_false_ftyp_candidate_is_rejected() -> None:
    result = MP4Validator(b"\x00\x00\x00\x08ftyp").validate()

    assert result.is_valid is False
    assert result.status == "INVALID"


def test_valid_gif_is_structurally_usable() -> None:
    data = make_valid_gif()
    parsed = parse_gif(data)
    result = GIFValidator(data).validate()

    assert parsed.complete is True
    assert parsed.image_count == 1
    assert result.is_valid is True
    assert result.status == "VALID"
    assert result.file_type == "GIF"


def test_truncated_gif_is_partial() -> None:
    result = GIFValidator(make_valid_gif()[:-1]).validate()

    assert result.is_valid is False
    assert result.status == "PARTIAL"
    assert result.has_valid_header is True


def test_gif_with_header_but_no_image_is_rejected() -> None:
    data = b"GIF89a" + b"\x01\x00\x01\x00\x00\x00\x00" + b"\x3b"
    result = GIFValidator(data).validate()

    assert result.is_valid is False
    assert result.status == "INVALID"
    assert result.errors


def test_valid_bmp_header_and_pixels_are_structurally_usable() -> None:
    data = make_valid_bmp()
    parsed = parse_bmp(data)
    result = BMPValidator(data).validate()

    assert parsed.complete is True
    assert parsed.width == 2
    assert parsed.height == 2
    assert parsed.bits_per_pixel == 24
    assert result.is_valid is True
    assert result.status == "VALID"
    assert result.file_type == "BMP"


def test_bmp_invalid_dimensions_are_rejected() -> None:
    data = bytearray(make_valid_bmp())
    data[18:22] = (0).to_bytes(4, "little")

    result = BMPValidator(bytes(data)).validate()

    assert result.is_valid is False
    assert result.status == "INVALID"


def test_bmp_invalid_pixel_offset_is_rejected() -> None:
    data = bytearray(make_valid_bmp())
    data[10:14] = (10).to_bytes(4, "little")

    result = BMPValidator(bytes(data)).validate()

    assert result.is_valid is False
    assert result.status == "INVALID"


def test_bmp_false_signature_is_rejected() -> None:
    result = BMPValidator(b"noiseBMnot-a-bmp").validate()

    assert result.is_valid is False
    assert result.status == "INVALID"


def test_valid_little_and_big_endian_tiff() -> None:
    little = make_valid_tiff("<")
    big = make_valid_tiff(">")

    little_result = TIFFValidator(little).validate()
    big_result = TIFFValidator(big).validate()

    assert parse_tiff(little).complete is True
    assert parse_tiff(big).complete is True
    assert little_result.status == "VALID"
    assert big_result.status == "VALID"


def test_tiff_invalid_magic_is_rejected() -> None:
    data = bytearray(make_valid_tiff())
    data[2:4] = b"+\x00"

    result = TIFFValidator(bytes(data)).validate()

    assert result.status == "INVALID"


def test_tiff_invalid_ifd_offset_is_rejected() -> None:
    data = bytearray(make_valid_tiff())
    data[4:8] = (0xFFFFFF00).to_bytes(4, "little")

    result = TIFFValidator(bytes(data)).validate()

    assert result.status == "INVALID"


def test_tiff_invalid_entry_count_is_rejected() -> None:
    data = bytearray(make_valid_tiff())
    data[8:10] = (5000).to_bytes(2, "little")

    result = TIFFValidator(bytes(data)).validate()

    assert result.status == "INVALID"


def test_tiff_out_of_bounds_referenced_data_is_partial() -> None:
    data = bytearray(make_valid_tiff())
    data[114:118] = (0xFFFFFF00).to_bytes(4, "little")

    result = TIFFValidator(bytes(data)).validate()

    assert result.status == "PARTIAL"


def test_tiff_false_signature_is_rejected() -> None:
    result = TIFFValidator(b"noiseII*\x00not-a-tiff").validate()

    assert result.status == "INVALID"


def test_valid_webp_riff_chunks_are_usable() -> None:
    data = make_valid_webp()
    parsed = parse_webp(data)
    result = WebPValidator(data).validate()

    assert parsed.complete is True
    assert parsed.image_chunks
    assert result.is_valid is True
    assert result.status == "VALID"


def test_webp_invalid_riff_size_is_rejected() -> None:
    data = bytearray(make_valid_webp())
    data[4:8] = (0xFFFFFF00).to_bytes(4, "little")

    result = WebPValidator(bytes(data)).validate()

    assert result.status == "INVALID"


def test_webp_without_image_chunk_is_rejected() -> None:
    data = b"RIFF\x04\x00\x00\x00WEBP"

    result = WebPValidator(data).validate()

    assert result.status == "INVALID"
