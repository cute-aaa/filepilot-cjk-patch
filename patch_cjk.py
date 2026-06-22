#!/usr/bin/env python3
"""
FilePilot CJK Patch — Fix Chinese/Japanese character display

Patches the Unicode range table in FPilot.exe v0.7.0 to include CJK
character ranges (Chinese ideographs, Japanese kana, fullwidth forms).

Usage:
    python patch_cjk.py <input_exe> [output_exe]

If output_exe is omitted, produces <input_name>_cjk.exe in the same directory.

Requirements:
    - Python 3.x
    - FPilot.exe v0.7.0 (2,184,784 bytes)

Technical:
    - Patch target: Unicode range table at file offset 0x1e5610
    - Format: 11 entries × 8 bytes each (start_u32 + end_u32, little-endian)
    - Located in .data section, referenced by DAT_1401e7010
"""

import struct
import sys
import os
import hashlib

# --- Constants ---

PATCH_OFFSET = 0x1E5610
EXPECTED_SIZE = 2_184_784
EXPECTED_MD5 = None  # Set to a known hash if you want strict validation

# Number of range entries (each is 2 × uint32)
NUM_ENTRIES = 11
ENTRY_SIZE = 8  # 4 bytes start + 4 bytes end
TABLE_SIZE = NUM_ENTRIES * ENTRY_SIZE  # 88 bytes

# Original ranges (for reference / verification)
ORIGINAL_RANGES = [
    (0x0020, 0x007F),  # Type 0:  Basic Latin
    (0x0080, 0x00FF),  # Type 1:  Latin-1 Supplement
    (0x0100, 0x017F),  # Type 2:  Latin Extended-A
    (0x0180, 0x024F),  # Type 3:  Latin Extended-B
    (0x0370, 0x03FF),  # Type 4:  Greek/Coptic
    (0x0400, 0x04FF),  # Type 5:  Cyrillic
    (0x0500, 0x052F),  # Type 6:  Cyrillic Supplement
    (0x2DE0, 0x2DFF),  # Type 7:  Cyrillic Extended-A
    (0xA640, 0xA69F),  # Type 8:  Cyrillic Extended-B
    (0x1C80, 0x1C8F),  # Type 9:  Cyrillic Extended-C
    (0x0300, 0x036F),  # Type 10: Combining Diacritical Marks
]

# Patched ranges: keep Latin (types 0-3), add CJK (types 4-10)
PATCHED_RANGES = [
    (0x0020, 0x007F),  # Type 0:  Basic Latin (unchanged)
    (0x0080, 0x00FF),  # Type 1:  Latin-1 Supplement (unchanged)
    (0x0100, 0x017F),  # Type 2:  Latin Extended-A (unchanged)
    (0x0180, 0x024F),  # Type 3:  Latin Extended-B (unchanged)
    (0x4E00, 0x5FFF),  # Type 4:  CJK Ideographs 1/5
    (0x6000, 0x6FFF),  # Type 5:  CJK Ideographs 2/5
    (0x7000, 0x7FFF),  # Type 6:  CJK Ideographs 3/5
    (0x8000, 0x8FFF),  # Type 7:  CJK Ideographs 4/5
    (0x9000, 0x9FFF),  # Type 8:  CJK Ideographs 5/5
    (0x3000, 0x30FF),  # Type 9:  CJK Symbols + Japanese Kana
    (0xFF00, 0xFFEF),  # Type 10: Fullwidth Forms
]


def count_chars(ranges):
    """Count total characters covered by a range list."""
    return sum(end - start + 1 for start, end in ranges)


def read_ranges(data, offset):
    """Read 11 Unicode range entries from binary data."""
    ranges = []
    for i in range(NUM_ENTRIES):
        start, end = struct.unpack_from('<II', data, offset + i * ENTRY_SIZE)
        ranges.append((start, end))
    return ranges


def verify_original(data):
    """Verify the file contains the expected original range table."""
    current = read_ranges(data, PATCH_OFFSET)
    if current != ORIGINAL_RANGES:
        # Check if already patched
        if current == PATCHED_RANGES:
            return "already_patched"
        # Show what we found
        print("WARNING: Range table doesn't match expected original values.")
        print("  Expected:")
        for i, (s, e) in enumerate(ORIGINAL_RANGES):
            print(f"    Type {i:2d}: U+{s:04X}-U+{e:04X}")
        print("  Found:")
        for i, (s, e) in enumerate(current):
            print(f"    Type {i:2d}: U+{s:04X}-U+{e:04X}")
        return "mismatch"
    return "ok"


def patch_file(input_path, output_path):
    """Apply CJK patch to FPilot.exe."""
    # Read input
    with open(input_path, 'rb') as f:
        data = bytearray(f.read())

    # Size check
    if len(data) != EXPECTED_SIZE:
        print(f"ERROR: Unexpected file size {len(data)} (expected {EXPECTED_SIZE})")
        print("       This patch is for FilePilot v0.7.0 only.")
        return False

    # Verify original table
    status = verify_original(data)
    if status == "already_patched":
        print("File is already patched with CJK ranges. Nothing to do.")
        return True
    if status == "mismatch":
        resp = input("Continue anyway? [y/N] ").strip().lower()
        if resp != 'y':
            print("Aborted.")
            return False

    # Apply patch
    for i, (start, end) in enumerate(PATCHED_RANGES):
        struct.pack_into('<II', data, PATCH_OFFSET + i * ENTRY_SIZE, start, end)

    # Write output
    with open(output_path, 'wb') as f:
        f.write(data)

    # Summary
    orig_count = count_chars(ORIGINAL_RANGES)
    patched_count = count_chars(PATCHED_RANGES)
    print(f"Patch applied successfully!")
    print(f"  Input:  {input_path}")
    print(f"  Output: {output_path}")
    print(f"  Characters: {orig_count:,} → {patched_count:,}")
    print(f"  Memory impact: ~18 MB → ~50 MB")
    print()
    print("Next steps:")
    print("  1. Close FilePilot")
    print("  2. Backup original FPilot.exe")
    print("  3. Replace with patched exe")
    print('  4. Set "FontName": "simhei.ttf" in FPilot-Config.json')
    print("  5. Restart FilePilot")
    return True


def main():
    if len(sys.argv) < 2:
        print(__doc__.strip())
        print()
        print("Range table comparison:")
        print(f"  Original: {count_chars(ORIGINAL_RANGES):,} characters (Latin/Cyrillic)")
        print(f"  Patched:  {count_chars(PATCHED_RANGES):,} characters (+CJK/Japanese)")
        sys.exit(1)

    input_path = sys.argv[1]
    if not os.path.isfile(input_path):
        print(f"ERROR: File not found: {input_path}")
        sys.exit(1)

    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_cjk{ext}"

    if os.path.abspath(input_path) == os.path.abspath(output_path):
        print("ERROR: Input and output paths are the same.")
        print("       Specify a different output path.")
        sys.exit(1)

    success = patch_file(input_path, output_path)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
