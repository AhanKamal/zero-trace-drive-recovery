from __future__ import annotations

import argparse
import sys
from pathlib import Path

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
        help="Recover JPEG files from a disk image",
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

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_usage(sys.stderr)
        return 2

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

    parser.print_usage(sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())