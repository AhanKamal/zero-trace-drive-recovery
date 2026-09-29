from pathlib import Path
from io import BytesIO
import struct

from PIL import Image


def make_valid_jpeg() -> bytes:
    image = Image.new("RGB", (40, 40))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def make_valid_png() -> bytes:
    image = Image.new("RGBA", (40, 40), color=(20, 80, 140, 255))
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def make_valid_pdf() -> bytes:
    header = b"%PDF-1.4\n"
    objects = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Count 0 >>\nendobj\n",
    ]
    body = header
    offsets = [0]
    for obj in objects:
        offsets.append(len(body))
        body += obj
    xref_offset = len(body)
    xref = b"xref\n0 3\n0000000000 65535 f \n" + b"".join(
        f"{offset:010d} 00000 n \n".encode("ascii") for offset in offsets[1:]
    )
    trailer = b"trailer\n<< /Size 3 /Root 1 0 R >>\nstartxref\n" + str(xref_offset).encode("ascii") + b"\n%%EOF\n"
    return body + xref + trailer


def make_valid_mp3(frame_count: int = 3) -> bytes:
    id3_header = b"ID3\x04\x00\x00\x00\x00\x00\x00"
    frame_header = b"\xff\xfb\x90\x64"
    frame_length = 417
    frame_payload = bytes((index % 251 for index in range(frame_length - len(frame_header))))
    frame = frame_header + frame_payload
    return id3_header + frame * frame_count


def make_valid_mp4() -> bytes:
    def box(box_type: bytes, payload: bytes) -> bytes:
        return (8 + len(payload)).to_bytes(4, "big") + box_type + payload

    ftyp = box(b"ftyp", b"isom\x00\x00\x02\x00isomiso2")
    moov = box(b"moov", b"\x00\x00\x00\x00minimal-moov")
    mdat = box(b"mdat", bytes(range(32)))
    return ftyp + moov + mdat


def make_valid_gif() -> bytes:
    image = Image.new("P", (24, 24))
    image.putdata([(x + y) % 4 for y in range(24) for x in range(24)])
    image.putpalette([0, 0, 0, 80, 80, 80, 160, 160, 160, 255, 255, 255] + [0] * 756)
    buffer = BytesIO()
    image.save(buffer, format="GIF", optimize=False)
    return buffer.getvalue()


def make_valid_bmp() -> bytes:
    width = 2
    height = 2
    pixel_offset = 54
    row_stride = 8
    pixel_data = (
        b"\xff\x00\x00" + b"\x00\xff\x00" + b"\x00\x00"
        + b"\x00\x00\xff" + b"\xff\xff\xff" + b"\x00\x00"
    )
    file_size = pixel_offset + len(pixel_data)
    file_header = b"BM" + file_size.to_bytes(4, "little") + b"\x00\x00\x00\x00" + pixel_offset.to_bytes(4, "little")
    dib_header = (
        (40).to_bytes(4, "little")
        + width.to_bytes(4, "little", signed=True)
        + height.to_bytes(4, "little", signed=True)
        + (1).to_bytes(2, "little")
        + (24).to_bytes(2, "little")
        + (0).to_bytes(4, "little")
        + len(pixel_data).to_bytes(4, "little")
        + (2835).to_bytes(4, "little", signed=True)
        + (2835).to_bytes(4, "little", signed=True)
        + (0).to_bytes(4, "little")
        + (0).to_bytes(4, "little")
    )
    return file_header + dib_header + pixel_data


def make_valid_tiff(byte_order: str = "<") -> bytes:
    if byte_order not in ("<", ">"):
        raise ValueError("byte_order must be '<' or '>'")
    marker = b"II" if byte_order == "<" else b"MM"

    def pack(fmt: str, *values: int) -> bytes:
        return struct.pack(byte_order + fmt, *values)

    pixel_offset = 122
    pixels = b"\x10\x20\x30\x40"
    entries = [
        pack("HHI", 256, 3, 1) + pack("H", 2) + b"\x00\x00",
        pack("HHI", 257, 3, 1) + pack("H", 2) + b"\x00\x00",
        pack("HHI", 258, 3, 1) + pack("H", 8) + b"\x00\x00",
        pack("HHI", 259, 3, 1) + pack("H", 1) + b"\x00\x00",
        pack("HHI", 262, 3, 1) + pack("H", 1) + b"\x00\x00",
        pack("HHII", 273, 4, 1, pixel_offset),
        pack("HHI", 277, 3, 1) + pack("H", 1) + b"\x00\x00",
        pack("HHII", 278, 4, 1, 2),
        pack("HHII", 279, 4, 1, len(pixels)),
    ]
    header = marker + pack("H", 42) + pack("I", 8)
    ifd = pack("H", len(entries)) + b"".join(entries) + pack("I", 0)
    return header + ifd + pixels


def make_valid_webp() -> bytes:
    image = Image.new("RGB", (16, 16), color=(40, 90, 140))
    buffer = BytesIO()
    image.save(buffer, format="WEBP", lossless=True)
    return buffer.getvalue()


def create_synthetic_disk_image(
    path: Path, filename: str | None = None
) -> Path:
    if filename is not None:
        path.mkdir(parents=True, exist_ok=True)
        path = path / filename

    jpeg = make_valid_jpeg()

    data = (
        b"\x00" * 67
        + jpeg
        + b"\x00" * 49
        + jpeg
        + b"\x00" * 33
        + jpeg[:62]
        + b"\x00" * 20
    )

    path.write_bytes(data)
    return path


def create_synthetic_multi_format_disk_image(path: Path, filename: str = "synthetic_multi_format.img") -> Path:
    jpeg = make_valid_jpeg()
    png = make_valid_png()
    pdf = make_valid_pdf()
    mp3 = make_valid_mp3()
    mp4 = make_valid_mp4()
    gif = make_valid_gif()
    bmp = make_valid_bmp()
    tiff = make_valid_tiff()
    webp = make_valid_webp()
    data = (
        b"\x00" * 67
        + jpeg
        + b"\x00" * 49
        + png
        + b"\x00" * 33
        + pdf
        + b"\x00" * 20
        + mp3
        + b"\x00" * 20
        + mp4
        + b"\x00" * 20
        + gif
        + b"\x00" * 20
        + bmp
        + b"\x00" * 20
        + tiff
        + b"\x00" * 20
        + webp
        + b"\x00" * 20
        + jpeg[:62]
        + b"\x00" * 20
    )
    path.mkdir(parents=True, exist_ok=True)
    image_path = path / filename
    image_path.write_bytes(data)
    return image_path