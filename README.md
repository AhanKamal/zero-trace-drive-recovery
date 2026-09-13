# Zero Trace Drive Recovery

JPEG disk image recovery component for the Zero Trace project.

## Overview

Zero Trace Drive Recovery is a lightweight Python-based recovery component designed to identify and recover JPEG files from raw disk images.

The current MVP focuses on recovering JPEG files from `.img` and `.dd` disk image files.

## Features

* Scan raw disk images for JPEG file signatures
* Detect JPEG file candidates
* Validate recovered JPEG data
* Reconstruct recoverable JPEG files
* Support partial JPEG recovery
* Assign recovery IDs to recovered files
* Calculate recovery confidence scores
* Generate structured recovery results
* Command-line interface
* GUI interface for testing and demonstration

## Supported Input

The current MVP supports:

* `.img` disk images
* `.dd` disk images

Currently supported file type:

* JPEG / JPG

Other file types are not currently part of the MVP.

## Recovery Status

Each detected file is classified into one of the following statuses:

* `RECONSTRUCTED` — File was successfully reconstructed
* `PARTIAL` — Only part of the file could be recovered
* `REJECTED` — Candidate did not pass recovery or validation requirements

## How It Works

The recovery pipeline follows these stages:

```text
Disk Image
    |
    v
Image Reader
    |
    v
JPEG Signature Scanner
    |
    v
Candidate Detection
    |
    v
JPEG Carving
    |
    v
Reconstruction
    |
    v
Validation
    |
    v
Recovered Files
```

### 1. Read

The disk image is read as raw binary data.

### 2. Scan

The scanner searches the image for known JPEG signatures and identifies possible JPEG file locations.

### 3. Carve

Detected candidates are extracted from the disk image.

### 4. Reconstruct

Recoverable JPEG data is reconstructed into output files.

### 5. Validate

Recovered files are checked to determine whether they are valid, partial, or rejected.

### 6. Output

Recovered files are written to the selected output directory along with their recovery information.

## Project Structure

```text
zero-trace-drive-recovery/
|
+-- app/
|   +-- __main__.py
|   +-- carver.py
|   +-- cli.py
|   +-- gui.py
|   +-- image_reader.py
|   +-- reconstruction.py
|   +-- recovery.py
|   +-- scanner.py
|   +-- signatures.py
|   +-- synthetic_image_generator.py
|   +-- validator.py
|
+-- tests/
|   +-- test_carver.py
|   +-- test_cli.py
|   +-- test_end_to_end.py
|   +-- test_image_generator.py
|   +-- test_image_reader.py
|   +-- test_reconstruction.py
|   +-- test_recovery.py
|   +-- test_scanner.py
|   +-- test_validator.py
|
+-- .gitignore
+-- README.md
```

## Installation

Clone the repository:

```bash
git clone https://github.com/AhanKamal/zero-trace-drive-recovery.git
cd zero-trace-drive-recovery
```

Create a virtual environment:

### Windows

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Linux / macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the required dependencies:

```bash
pip install -r requirements.txt
```

## Running the Recovery Tool

The recovery component can be run through the command-line interface or GUI.

### CLI

```bash
python -m app recover ".\disk.img"
```

Specify an output directory:

```bash
python -m app recover ".\disk.img" --output ".\recovered"
```

The same command can be used with `.dd` images:

```bash
python -m app recover ".\disk.dd" --output ".\recovered"
```

### GUI

```bash
python -m app.gui
```

The GUI allows you to select a disk image and output directory before starting recovery.

## Example

Input:

```text
synthetic_disk.img
```

Output:

```text
recovered/
|
+-- REC-0001.jpg
+-- REC-0002.jpg
+-- REC-0003.jpg
```

Example recovery results:

```text
REC-0001    JPEG    RECONSTRUCTED    663 bytes    0.900
REC-0002    JPEG    RECONSTRUCTED    663 bytes    0.900
REC-0003    JPEG    PARTIAL           82 bytes    0.550
```

## Testing

The project includes unit tests and end-to-end tests covering the recovery pipeline.

Run the complete test suite with:

```bash
pytest -q
```

The current test suite contains 67 tests covering:

* JPEG carving
* CLI behavior
* End-to-end recovery
* Image reading
* Reconstruction
* Recovery engine behavior
* Signature scanning
* JPEG validation
* Synthetic image generation

## MVP Scope

The current MVP is intentionally focused on JPEG recovery from raw disk images.

Included:

* Disk image reading
* JPEG signature detection
* JPEG carving
* JPEG reconstruction
* JPEG validation
* Partial recovery handling
* Confidence scoring
* CLI
* GUI
* Automated tests

Future extensions may include:

* Additional image formats
* Document recovery
* Audio recovery
* Video recovery
* More advanced filesystem-aware recovery
* Metadata extraction
* Improved fragmented-file reconstruction
* Larger disk image support
* Integration with the main Zero Trace application

These features are outside the current MVP scope.

## Integration

This repository is intended to serve as a recovery component for the Zero Trace project.

The primary recovery implementation is located in:

```text
app/recovery.py
```

Supporting functionality is divided across the scanner, carver, reconstruction, image reader, and validator modules.

## Development

Run the test suite before submitting changes:

```bash
pytest -q
```

Keep generated files, disk images, virtual environments, and temporary debugging output outside version control.


