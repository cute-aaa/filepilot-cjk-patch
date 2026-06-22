# FilePilot CJK Patch

Fix Chinese/Japanese characters displaying as `?` in [FilePilot](https://voidstar.tools/file-pilot/) (FPilot.exe v0.7.0).

## Problem

FilePilot uses a pre-rendered font atlas (texture array) for text display. The atlas only covers Latin/Cyrillic Unicode ranges — CJK characters (Chinese, Japanese) fall outside these ranges and render as `?`.

## Solution

A binary patch that modifies the Unicode range table at file offset `0x1e5610` to include CJK character ranges. The patch is applied via a Python script — no source code modification needed.

## Quick Start

```bash
# Patch FPilot.exe → FPilot_cjk.exe
python patch_cjk.py "C:\path\to\FPilot.exe"

# Or specify output path
python patch_cjk.py "C:\path\to\FPilot.exe" "C:\path\to\FPilot_cjk.exe"
```

Then replace the original `FPilot.exe` with the patched version.

### Prerequisites

- FilePilot v0.7.0 (`FPilot.exe`, 2,184,784 bytes)
- Python 3.x
- In `FPilot-Config.json`: set `"FontName": "simhei.ttf"` (or any CJK font in `C:\Windows\Fonts\`)

## What Gets Patched

The patch modifies 11 Unicode range entries (8 bytes each) at offset `0x1e5610`:

| Type | Original Range | Patched Range | Coverage |
|------|---------------|---------------|----------|
| 0 | U+0020-007F | *(unchanged)* | Basic Latin |
| 1 | U+0080-00FF | *(unchanged)* | Latin-1 Supplement |
| 2 | U+0100-017F | *(unchanged)* | Latin Extended-A |
| 3 | U+0180-024F | *(unchanged)* | Latin Extended-B |
| 4 | U+0370-03FF | U+4E00-5FFF | CJK Ideographs (1/5) |
| 5 | U+0400-04FF | U+6000-6FFF | CJK Ideographs (2/5) |
| 6 | U+0500-052F | U+7000-7FFF | CJK Ideographs (3/5) |
| 7 | U+2DE0-2DFF | U+8000-8FFF | CJK Ideographs (4/5) |
| 8 | U+A640-A69F | U+9000-9FFF | CJK Ideographs (5/5) |
| 9 | U+1C80-1C8F | U+3000-30FF | CJK Symbols + Japanese Kana |
| 10 | U+0300-036F | U+FF00-FFEF | Fullwidth Forms |

**Total coverage**: ~22,048 characters (was ~1,128)

### Memory Impact

| Version | Memory Usage |
|---------|-------------|
| Original | ~18 MB |
| CJK patched | ~50 MB |

## Limitations

- **Korean (Hangul) not included**: Hangul syllables (U+AC00-D7AF, 11,184 chars) cause atlas creation failure even when split across multiple types. This appears to be a hard limit in FilePilot's atlas allocator.
- **Increased memory**: The larger atlas uses ~50 MB vs ~18 MB original.
- **CJK font required**: The system must have a CJK font (e.g., SimHei, Microsoft YaHei) installed in `C:\Windows\Fonts\`.

## Technical Details

See [docs/REVERSE-ENGINEERING.md](docs/REVERSE-ENGINEERING.md) for the full reverse engineering analysis.

### Font Rendering Pipeline

```
Config: FPilot-Config.json → FontName: "simhei.ttf"
  ↓
Font Load: SHGetKnownFolderPath(FONTS) → C:\Windows\Fonts\simhei.ttf
  ↓
DWrite: DWriteCreateFactory → CreateFontFileReference → CreateFontFace
  ↓
Atlas Creation: Win__FontCreateAtlas (RVA 0x1bda40)
  → Build Unicode codepoint array [start..end] from range table
  → GetGlyphIndices → get glyph indices
  → DrawGlyphRun → render each glyph to DIB bitmap
  → Copy pixels to OpenGL texture atlas
  ↓
OpenGL Render: sampler2DArray texture sampling → display
```

### Key Addresses

| Item | RVA / Offset |
|------|-------------|
| Unicode range table | `0x1e5610` (file offset, `.data` section) |
| Win__FontCreateAtlas | RVA `0x1bda40` |
| Win_FontCreateAtlasFromFile | RVA `0x1be350` |
| Font config function | RVA `0xc7db0` |
| Font config caller (type loop 0-10) | RVA `0x125580` |

## File Structure

```
filepilot-cjk-patch/
├── README.md              ← This file
├── patch_cjk.py           ← Patch script
├── test-files/            ← Test files for verification
│   ├── 中日English混合.txt
│   ├── 测试文件.txt
│   ├── テストファイル.txt
│   └── ...
└── docs/
    └── REVERSE-ENGINEERING.md  ← Detailed analysis
```

## Verification

After patching, create test files with these names and browse to them in FilePilot:

- `测试文件.txt` — Chinese
- `テストファイル.txt` — Japanese
- `中日English混合.txt` — Mixed

All characters should display correctly instead of `?`.

## Disclaimer

This project is an **independent, educational research artifact**. It is **not affiliated with, endorsed by, or sponsored by** Voidstar or the FilePilot development team.

- **No proprietary code is distributed.** The patch script is original code that modifies a specific offset in the user's own copy of FPilot.exe.
- **No modified binaries are distributed.** Users must apply the patch to their own legally obtained copy.
- This patch addresses a **display bug** (CJK characters rendering as `?`) in the free public beta, not license circumvention.

Use at your own risk. If the FilePilot developer requests removal, this repository will comply promptly.

## Credits

Reverse engineering and patch by analyzing FilePilot v0.7.0 (by Vjekoslav / Voidstar) with Ghidra 11.3.2.

## License

This patch script and documentation are provided as-is for educational purposes. FilePilot is proprietary software by [Voidstar](https://voidstar.tools/). Please support the developer by [purchasing a license](https://filepilot.tech/pricing) when it becomes available.
