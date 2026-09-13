from pathlib import Path
from io import BytesIO

from PIL import Image


def make_valid_jpeg() -> bytes:
    image = Image.new("RGB", (40, 40))
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=90)
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