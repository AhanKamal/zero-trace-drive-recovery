# Drive Recovery

A lightweight disk-image recovery tool for identifying and recovering JPEG files from `.img` and `.dd` disk images.

## MVP

The current MVP focuses on JPEG file recovery from raw disk images.

It can:

- Scan a disk image for JPEG signatures
- Carve complete JPEG files
- Detect and preserve partial JPEG fragments
- Validate recovered JPEG files
- Attempt reconstruction of recoverable JPEG fragments
- Write recovered files to an output directory
- Provide recovery statistics through a command-line interface
- Work with both `.img` and `.dd` disk-image files

## Architecture

```text
Disk Image (.img / .dd)
        |
        v
Signature Scanner
        |
        v
JPEG Candidates
        |
        v
JPEG Carver
        |
        v
JPEG Validator
        |
        v
Reconstruction Engine
        |
        v
Recovered / Partial Files
Components
app/image_reader.py

Reads the disk image in chunks.

app/signatures.py

Contains file signatures used by the scanner.

app/scanner.py

Searches the disk image for known file signatures.

app/carver.py

Extracts JPEG data from detected locations.

app/validator.py

Checks JPEG headers, markers and decodability.

app/reconstruction.py

Handles reconstruction of recoverable fragments.

app/recovery.py

Coordinates the complete recovery pipeline.

app/cli.py

Provides the command-line interface.

Requirements
Python 3.10+
Pillow
pytest
Setup

Create a virtual environment:

python -m venv .venv

Activate it:

.\.venv\Scripts\Activate.ps1

Install dependencies:

pip install -r requirements.txt
Running the Tests

Run the complete test suite:

.\.venv\Scripts\python.exe -m pytest

The current test suite contains 67 tests covering:

JPEG carving
CLI behavior
End-to-end recovery
Image reading
Reconstruction
Recovery engine behavior
Signature scanning
JPEG validation
Recover Files

Basic usage:

.\.venv\Scripts\python.exe -m app recover ".\disk.img"

Specify an output directory:

.\.venv\Scripts\python.exe -m app recover ".\disk.img" --output ".\recovered"

The same command can be used with .dd images:

.\.venv\Scripts\python.exe -m app recover ".\disk.dd" --output ".\recovered"
Example Output
Drive Recovery
==============

Source: disk.img
Output: recovered

Scanning...

Recovery summary
----------------
Files/candidates found: 3
Successfully recovered: 2
Partial recoveries: 1
Rejected: 0
Output directory: recovered

Recovered files
---------------

REC-0001.jpg     RECONSTRUCTED  663 bytes
REC-0002.jpg     RECONSTRUCTED  663 bytes
REC-0003.jpg     PARTIAL        82 bytes
Recovery Status
RECONSTRUCTED

The recovered JPEG was successfully processed by the recovery and reconstruction pipeline.

PARTIAL

A JPEG signature was found, but the available data was incomplete. The partial fragment is preserved rather than discarded.

REJECTED

A candidate was detected but did not meet the recovery/validation requirements.

Testing with the Synthetic Disk Image

The project includes a synthetic image generator for testing the recovery pipeline without using a real storage device.

Generate a synthetic disk image:

.\.venv\Scripts\python.exe -c "from pathlib import Path; from app.synthetic_image_generator import create_synthetic_disk_image; p=create_synthetic_disk_image(Path(r'.\tmp_final_debug'), filename='synthetic_disk.img'); print('Generated:', p)"

Recover from it:

.\.venv\Scripts\python.exe -m app recover ".\tmp_final_debug\synthetic_disk.img" --output ".\mvp_output"
Important Note

This is an MVP for JPEG recovery from raw disk images.

It is intended for development, testing and demonstration purposes. It should not be treated as a complete forensic recovery suite.

The current MVP does not attempt to recover every possible file format or handle every type of filesystem corruption.

Project Structure
sih-drive-recovery/
|
├── app/
│   ├── __main__.py
│   ├── carver.py
│   ├── cli.py
│   ├── image_reader.py
│   ├── reconstruction.py
│   ├── recovery.py
│   ├── scanner.py
│   ├── signatures.py
│   ├── synthetic_image_generator.py
│   └── validator.py
|
├── tests/
│   ├── test_carver.py
│   ├── test_cli.py
│   ├── test_end_to_end.py
│   ├── test_image_reader.py
│   ├── test_reconstruction.py
│   ├── test_recovery.py
│   ├── test_scanner.py
│   └── test_validator.py
|
├── README.md
└── requirements.txt