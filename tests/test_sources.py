from pathlib import Path

import pytest

from app.image_reader import DiskImageReader, RawDataSource
from app.physical_devices import probe_physical_device, validate_output_destination, validate_physical_device_path
from app.recovery import RecoveryEngine
from app.scanner import SignatureScanner
from app.synthetic_image_generator import make_valid_jpeg


class FakeSource:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.closed = False
        self.read_calls: list[tuple[int, int]] = []

    @property
    def size(self) -> int:
        return len(self.data)

    def read(self, offset: int, size: int) -> bytes:
        if offset < 0 or size <= 0 or offset + size > len(self.data):
            raise ValueError("invalid bounded read")
        self.read_calls.append((offset, size))
        return self.data[offset:offset + size]

    def iter_chunks(self, chunk_size: int, offset: int = 0):
        for start in range(offset, len(self.data), chunk_size):
            yield self.read(start, min(chunk_size, len(self.data) - start))

    def close(self) -> None:
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def test_disk_image_reader_remains_read_only(tmp_path: Path) -> None:
    image_path = tmp_path / "source.img"
    image_path.write_bytes(b"abcdef")

    with DiskImageReader(image_path) as reader:
        assert reader.size == 6
        assert reader.read(1, 3) == b"bcd"

    assert image_path.read_bytes() == b"abcdef"


def test_fake_source_scans_signature_across_chunks() -> None:
    source = FakeSource(b"xx\xff\xd8\xfftail")
    scanner = SignatureScanner("fake-source", chunk_size=2, reader_factory=lambda: source)

    candidates = scanner.scan()

    assert candidates[0].file_type == "JPEG"
    assert candidates[0].offset == 2
    assert source.read_calls
    assert max(size for _, size in source.read_calls) <= 2


def test_recovery_engine_accepts_custom_read_only_source(tmp_path: Path) -> None:
    jpeg = make_valid_jpeg()
    sources: list[FakeSource] = []

    def factory() -> FakeSource:
        source = FakeSource(b"prefix" + jpeg)
        sources.append(source)
        return source

    output_dir = tmp_path / "recovered"

    result = RecoveryEngine(
        r"\\.\PhysicalDrive99",
        output_dir,
        reader_factory=factory,
    ).recover()

    assert result.recovered_files
    assert result.recovered_files[0].source_offset == 6
    assert result.recovered_files[0].status == "RECONSTRUCTED"
    assert output_dir.exists()
    assert sources and all(source.closed for source in sources)


def test_physical_device_path_validation_is_explicit() -> None:
    assert validate_physical_device_path(r"\\.\PhysicalDrive1") == r"\\.\PhysicalDrive1"
    with pytest.raises(ValueError):
        validate_physical_device_path("disk.img")


def test_physical_output_must_not_be_device_path(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        validate_output_destination(r"\\.\PhysicalDrive1", r"\\.\PhysicalDrive1")
    assert validate_output_destination(r"\\.\PhysicalDrive1", tmp_path) == tmp_path


def test_probe_reads_only_a_small_bounded_region_and_closes() -> None:
    sources: list[FakeSource] = []

    def factory() -> FakeSource:
        source = FakeSource(bytes(range(256)) * 32)
        sources.append(source)
        return source

    result = probe_physical_device(r"\\.\PhysicalDrive7", reader_factory=factory)

    assert result.device_path == r"\\.\PhysicalDrive7"
    assert result.device_size == 8192
    assert result.read_only_open_succeeded is True
    assert result.bytes_read == 4096
    assert result.preview_hex.startswith("00 01 02")
    assert sources[0].read_calls == [(0, 4096)]
    assert sources[0].closed is True


def test_probe_fails_on_short_read() -> None:
    class ShortSource(FakeSource):
        def read(self, offset: int, size: int) -> bytes:
            return self.data[offset:offset + max(0, size - 1)]

    with pytest.raises(OSError, match="short read"):
        probe_physical_device(r"\\.\PhysicalDrive7", reader_factory=lambda: ShortSource(b"x" * 4096))


def test_probe_propagates_unavailable_or_access_errors() -> None:
    with pytest.raises(PermissionError):
        probe_physical_device(r"\\.\PhysicalDrive7", reader_factory=lambda: (_ for _ in ()).throw(PermissionError("denied")))
    with pytest.raises(OSError):
        probe_physical_device(r"\\.\PhysicalDrive7", reader_factory=lambda: (_ for _ in ()).throw(OSError("unavailable")))
