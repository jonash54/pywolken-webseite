"""File validation and security checks."""

import struct

# LAS file magic: "LASF"
LAS_MAGIC = b"LASF"

# TIFF magic: little-endian "II" + 42, or big-endian "MM" + 42
TIFF_LE_MAGIC = b"II\x2a\x00"
TIFF_BE_MAGIC = b"MM\x00\x2a"

# BigTIFF magic
BIGTIFF_LE_MAGIC = b"II\x2b\x00"
BIGTIFF_BE_MAGIC = b"MM\x00\x2b"

MAX_FILE_SIZE = 540 * 1024 * 1024  # 540 MB


def validate_las_file(filepath):
    """Validate that a file is a real LAS/LAZ file by checking header structure."""
    try:
        with open(filepath, "rb") as f:
            magic = f.read(4)
            if magic != LAS_MAGIC:
                return False, "Not a valid LAS/LAZ file (bad magic bytes)"

            # Read header fields for sanity
            # Bytes 24-25: header size (should be >= 227 for LAS 1.0)
            f.seek(94)
            header_size_bytes = f.read(2)
            if len(header_size_bytes) < 2:
                return False, "LAS header too short"
            header_size = struct.unpack("<H", header_size_bytes)[0]
            if header_size < 100:
                return False, "LAS header size invalid"

            # Check point data format (byte 104, should be 0-10)
            # LAZ compression adds 128 to the point format ID
            f.seek(104)
            point_format = struct.unpack("<B", f.read(1))[0]
            if point_format >= 128:
                point_format -= 128
            if point_format > 10:
                return False, "Invalid point data format"

            return True, None
    except (OSError, struct.error):
        return False, "Could not read file"


def validate_tiff_file(filepath):
    """Validate that a file is a real GeoTIFF by checking header structure."""
    try:
        with open(filepath, "rb") as f:
            header = f.read(4)
            if header not in (
                TIFF_LE_MAGIC,
                TIFF_BE_MAGIC,
                BIGTIFF_LE_MAGIC,
                BIGTIFF_BE_MAGIC,
            ):
                return False, "Not a valid TIFF file (bad magic bytes)"

            # Check that IFD offset is reasonable
            if header[:2] == b"II":
                byte_order = "<"
            else:
                byte_order = ">"

            is_bigtiff = header[2:4] in (b"\x2b\x00", b"\x00\x2b")

            if is_bigtiff:
                # BigTIFF: 8-byte offset at position 8
                f.seek(8)
                offset_bytes = f.read(8)
                if len(offset_bytes) < 8:
                    return False, "BigTIFF header too short"
                ifd_offset = struct.unpack(f"{byte_order}Q", offset_bytes)[0]
            else:
                # Classic TIFF: 4-byte offset at position 4
                offset_bytes = f.read(4)
                if len(offset_bytes) < 4:
                    return False, "TIFF header too short"
                ifd_offset = struct.unpack(f"{byte_order}I", offset_bytes)[0]

            if ifd_offset < 8 or ifd_offset > MAX_FILE_SIZE:
                return False, "Invalid IFD offset"

            return True, None
    except (OSError, struct.error):
        return False, "Could not read file"


def validate_upload(filepath, expected_type):
    """Validate an uploaded file. expected_type is 'laz' or 'tif'."""
    import os

    size = os.path.getsize(filepath)
    if size > MAX_FILE_SIZE:
        return False, "File exceeds maximum size"
    if size < 100:
        return False, "File too small to be valid"

    if expected_type == "laz":
        return validate_las_file(filepath)
    elif expected_type == "tif":
        return validate_tiff_file(filepath)
    else:
        return False, "Unsupported file type"
