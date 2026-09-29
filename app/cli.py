from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.physical_devices import enumerate_physical_devices, physical_reader_factory, probe_physical_device, validate_output_destination
from app.recovery import RecoveryEngine


def _print_summary(result, output_dir: Path) -> None:
    found = result.candidates_found
    recovered = sum(
        1 for item in result.recovered_files
        if item.status == "RECONSTRUCTED"
    )
    partial = sum(
        1 for item in result.recovered_files
        if item.status == "PARTIAL"
    )
    rejected = sum(
        1 for item in result.recovered_files
        if item.status == "REJECTED"
    )

    print()
    print("Recovery summary")
    print("----------------")
    print(f"Unique candidates found: {found}")
    print(f"Raw signature hits: {result.raw_signature_hits}")
    print(f"Files/candidates found: {found}")
    print(f"Successfully recovered: {recovered}")
    print(f"Partial recoveries: {partial}")
    print(f"Rejected: {rejected}")
    print(f"Output directory: {output_dir}")

    if result.recovered_files:
        print()
        print("Recovered files")
        print("---------------")

        for item in result.recovered_files:
            filename = Path(item.output_path).name
            print(
                f"{filename:<16} "
                f"{item.status:<14} "
                f"{item.size} bytes"
            )


def _validate_output_path(output_path: str) -> Path:
    output_dir = Path(output_path)

    if output_dir.exists() and not output_dir.is_dir():
        raise ValueError(f"Invalid output directory: {output_path}")

    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app",
        description="Drive Recovery CLI",
    )

    subparsers = parser.add_subparsers(dest="command")

    recover_parser = subparsers.add_parser(
        "recover",
        help="Recover supported files from a disk image",
    )

    recover_parser.add_argument(
        "source_image",
        help="Path to the source .img or .dd file",
    )

    recover_parser.add_argument(
        "--output",
        default="recovered",
        help="Directory for recovered output (default: recovered)",
    )

    subparsers.add_parser(
        "devices",
        help="List available physical storage devices",
    )

    device_parser = subparsers.add_parser(
        "recover-device",
        help="Recover from an explicitly selected physical device in read-only mode",
    )
    device_parser.add_argument(
        "device_path",
        help=r"Physical device path, for example \\.\PhysicalDrive1",
    )
    device_parser.add_argument(
        "--output",
        default="recovered",
        help="Directory for recovered output (default: recovered)",
    )

    probe_parser = subparsers.add_parser(
        "probe-device",
        help="Read a small bounded region from one physical device in read-only mode",
    )
    probe_parser.add_argument(
        "device_path",
        help=r"Physical device path, for example \\.\PhysicalDrive1",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2

    if args.command == "devices":
        devices = enumerate_physical_devices()
        print("Available physical devices:")
        print()
        if not devices:
            print("No physical devices available or enumeration is unsupported.")
            return 0
        print(f"{'ID':<5} {'MODEL':<32} {'SIZE':<12} {'TYPE':<12} PATH")
        for device in devices:
            print(f"{device.device_id:<5} {device.model[:31]:<32} {device.capacity_label:<12} {device.media_type[:11]:<12} {device.path}")
        return 0

    if args.command == "probe-device":
        try:
            result = probe_physical_device(args.device_path, max_bytes=4096)
            print("Physical device probe")
            print("---------------------")
            print(f"Device path: {result.device_path}")
            print(f"Reported device size: {result.device_size} bytes")
            print(f"Read-only open succeeded: {result.read_only_open_succeeded}")
            print(f"Bytes successfully read: {result.bytes_read}")
            print(f"Hex preview: {result.preview_hex}")
            return 0
        except (OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.command == "recover":
        source_path = Path(args.source_image)
        output_dir = Path(args.output)

        try:
            if not source_path.exists():
                raise FileNotFoundError(
                    f"Source image not found: {source_path}"
                )

            if not source_path.is_file():
                raise ValueError(
                    f"Invalid source image path: {source_path}"
                )

            output_dir = _validate_output_path(str(output_dir))

            print("Drive Recovery")
            print("==============")
            print(f"Source: {source_path}")
            print(f"Output: {output_dir}")
            print()
            print("Scanning...")

            result = RecoveryEngine(
                source_path,
                output_dir,
            ).recover()

            _print_summary(result, output_dir)

            return 0

        except (FileNotFoundError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    if args.command == "recover-device":
        try:
            output_dir = validate_output_destination(args.device_path, args.output)
            print("Drive Recovery")
            print("==============")
            print(f"Source device: {args.device_path}")
            print(f"Output: {output_dir}")
            print("WARNING: source device will be opened read-only; output must remain separate.")
            print()
            print("Scanning...")
            result = RecoveryEngine(
                args.device_path,
                output_dir,
                reader_factory=physical_reader_factory(args.device_path),
            ).recover()
            _print_summary(result, output_dir)
            return 0
        except (FileNotFoundError, OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            return 1

    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())