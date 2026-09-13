from pathlib import Path


def make_valid_jpeg() -> bytes:
    """Return a small, genuinely decodable JPEG."""
    from PIL import Image
    from io import BytesIO

    image = Image.new("RGB", (40, 40))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
    return buffer.getvalue()


def create_synthetic_disk_image(path: Path) -> Path:
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