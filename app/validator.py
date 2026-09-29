from __future__ import annotations

from dataclasses import dataclass, field

try:
    from PIL import Image
    from PIL import UnidentifiedImageError
except ImportError:  # pragma: no cover - Pillow is a dependency for production JPEG validation
    Image = None
    UnidentifiedImageError = Exception


@dataclass
class ValidationResult:
    is_valid: bool
    status: str
    file_type: str
    size: int
    has_valid_header: bool
    has_eoi_marker: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MP3Frame:
    offset: int
    length: int


@dataclass(frozen=True)
class MP4Box:
    offset: int
    size: int
    box_type: bytes
    header_size: int


@dataclass(frozen=True)
class MP4ParseResult:
    boxes: list[MP4Box]
    complete: bool
    end_offset: int
    error: str | None = None


@dataclass(frozen=True)
class GIFParseResult:
    complete: bool
    end_offset: int
    image_count: int
    error: str | None = None
    truncated: bool = False


@dataclass(frozen=True)
class BMPParseResult:
    complete: bool
    end_offset: int
    file_size: int
    pixel_offset: int
    width: int
    height: int
    bits_per_pixel: int
    compression: int
    error: str | None = None
    truncated: bool = False


@dataclass(frozen=True)
class TIFFParseResult:
    complete: bool
    end_offset: int
    byte_order: str
    first_ifd_offset: int
    image_tags: frozenset[int]
    width: int | None
    height: int | None
    bits_per_sample: tuple[int, ...]
    compression: int | None
    error: str | None = None
    truncated: bool = False


@dataclass(frozen=True)
class WebPParseResult:
    complete: bool
    end_offset: int
    image_chunks: tuple[bytes, ...]
    error: str | None = None
    truncated: bool = False


def parse_webp(data: bytes) -> WebPParseResult:
    if len(data) < 12:
        return WebPParseResult(False, len(data), (), "RIFF/WEBP header is truncated.", True)
    if data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return WebPParseResult(False, 0, (), "WebP RIFF signature is invalid.")

    riff_size = int.from_bytes(data[4:8], "little")
    if riff_size < 4 or riff_size > 0x7FFFFFFF:
        return WebPParseResult(False, 12, (), "WebP RIFF size is invalid.")
    declared_end = 8 + riff_size
    limit = min(declared_end, len(data))
    position = 12
    image_chunks: list[bytes] = []

    while position < limit:
        if position + 8 > limit:
            return WebPParseResult(False, position, tuple(image_chunks), "WebP chunk header is truncated.", True)
        chunk_type = data[position:position + 4]
        if not all(32 <= value < 127 for value in chunk_type):
            return WebPParseResult(False, position, tuple(image_chunks), "WebP chunk type is invalid.")
        chunk_size = int.from_bytes(data[position + 4:position + 8], "little")
        padded_size = chunk_size + (chunk_size & 1)
        chunk_end = position + 8 + padded_size
        if chunk_end < position or chunk_end > limit:
            return WebPParseResult(False, position, tuple(image_chunks), "WebP chunk extends beyond the declared RIFF size.", True)
        if chunk_type in (b"VP8 ", b"VP8L", b"VP8X"):
            if chunk_size == 0:
                return WebPParseResult(False, position, tuple(image_chunks), "WebP image chunk is empty.")
            image_chunks.append(chunk_type)
        position = chunk_end

    if declared_end > len(data):
        return WebPParseResult(False, position, tuple(image_chunks), "WebP RIFF data is truncated.", True)
    if position != declared_end:
        return WebPParseResult(False, position, tuple(image_chunks), "WebP chunks do not reach the declared RIFF boundary.")
    if not image_chunks:
        return WebPParseResult(False, position, (), "WebP contains no image payload chunk.")
    return WebPParseResult(True, declared_end, tuple(image_chunks))


_TIFF_TYPE_SIZES = {1: 1, 2: 1, 3: 2, 4: 4, 5: 8, 6: 1, 7: 1, 8: 2, 9: 4, 10: 8, 11: 4, 12: 8}
_TIFF_MAX_IFDS = 32
_TIFF_MAX_ENTRIES = 4096
_TIFF_MAX_VALUE_BYTES = 64 * 1024 * 1024


def parse_tiff(data: bytes) -> TIFFParseResult:
    if len(data) < 8:
        return TIFFParseResult(False, len(data), "", 0, frozenset(), None, None, (), None, "TIFF header is truncated.", True)
    if data[:2] == b"II":
        byte_order = "little"
        magic = int.from_bytes(data[2:4], "little")
        read_u16 = lambda value: int.from_bytes(value, "little")
        read_u32 = lambda value: int.from_bytes(value, "little")
    elif data[:2] == b"MM":
        byte_order = "big"
        magic = int.from_bytes(data[2:4], "big")
        read_u16 = lambda value: int.from_bytes(value, "big")
        read_u32 = lambda value: int.from_bytes(value, "big")
    else:
        return TIFFParseResult(False, 0, "", 0, frozenset(), None, None, (), None, "TIFF byte-order marker is invalid.")

    if magic == 43:
        return TIFFParseResult(False, 4, byte_order, 0, frozenset(), None, None, (), None, "BigTIFF is not supported.")
    if magic != 42:
        return TIFFParseResult(False, 4, byte_order, 0, frozenset(), None, None, (), None, "TIFF magic number is invalid.")

    first_ifd_offset = read_u32(data[4:8])
    if first_ifd_offset < 8 or first_ifd_offset >= len(data):
        return TIFFParseResult(False, 8, byte_order, first_ifd_offset, frozenset(), None, None, (), None, "TIFF first IFD offset is outside the candidate.")

    visited: set[int] = set()
    ifd_offset = first_ifd_offset
    max_end = 8
    image_tags: set[int] = set()
    width: int | None = None
    height: int | None = None
    bits_per_sample: tuple[int, ...] = ()
    compression: int | None = None
    strip_offsets: list[int] = []
    strip_byte_counts: list[int] = []

    for _ in range(_TIFF_MAX_IFDS):
        if ifd_offset in visited:
            return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF IFD chain contains a cycle.")
        visited.add(ifd_offset)
        if ifd_offset + 2 > len(data):
            return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF IFD entry count is truncated.", True)

        entry_count = read_u16(data[ifd_offset:ifd_offset + 2])
        if entry_count > _TIFF_MAX_ENTRIES:
            return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF IFD entry count is unreasonable.")
        entries_start = ifd_offset + 2
        entries_end = entries_start + entry_count * 12
        next_offset_position = entries_end
        if entries_end + 4 > len(data):
            return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF IFD entries are truncated.", True)
        max_end = max(max_end, entries_end + 4)

        for index in range(entry_count):
            entry_start = entries_start + index * 12
            tag = read_u16(data[entry_start:entry_start + 2])
            field_type = read_u16(data[entry_start + 2:entry_start + 4])
            count = read_u32(data[entry_start + 4:entry_start + 8])
            if field_type not in _TIFF_TYPE_SIZES or count == 0:
                return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF entry type or count is invalid.")
            value_bytes = _TIFF_TYPE_SIZES[field_type] * count
            if value_bytes > _TIFF_MAX_VALUE_BYTES:
                return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF entry value is too large.")

            raw_value = data[entry_start + 8:entry_start + 12]
            if value_bytes <= 4:
                value_data = raw_value[:value_bytes]
            else:
                value_offset = read_u32(raw_value)
                value_end = value_offset + value_bytes
                if value_offset < 8 or value_end < value_offset:
                    return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF entry offset calculation is invalid.")
                if value_end > len(data):
                    return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF referenced data is truncated.", True)
                max_end = max(max_end, value_end)
                value_data = data[value_offset:value_end]

            values = _read_tiff_values(value_data, field_type, count, read_u16, read_u32)
            if values is None:
                return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF entry value cannot be decoded.")
            if tag in {256, 257, 258, 259, 273, 277, 278, 279}:
                image_tags.add(tag)
            if tag == 256 and values:
                width = values[0]
            elif tag == 257 and values:
                height = values[0]
            elif tag == 258:
                bits_per_sample = tuple(values)
            elif tag == 259 and values:
                compression = values[0]
            elif tag == 273:
                strip_offsets = values
            elif tag == 279:
                strip_byte_counts = values

        next_ifd_offset = read_u32(data[next_offset_position:next_offset_position + 4])
        if next_ifd_offset == 0:
            if len(strip_offsets) != len(strip_byte_counts) or not strip_offsets:
                return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF strip offset and byte-count entries are invalid.")
            for strip_offset, strip_byte_count in zip(strip_offsets, strip_byte_counts):
                strip_end = strip_offset + strip_byte_count
                if strip_offset < 8 or strip_end < strip_offset:
                    return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF strip range calculation is invalid.")
                if strip_end > len(data):
                    return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF strip data is truncated.", True)
                max_end = max(max_end, strip_end)
            return TIFFParseResult(True, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression)
        if next_ifd_offset < 8 or next_ifd_offset >= len(data):
            return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF next IFD offset is outside the candidate.")
        ifd_offset = next_ifd_offset

    return TIFFParseResult(False, max_end, byte_order, first_ifd_offset, frozenset(image_tags), width, height, bits_per_sample, compression, "TIFF IFD chain exceeds the safe traversal limit.")


def _read_tiff_values(data: bytes, field_type: int, count: int, read_u16, read_u32) -> list[int] | None:
    if field_type in (1, 2, 6, 7):
        return list(data[:count])
    if field_type in (3, 8):
        width = 2
        return [read_u16(data[index:index + width]) for index in range(0, count * width, width)]
    if field_type in (4, 9, 11):
        width = 4
        return [read_u32(data[index:index + width]) for index in range(0, count * width, width)]
    if field_type in (5, 10):
        width = 8
        return [read_u32(data[index:index + 4]) for index in range(0, count * width, width)]
    if field_type == 12:
        return [0] * count
    return None


def parse_bmp(data: bytes) -> BMPParseResult:
    if len(data) < 14:
        return BMPParseResult(False, len(data), 0, 0, 0, 0, 0, 0, "BMP file header is truncated.", True)
    if data[:2] != b"BM":
        return BMPParseResult(False, 0, 0, 0, 0, 0, 0, 0, "BMP signature is invalid.")

    file_size = int.from_bytes(data[2:6], "little")
    pixel_offset = int.from_bytes(data[10:14], "little")
    if file_size < 14 or file_size > 0x7FFFFFFF:
        return BMPParseResult(False, 14, file_size, pixel_offset, 0, 0, 0, 0, "BMP file size is invalid.")
    if len(data) < 18:
        return BMPParseResult(False, len(data), file_size, pixel_offset, 0, 0, 0, 0, "BMP DIB header size is truncated.", True)

    dib_size = int.from_bytes(data[14:18], "little")
    if dib_size == 12:
        if len(data) < 26:
            return BMPParseResult(False, len(data), file_size, pixel_offset, 0, 0, 0, 0, "BMP core header is truncated.", True)
        width = int.from_bytes(data[18:20], "little")
        height = int.from_bytes(data[20:22], "little")
        planes = int.from_bytes(data[22:24], "little")
        bits_per_pixel = int.from_bytes(data[24:26], "little")
        compression = 0
        header_end = 26
        palette_entry_size = 3
    elif dib_size in (40, 52, 56, 108, 124):
        if len(data) < 14 + dib_size:
            return BMPParseResult(False, len(data), file_size, pixel_offset, 0, 0, 0, 0, "BMP DIB header is truncated.", True)
        width = int.from_bytes(data[18:22], "little", signed=True)
        height = int.from_bytes(data[22:26], "little", signed=True)
        planes = int.from_bytes(data[26:28], "little")
        bits_per_pixel = int.from_bytes(data[28:30], "little")
        compression = int.from_bytes(data[30:34], "little")
        header_end = 14 + dib_size
        palette_entry_size = 4
    else:
        return BMPParseResult(False, 18, file_size, pixel_offset, 0, 0, 0, 0, "BMP DIB header size is unsupported.")

    if width <= 0 or height == 0:
        return BMPParseResult(False, header_end, file_size, pixel_offset, width, height, bits_per_pixel, compression, "BMP dimensions are invalid.")
    if planes != 1:
        return BMPParseResult(False, header_end, file_size, pixel_offset, width, height, bits_per_pixel, compression, "BMP planes must equal 1.")
    if bits_per_pixel not in {1, 4, 8, 16, 24, 32}:
        return BMPParseResult(False, header_end, file_size, pixel_offset, width, height, bits_per_pixel, compression, "BMP bits per pixel is unsupported.")
    if compression != 0:
        return BMPParseResult(False, header_end, file_size, pixel_offset, width, height, bits_per_pixel, compression, "BMP compression format is unsupported.")

    colors_used = 0
    if dib_size >= 40:
        colors_used = int.from_bytes(data[46:50], "little")
    palette_entries = colors_used or (2 ** bits_per_pixel if bits_per_pixel <= 8 else 0)
    minimum_pixel_offset = header_end + palette_entries * palette_entry_size
    if pixel_offset < minimum_pixel_offset or pixel_offset >= file_size:
        return BMPParseResult(False, header_end, file_size, pixel_offset, width, height, bits_per_pixel, compression, "BMP pixel-data offset is invalid.")

    row_stride = ((width * bits_per_pixel + 31) // 32) * 4
    required_pixel_bytes = row_stride * abs(height)
    required_file_size = pixel_offset + required_pixel_bytes
    if required_file_size > file_size:
        return BMPParseResult(False, header_end, file_size, pixel_offset, width, height, bits_per_pixel, compression, "BMP file size is smaller than its declared pixel data.")
    if file_size > len(data):
        return BMPParseResult(False, len(data), file_size, pixel_offset, width, height, bits_per_pixel, compression, "BMP file is truncated before its declared file size.", True)

    return BMPParseResult(True, file_size, file_size, pixel_offset, width, height, bits_per_pixel, compression)


def parse_gif(data: bytes) -> GIFParseResult:
    if len(data) < 13:
        return GIFParseResult(False, len(data), 0, "GIF header or logical screen descriptor is truncated.", True)
    if data[:6] not in (b"GIF87a", b"GIF89a"):
        return GIFParseResult(False, 0, 0, "GIF header is invalid.")

    width = int.from_bytes(data[6:8], "little")
    height = int.from_bytes(data[8:10], "little")
    packed = data[10]
    if width == 0 or height == 0:
        return GIFParseResult(False, 13, 0, "GIF logical screen dimensions are zero.")

    position = 13
    if packed & 0x80:
        color_table_size = 3 * (2 ** ((packed & 0x07) + 1))
        if position + color_table_size > len(data):
            return GIFParseResult(False, position, 0, "GIF global color table is truncated.", True)
        position += color_table_size

    image_count = 0
    while position < len(data):
        introducer = data[position]
        position += 1

        if introducer == 0x3B:
            if image_count == 0:
                return GIFParseResult(False, position, 0, "GIF contains no image descriptor.")
            return GIFParseResult(True, position, image_count)

        if introducer == 0x2C:
            if position + 9 > len(data):
                return GIFParseResult(False, position, image_count, "GIF image descriptor is truncated.", True)
            image_packed = data[position + 8]
            position += 9
            if image_packed & 0x80:
                local_table_size = 3 * (2 ** ((image_packed & 0x07) + 1))
                if position + local_table_size > len(data):
                    return GIFParseResult(False, position, image_count, "GIF local color table is truncated.", True)
                position += local_table_size
            if position >= len(data):
                return GIFParseResult(False, position, image_count, "GIF image data is truncated.", True)
            position += 1
            position, error, truncated = _skip_gif_sub_blocks(data, position)
            if error:
                return GIFParseResult(False, position, image_count, error, truncated)
            image_count += 1
            continue

        if introducer == 0x21:
            if position >= len(data):
                return GIFParseResult(False, position, image_count, "GIF extension is truncated.", True)
            position += 1
            position, error, truncated = _skip_gif_sub_blocks(data, position)
            if error:
                return GIFParseResult(False, position, image_count, error, truncated)
            continue

        return GIFParseResult(False, position, image_count, f"Unknown GIF block introducer 0x{introducer:02x}.")

    return GIFParseResult(False, position, image_count, "GIF trailer is missing.", True)


def _skip_gif_sub_blocks(data: bytes, position: int) -> tuple[int, str | None, bool]:
    while True:
        if position >= len(data):
            return position, "GIF data sub-block terminator is missing.", True
        block_size = data[position]
        position += 1
        if block_size == 0:
            return position, None, False
        if position + block_size > len(data):
            return len(data), "GIF data sub-block is truncated.", True
        position += block_size


def parse_mp4_boxes(data: bytes) -> MP4ParseResult:
    boxes: list[MP4Box] = []
    position = 0

    while position < len(data):
        remaining = len(data) - position
        if remaining < 8:
            return MP4ParseResult(boxes, False, position, "Trailing bytes are shorter than an MP4 box header.")

        size = int.from_bytes(data[position:position + 4], "big")
        box_type = data[position + 4:position + 8]
        if not all(32 <= value < 127 for value in box_type):
            return MP4ParseResult(boxes, False, position, "MP4 box type is not printable ASCII.")

        header_size = 8
        if size == 1:
            if remaining < 16:
                return MP4ParseResult(boxes, False, position, "MP4 extended box size is truncated.")
            size = int.from_bytes(data[position + 8:position + 16], "big")
            header_size = 16
        elif size == 0:
            size = remaining

        if size < header_size:
            return MP4ParseResult(boxes, False, position, "MP4 box size is smaller than its header.")
        if size > remaining:
            return MP4ParseResult(boxes, False, position, "MP4 box extends beyond the available data.")

        boxes.append(MP4Box(position, size, box_type, header_size))
        position += size

    return MP4ParseResult(boxes, True, position)


def parse_mp3_frames(data: bytes) -> tuple[list[MP3Frame], bool, int]:
    position = 0
    if data.startswith(b"ID3"):
        if len(data) < 10:
            return [], True, len(data)
        tag_size_bytes = data[6:10]
        if any(value & 0x80 for value in tag_size_bytes):
            return [], False, 0
        tag_size = (
            (tag_size_bytes[0] << 21)
            | (tag_size_bytes[1] << 14)
            | (tag_size_bytes[2] << 7)
            | tag_size_bytes[3]
        )
        position = 10 + tag_size
        if position > len(data):
            return [], True, position

    frames: list[MP3Frame] = []
    incomplete = False
    while position + 4 <= len(data):
        frame_length = _mp3_frame_length(data[position:position + 4])
        if frame_length is None:
            break
        if position + frame_length > len(data):
            incomplete = True
            break
        frames.append(MP3Frame(position, frame_length))
        position += frame_length

    if position < len(data) and len(data) - position < 4:
        incomplete = bool(frames)

    return frames, incomplete, position


def _mp3_frame_length(header: bytes) -> int | None:
    if len(header) < 4 or header[0] != 0xFF or header[1] & 0xE0 != 0xE0:
        return None

    version_id = (header[1] >> 3) & 0x03
    layer = (header[1] >> 1) & 0x03
    bitrate_index = (header[2] >> 4) & 0x0F
    sample_rate_index = (header[2] >> 2) & 0x03
    padding = (header[2] >> 1) & 0x01

    if version_id == 1 or layer != 1 or bitrate_index in (0, 15) or sample_rate_index == 3:
        return None

    if version_id == 3:
        bitrates = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)
        sample_rates = (44100, 48000, 32000)
        multiplier = 144
    else:
        bitrates = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)
        sample_rates = (22050, 24000, 16000) if version_id == 2 else (11025, 12000, 8000)
        multiplier = 72

    return (multiplier * bitrates[bitrate_index] * 1000 // sample_rates[sample_rate_index]) + padding


class JPEGValidator:
    def __init__(self, file_bytes: bytes) -> None:
        self.file_bytes = file_bytes

    def validate(self) -> ValidationResult:
        data = self.file_bytes
        errors: list[str] = []
        warnings: list[str] = []

        if not data:
            return ValidationResult(
                is_valid=False,
                status="INVALID",
                file_type="JPEG",
                size=0,
                has_valid_header=False,
                has_eoi_marker=False,
                errors=["File is empty."],
                warnings=[],
            )

        has_valid_header = data.startswith(b"\xff\xd8\xff")
        has_eoi_marker = b"\xff\xd9" in data

        if not has_valid_header:
            errors.append("Missing JPEG SOI marker (FF D8 FF).")

        if len(data) < 3:
            errors.append("File is too small to be a valid JPEG header.")

        if len(data) < 10 and has_valid_header:
            warnings.append("JPEG header present but payload is extremely small.")

        if not has_eoi_marker and has_valid_header:
            warnings.append("Missing JPEG EOI marker (FF D9); file may be partial.")

        decodable = False
        if has_valid_header and Image is not None:
            try:
                from io import BytesIO

                with Image.open(BytesIO(data)) as image:
                    image.verify()
                decodable = True
            except (OSError, ValueError, TypeError, UnidentifiedImageError):
                errors.append("JPEG starts with a valid marker but is not a decodable image.")

        if has_valid_header and not has_eoi_marker:
            status = "PARTIAL"
            is_valid = False
        elif has_valid_header and has_eoi_marker and decodable:
            status = "VALID"
            is_valid = True
        elif has_valid_header and has_eoi_marker and not decodable:
            status = "INVALID"
            is_valid = False
            errors.append("JPEG markers are present but the payload is not a decodable image.")
        else:
            status = "INVALID"
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            status=status,
            file_type="JPEG",
            size=len(data),
            has_valid_header=has_valid_header,
            has_eoi_marker=has_eoi_marker,
            errors=errors,
            warnings=warnings,
        )


class PNGValidator:
    def __init__(self, file_bytes: bytes) -> None:
        self.file_bytes = file_bytes

    def validate(self) -> ValidationResult:
        data = self.file_bytes
        signature = b"\x89PNG\r\n\x1a\n"
        end_marker = b"IEND\xaeB`\x82"
        errors: list[str] = []
        warnings: list[str] = []

        if not data:
            return ValidationResult(False, "INVALID", "PNG", 0, False, False, ["File is empty."], [])

        has_valid_header = data.startswith(signature)
        has_end_marker = data.endswith(end_marker)
        structurally_complete = False

        if not has_valid_header:
            errors.append("Missing PNG signature.")
        else:
            structurally_complete, structure_error = _validate_png_chunks(data, end_marker)
            if structure_error:
                if structure_error == "PNG data ends before a complete chunk is available.":
                    warnings.append(structure_error)
                else:
                    errors.append(structure_error)

        decodable = False
        if has_valid_header and structurally_complete and Image is not None:
            try:
                from io import BytesIO

                with Image.open(BytesIO(data)) as image:
                    image.verify()
                decodable = True
            except (OSError, ValueError, TypeError, UnidentifiedImageError):
                errors.append("PNG has a valid structure but is not a decodable image.")

        is_incomplete = not has_end_marker and not errors
        if has_valid_header and is_incomplete:
            status = "PARTIAL"
            is_valid = False
        elif has_valid_header and structurally_complete and decodable:
            status = "VALID"
            is_valid = True
        else:
            status = "INVALID"
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            status=status,
            file_type="PNG",
            size=len(data),
            has_valid_header=has_valid_header,
            has_eoi_marker=has_end_marker,
            errors=errors,
            warnings=warnings,
        )


def _validate_png_chunks(data: bytes, end_marker: bytes) -> tuple[bool, str | None]:
    position = 8

    while position + 12 <= len(data):
        length = int.from_bytes(data[position:position + 4], "big")
        chunk_end = position + 12 + length
        if chunk_end > len(data):
            return False, "PNG data ends before a complete chunk is available."

        chunk_type = data[position + 4:position + 8]
        chunk_data = data[position + 8:position + 8 + length]
        stored_crc = data[position + 8 + length:chunk_end]

        import zlib

        if zlib.crc32(chunk_type + chunk_data).to_bytes(4, "big") != stored_crc:
            return False, f"PNG chunk {chunk_type.decode('ascii', errors='replace')} has an invalid CRC."

        if chunk_type == b"IEND":
            return data[position:chunk_end].endswith(end_marker), None

        position = chunk_end

    return False, "PNG data ends before a complete chunk is available."


class PDFValidator:
    def __init__(self, file_bytes: bytes) -> None:
        self.file_bytes = file_bytes

    def validate(self) -> ValidationResult:
        data = self.file_bytes
        has_valid_header = data.startswith(b"%PDF-")
        eof_positions = _find_all(data, b"%%EOF")
        has_eof_marker = bool(eof_positions)
        errors: list[str] = []
        warnings: list[str] = []

        if not data:
            return ValidationResult(False, "INVALID", "PDF", 0, False, False, ["File is empty."], [])
        if not has_valid_header:
            errors.append("Missing PDF header (%PDF-).")

        if has_valid_header and not has_eof_marker:
            warnings.append("Missing PDF %%EOF marker; file may be partial.")
        elif has_eof_marker and data[eof_positions[-1] + 5:].strip():
            errors.append("PDF contains non-whitespace data after its final %%EOF marker.")

        has_trailer = b"trailer" in data
        has_startxref = b"startxref" in data
        has_object = b" obj" in data and b"endobj" in data

        if has_valid_header and has_eof_marker:
            if not has_trailer:
                errors.append("PDF is missing a trailer section.")
            if not has_startxref:
                errors.append("PDF is missing a startxref section.")
            if not has_object:
                errors.append("PDF contains no complete indirect object evidence.")

        if has_valid_header and not has_eof_marker and not errors:
            status = "PARTIAL"
            is_valid = False
        elif has_valid_header and has_eof_marker and not errors:
            status = "VALID"
            is_valid = True
        else:
            status = "INVALID"
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            status=status,
            file_type="PDF",
            size=len(data),
            has_valid_header=has_valid_header,
            has_eoi_marker=has_eof_marker,
            errors=errors,
            warnings=warnings,
        )


class MP3Validator:
    def __init__(self, file_bytes: bytes) -> None:
        self.file_bytes = file_bytes

    def validate(self) -> ValidationResult:
        data = self.file_bytes
        frames, incomplete, stream_end = parse_mp3_frames(data)
        has_id3 = data.startswith(b"ID3")
        id3_complete = not has_id3 or (stream_end >= 10 and stream_end <= len(data))
        has_valid_header = bool(frames and frames[0].offset == (stream_end - sum(frame.length for frame in frames))) or id3_complete and has_id3
        has_frame_structure = bool(frames)
        errors: list[str] = []
        warnings: list[str] = []

        if not data:
            return ValidationResult(False, "INVALID", "MP3", 0, False, False, ["File is empty."], [])
        if not has_valid_header:
            errors.append("Missing valid MP3 ID3 or MPEG Layer III frame header.")
        if has_id3 and not id3_complete:
            warnings.append("MP3 ID3 metadata is truncated; file may be partial.")
            if len(data) >= 10 and any(value & 0x80 for value in data[6:10]):
                errors.append("MP3 ID3 size uses invalid sync-safe bytes.")
        if has_id3 and not has_frame_structure and id3_complete:
            errors.append("MP3 contains an ID3 header but no valid MPEG audio frames.")
        if has_frame_structure and incomplete:
            warnings.append("MP3 ends inside an incomplete MPEG audio frame.")

        if has_frame_structure and not incomplete and stream_end < len(data):
            trailing = data[stream_end:]
            if not (trailing.startswith(b"TAG") and len(trailing) >= 128):
                errors.append("MP3 contains data after the last complete audio frame.")

        if has_frame_structure and not errors and not incomplete:
            status = "VALID"
            is_valid = True
        elif has_frame_structure and incomplete and not errors:
            status = "PARTIAL"
            is_valid = False
        elif has_id3 and not id3_complete and not errors:
            status = "PARTIAL"
            is_valid = False
        else:
            status = "INVALID"
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            status=status,
            file_type="MP3",
            size=len(data),
            has_valid_header=has_valid_header,
            has_eoi_marker=has_frame_structure,
            errors=errors,
            warnings=warnings,
        )


class MP4Validator:
    def __init__(self, file_bytes: bytes) -> None:
        self.file_bytes = file_bytes

    def validate(self) -> ValidationResult:
        data = self.file_bytes
        parsed = parse_mp4_boxes(data)
        errors: list[str] = []
        warnings: list[str] = []
        has_valid_header = bool(parsed.boxes and parsed.boxes[0].box_type == b"ftyp" and parsed.boxes[0].offset == 0)
        has_end_marker = parsed.complete

        if not data:
            return ValidationResult(False, "INVALID", "MP4", 0, False, False, ["File is empty."], [])
        if not has_valid_header:
            errors.append("MP4 must begin with a valid ftyp box.")
        elif not _valid_mp4_ftyp(data, parsed.boxes[0]):
            errors.append("MP4 ftyp box is too short or has an invalid brand.")

        box_types = {box.box_type for box in parsed.boxes}
        if not parsed.complete and parsed.end_offset + 8 <= len(data):
            partial_box_type = data[parsed.end_offset + 4:parsed.end_offset + 8]
            if all(32 <= value < 127 for value in partial_box_type):
                box_types.add(partial_box_type)
        if b"moov" not in box_types:
            errors.append("MP4 is missing a moov box.")
        if b"mdat" not in box_types:
            errors.append("MP4 is missing an mdat box.")

        if not parsed.complete and parsed.error:
            if "extends beyond" in parsed.error:
                warnings.append(parsed.error)
            else:
                errors.append(parsed.error)

        if has_valid_header and not parsed.complete and not errors:
            status = "PARTIAL"
            is_valid = False
        elif has_valid_header and parsed.complete and not errors:
            status = "VALID"
            is_valid = True
        else:
            status = "INVALID"
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            status=status,
            file_type="MP4",
            size=len(data),
            has_valid_header=has_valid_header,
            has_eoi_marker=has_end_marker,
            errors=errors,
            warnings=warnings,
        )


def _valid_mp4_ftyp(data: bytes, box: MP4Box) -> bool:
    if box.box_type != b"ftyp" or box.size < box.header_size + 8:
        return False
    payload_start = box.offset + box.header_size
    major_brand = data[payload_start:payload_start + 4]
    return len(major_brand) == 4 and all(32 <= value < 127 for value in major_brand)


class GIFValidator:
    def __init__(self, file_bytes: bytes) -> None:
        self.file_bytes = file_bytes

    def validate(self) -> ValidationResult:
        data = self.file_bytes
        parsed = parse_gif(data)
        has_valid_header = data[:6] in (b"GIF87a", b"GIF89a")
        errors: list[str] = []
        warnings: list[str] = []

        if not data:
            return ValidationResult(False, "INVALID", "GIF", 0, False, False, ["File is empty."], [])
        if not has_valid_header:
            errors.append("Missing GIF87a or GIF89a header.")
        if parsed.error and not parsed.truncated:
            errors.append(parsed.error)
        if parsed.truncated:
            warnings.append(parsed.error or "GIF data is incomplete.")
        if parsed.complete and parsed.end_offset != len(data):
            errors.append("GIF contains data after its trailer.")
        if parsed.image_count == 0 and has_valid_header and not parsed.truncated:
            errors.append("GIF contains no image descriptor.")

        if has_valid_header and parsed.truncated and not errors:
            status = "PARTIAL"
            is_valid = False
        elif has_valid_header and parsed.complete and parsed.image_count > 0 and not errors:
            status = "VALID"
            is_valid = True
        else:
            status = "INVALID"
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            status=status,
            file_type="GIF",
            size=len(data),
            has_valid_header=has_valid_header,
            has_eoi_marker=parsed.complete,
            errors=errors,
            warnings=warnings,
        )


class BMPValidator:
    def __init__(self, file_bytes: bytes) -> None:
        self.file_bytes = file_bytes

    def validate(self) -> ValidationResult:
        data = self.file_bytes
        parsed = parse_bmp(data)
        has_valid_header = data.startswith(b"BM")
        errors: list[str] = []
        warnings: list[str] = []

        if not data:
            return ValidationResult(False, "INVALID", "BMP", 0, False, False, ["File is empty."], [])
        if not has_valid_header:
            errors.append("Missing BMP BM signature.")
        if parsed.error and not parsed.truncated:
            errors.append(parsed.error)
        if parsed.truncated:
            warnings.append(parsed.error or "BMP data is incomplete.")
        if parsed.complete and parsed.end_offset != len(data):
            errors.append("BMP contains data beyond its declared file size.")

        if has_valid_header and parsed.truncated and not errors:
            status = "PARTIAL"
            is_valid = False
        elif has_valid_header and parsed.complete and not errors:
            status = "VALID"
            is_valid = True
        else:
            status = "INVALID"
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            status=status,
            file_type="BMP",
            size=len(data),
            has_valid_header=has_valid_header,
            has_eoi_marker=parsed.complete,
            errors=errors,
            warnings=warnings,
        )


class TIFFValidator:
    def __init__(self, file_bytes: bytes) -> None:
        self.file_bytes = file_bytes

    def validate(self) -> ValidationResult:
        data = self.file_bytes
        parsed = parse_tiff(data)
        has_valid_header = data[:4] in (b"II*\x00", b"MM\x00*")
        errors: list[str] = []
        warnings: list[str] = []

        if not data:
            return ValidationResult(False, "INVALID", "TIFF", 0, False, False, ["File is empty."], [])
        if not has_valid_header:
            errors.append("Missing classic TIFF byte-order and magic header.")
        if parsed.error and not parsed.truncated:
            errors.append(parsed.error)
        if parsed.truncated:
            warnings.append(parsed.error or "TIFF data is incomplete.")
        if parsed.complete and parsed.end_offset != len(data):
            errors.append("TIFF contains data beyond its referenced ranges.")

        required_tags = {256, 257, 258, 259, 273, 279}
        if not required_tags.issubset(parsed.image_tags):
            errors.append("TIFF is missing required image IFD tags.")
        if parsed.width is not None and parsed.width <= 0:
            errors.append("TIFF image width is invalid.")
        if parsed.height is not None and parsed.height == 0:
            errors.append("TIFF image height is invalid.")
        if not parsed.bits_per_sample or any(bits not in {1, 2, 4, 8, 16, 24, 32} for bits in parsed.bits_per_sample):
            errors.append("TIFF bits-per-sample value is unsupported.")
        if parsed.compression not in (None, 1):
            errors.append("TIFF compression is unsupported for this recovery path.")

        if has_valid_header and parsed.truncated and not errors:
            status = "PARTIAL"
            is_valid = False
        elif has_valid_header and parsed.complete and not errors:
            status = "VALID"
            is_valid = True
        else:
            status = "INVALID"
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            status=status,
            file_type="TIFF",
            size=len(data),
            has_valid_header=has_valid_header,
            has_eoi_marker=parsed.complete,
            errors=errors,
            warnings=warnings,
        )


class WebPValidator:
    def __init__(self, file_bytes: bytes) -> None:
        self.file_bytes = file_bytes

    def validate(self) -> ValidationResult:
        data = self.file_bytes
        parsed = parse_webp(data)
        has_valid_header = len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP"
        errors: list[str] = []
        warnings: list[str] = []

        if not data:
            return ValidationResult(False, "INVALID", "WEBP", 0, False, False, ["File is empty."], [])
        if not has_valid_header:
            errors.append("Missing RIFF/WEBP header.")
        if parsed.error and not parsed.truncated:
            errors.append(parsed.error)
        if parsed.truncated:
            warnings.append(parsed.error or "WebP data is incomplete.")
        if parsed.complete and parsed.end_offset != len(data):
            errors.append("WebP contains data beyond its declared RIFF size.")

        if has_valid_header and parsed.truncated and not errors:
            status = "PARTIAL"
            is_valid = False
        elif has_valid_header and parsed.complete and not errors:
            status = "VALID"
            is_valid = True
        else:
            status = "INVALID"
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            status=status,
            file_type="WEBP",
            size=len(data),
            has_valid_header=has_valid_header,
            has_eoi_marker=parsed.complete,
            errors=errors,
            warnings=warnings,
        )


def _find_all(data: bytes, marker: bytes) -> list[int]:
    positions: list[int] = []
    start = 0
    while True:
        position = data.find(marker, start)
        if position == -1:
            return positions
        positions.append(position)
        start = position + 1
