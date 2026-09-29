from __future__ import annotations

import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.image_reader import PhysicalDeviceReader, RawDataSource


_DEVICE_PATH_PATTERN = re.compile(r"^\\\\\.\\PhysicalDrive\d+$", re.IGNORECASE)


@dataclass(frozen=True)
class PhysicalDeviceInfo:
    device_id: str
    model: str
    capacity: int
    media_type: str
    path: str
    read_only: bool = True
    accessible: bool | None = None

    @property
    def capacity_label(self) -> str:
        if self.capacity <= 0:
            return "Unknown size"
        value = float(self.capacity)
        for suffix in ("B", "KB", "MB", "GB", "TB"):
            if value < 1024 or suffix == "TB":
                return f"{value:.1f} {suffix}"
            value /= 1024
        return "Unknown size"


@dataclass(frozen=True)
class PhysicalDeviceProbeResult:
    device_path: str
    device_size: int
    read_only_open_succeeded: bool
    bytes_read: int
    preview_hex: str


def validate_physical_device_path(device_path: str) -> str:
    normalized = device_path.strip()
    if not _DEVICE_PATH_PATTERN.fullmatch(normalized):
        raise ValueError("Invalid physical device path; expected \\\\.\\PhysicalDriveN.")
    return normalized


def physical_reader_factory(device_path: str) -> Callable[[], RawDataSource]:
    normalized = validate_physical_device_path(device_path)
    return lambda: PhysicalDeviceReader(normalized)


def probe_physical_device(
    device_path: str,
    reader_factory: Callable[[], RawDataSource] | None = None,
    max_bytes: int = 4096,
) -> PhysicalDeviceProbeResult:
    normalized = validate_physical_device_path(device_path)
    if max_bytes <= 0:
        raise ValueError("Probe size must be > 0.")
    factory = reader_factory or physical_reader_factory(normalized)

    with factory() as reader:
        device_size = reader.size
        read_size = min(max_bytes, device_size)
        data = reader.read(0, read_size) if read_size else b""
        if len(data) != read_size:
            raise OSError(f"Physical device returned a short read: expected {read_size}, got {len(data)}.")
        return PhysicalDeviceProbeResult(
            device_path=normalized,
            device_size=device_size,
            read_only_open_succeeded=True,
            bytes_read=len(data),
            preview_hex=data[:32].hex(" "),
        )


def validate_output_destination(device_path: str, output_dir: str | Path) -> Path:
    normalized_device = validate_physical_device_path(device_path).lower()
    output_path = Path(output_dir)
    if str(output_path).strip().lower() == normalized_device:
        raise ValueError("Recovery output must be separate from the physical source device.")
    if str(output_path).startswith("\\\\.\\PhysicalDrive"):
        raise ValueError("Recovery output cannot be a physical device path.")
    return output_path


def enumerate_physical_devices() -> list[PhysicalDeviceInfo]:
    if sys.platform != "win32":
        return []

    command = (
        "Get-CimInstance Win32_DiskDrive | "
        "Select-Object Index,Model,Size,MediaType | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", command],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    if completed.returncode != 0 or not completed.stdout.strip():
        return []

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return []
    records = payload if isinstance(payload, list) else [payload]
    devices: list[PhysicalDeviceInfo] = []
    for record in records:
        if not isinstance(record, dict) or record.get("Index") is None:
            continue
        device_id = str(record["Index"])
        try:
            index = int(record["Index"])
            capacity = int(record.get("Size") or 0)
        except (TypeError, ValueError):
            continue
        devices.append(
            PhysicalDeviceInfo(
                device_id=device_id,
                model=str(record.get("Model") or "Unknown device").strip(),
                capacity=capacity,
                media_type=str(record.get("MediaType") or "Unknown").strip(),
                path=f"\\\\.\\PhysicalDrive{index}",
            )
        )
    return devices
