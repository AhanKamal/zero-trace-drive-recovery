# Drive Recovery

A modular multi-format recovery tool for carving and validating common image, document, audio, and video artifacts from `.img`/`.dd` images and explicitly selected physical drives on supported Windows environments.

## MVP

The current implementation supports JPEG, PNG, PDF, MP3, MP4, GIF, BMP, classic TIFF, and WebP recovery from raw disk images.

It can:

- Scan a disk image for JPEG signatures
- Scan a disk image for PNG signatures and PNG chunk boundaries
- Scan a disk image for PDF signatures and structurally supported EOF boundaries
- Scan a disk image for ID3 and MPEG Layer III frame signatures
- Scan a disk image for MP4 `ftyp` box signatures
- Scan a disk image for GIF87a and GIF89a signatures
- Scan a disk image for BMP `BM` signatures with header validation
- Scan a disk image for little-endian and big-endian classic TIFF signatures
- Scan a disk image for RIFF/WEBP signatures at their structural offset
- Carve complete JPEG files
- Carve complete PNG files using the PNG chunk structure and IEND marker
- Carve complete PDF files using trailer, startxref, and %%EOF evidence
- Carve MP3 streams using ID3 metadata and MPEG Layer III frame lengths
- Carve MP4 containers using bounded ISO BMFF box sizes
- Carve GIF streams using logical screen data, block boundaries, and the GIF trailer
- Carve BMP files using declared file sizes and pixel-data boundaries
- Carve TIFF files using bounded IFD chains and referenced strip ranges
- Carve WebP files using RIFF chunk sizes and image payload chunks
- Detect and preserve partial JPEG fragments
- Detect and preserve partial PNG fragments
- Detect and preserve partial PDF fragments
- Detect and preserve partial MP3 streams with incomplete frames
- Detect and preserve partial MP4 containers with truncated boxes
- Detect and preserve partial GIF streams with truncated blocks or missing trailers
- Detect and preserve partial BMP files truncated before their declared file size
- Detect and preserve partial TIFF files truncated in IFD or pixel-data ranges
- Detect and preserve partial WebP files truncated in RIFF chunks
- Validate recovered JPEG files
- Validate PNG signatures, chunk CRCs, IEND structure, and image decodability
- Validate PDF headers, object evidence, trailer, startxref, and %%EOF structure
- Validate MP3 ID3 metadata and MPEG Layer III frame structure
- Validate MP4 `ftyp`, `moov`, `mdat`, and safe box boundaries
- Validate GIF headers, color tables, image data sub-blocks, and trailers
- Validate BMP headers, DIB fields, dimensions, pixel offsets, and supported uncompressed layouts
- Validate TIFF byte order, magic 42, IFD entries, typed offsets, image tags, and strip ranges
- Validate WebP RIFF size, chunk boundaries, and VP8/VP8L/VP8X payload evidence
- Attempt reconstruction of recoverable JPEG fragments
- Write recovered files to an output directory
- Provide recovery statistics through a command-line interface
- Work with both `.img` and `.dd` disk-image files
- Read explicitly selected physical drives through bounded read-only access on Windows
- Separate raw signature hits from overlap-consolidated unique candidates

## Architecture

```text
Disk Image (.img / .dd)
        |
        v
Signature Scanner
        |
        v
Format Candidates
        |
        v
Format-Aware Carver
        |
        v
Reconstruction Engine
        |
        v
Format-Aware Validator
        |
        v
Recovered / Partial Files
Components
app/image_reader.py

Defines the common bounded raw-data source contract, read-only disk-image reader, and Windows physical-device reader.

app/physical_devices.py

Provides safe Windows physical-device enumeration, path validation, and read-only reader factories.

app/signatures.py

Contains extensible format definitions, signatures, end markers, extensions, and support status.

app/scanner.py

Searches the disk image for known file signatures.

app/carver.py

Extracts JPEG, PNG, PDF, MP3, MP4, GIF, BMP, TIFF, and WebP data from detected locations. `JPEGCarver` remains available for compatibility.

app/validator.py

Checks JPEG markers and decodability, validates PNG structure and decodability, conservative PDF structure, MP3 frame structure, MP4 ISO BMFF box structure, GIF block structure, BMP/DIB structure, classic TIFF IFD structure, and WebP RIFF structure.

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

The current test suite contains 136 tests covering:

JPEG carving
PNG carving and validation
PDF carving and validation
MP3 frame detection, carving, validation, and partial recovery
MP4 box parsing, carving, validation, and partial recovery
GIF signature detection, parsing, carving, validation, and partial recovery
BMP signature detection, header parsing, carving, validation, and partial recovery
Little-endian and big-endian TIFF parsing, carving, validation, and partial recovery
WebP offset signatures, RIFF parsing, carving, validation, and partial recovery
Mixed-format end-to-end recovery
Read-only source abstraction, fake-device reads, source offsets, and output separation
CLI behavior
End-to-end recovery
Image reading
Reconstruction
Recovery engine behavior
Signature scanning
JPEG, PNG, PDF, MP3, MP4, GIF, BMP, TIFF, and WebP validation
Recover Files

Basic usage:

.\.venv\Scripts\python.exe -m app recover ".\disk.img"

Specify an output directory:

.\.venv\Scripts\python.exe -m app recover ".\disk.img" --output ".\recovered"

The same command can be used with .dd images:

.\.venv\Scripts\python.exe -m app recover ".\disk.dd" --output ".\recovered"

Physical Devices

List available physical devices on Windows:

.\.venv\Scripts\python.exe -m app devices

Recover from an explicitly selected physical device:

.\.venv\Scripts\python.exe -m app recover-device "\\.\PhysicalDrive1" --output ".\recovered"

Physical-device recovery is read-only and may require elevated privileges. The output directory must be separate from the source device. The application does not automatically select, mount, modify, format, repair, or write to physical devices.
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

The recovered JPEG, PNG, PDF, MP3, MP4, GIF, BMP, TIFF, or WebP was successfully processed by the recovery and reconstruction pipeline.

PARTIAL

A JPEG, PNG, PDF, MP3, MP4, GIF, BMP, TIFF, or WebP signature was found, but the available data was incomplete. The partial fragment is preserved rather than discarded.

REJECTED

A candidate was detected but did not meet the recovery/validation requirements.

Testing with the Synthetic Disk Image

The project includes synthetic image generators for testing the recovery pipeline without using a real storage device.

Generate a synthetic disk image:

.\.venv\Scripts\python.exe -c "from pathlib import Path; from app.synthetic_image_generator import create_synthetic_disk_image; p=create_synthetic_disk_image(Path(r'.\tmp_final_debug'), filename='synthetic_disk.img'); print('Generated:', p)"

Recover from it:

.\.venv\Scripts\python.exe -m app recover ".\tmp_final_debug\synthetic_disk.img" --output ".\mvp_output"
Important Note

This is an MVP for JPEG, PNG, PDF, MP3, MP4, GIF, BMP, classic TIFF, and WebP recovery from disk images and explicitly selected physical devices.

It is intended for development, testing and demonstration purposes. It should not be treated as a complete forensic recovery suite.

Currently supported formats

- JPEG/JPG
- PNG
- PDF
- MP3
- MP4
- GIF
- BMP
- TIFF
- WebP

Currently supported source types

- Disk images (`.img` and `.dd`)
- Physical drives on supported Windows environments

Detection-only formats

- ZIP (signature detection only; archive carving and validation are not implemented)

Physical recovery limitations

- Physical-device access may require elevated privileges and depends on Windows device availability.
- Deleted data may be unavailable after overwrite, SSD TRIM, garbage collection, encryption, or other loss of raw accessibility.
- Physical-device recovery is not filesystem-aware deleted-file recovery.
- Fragmented-file reconstruction remains conservative and format-dependent.
- The project does not claim universal file-format support or complete forensic recovery.

Future formats

Additional image, document, audio, video, archive, executable, database, and forensic formats are future work, along with stronger fragmented-file reconstruction and deeper filesystem-aware recovery. BigTIFF, complex/unsupported TIFF compression variants, and fragmented TIFF/WebP reconstruction are not claimed.

The current MVP does not attempt to recover every possible file format or handle every type of filesystem corruption.

Project Structure
sih-drive-recovery/
|
├── app/
│   ├── __main__.py
│   ├── carver.py
│   ├── cli.py
│   ├── image_reader.py
│   ├── physical_devices.py
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
│   ├── test_sources.py
│   └── test_validator.py
|
├── README.md
└── requirements.txt