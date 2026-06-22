# FilePilot CJK Patch — Reverse Engineering Analysis

Detailed technical analysis of the font rendering pipeline and patch development.

## 1. Program Identification

- **Binary**: FPilot.exe v0.7.0, PE32+ x86-64, 2,184,784 bytes
- **Compiler**: MSVC 14.32 (Visual Studio 2022)
- **Rendering**: OpenGL 4.5 with shader-based text rendering (`sampler2DArray`)
- **Font stack**: GDI (`CreateFontW`, `TextOutW`) + DirectWrite (`DWriteCreateFactory`)
- **No packing/obfuscation**: Plain MSVC binary

## 2. Font Rendering Pipeline

```
FPilot-Config.json
  → FontName: "simhei.ttf"
  → SHGetKnownFolderPath(FONTS) → C:\Windows\Fonts\simhei.ttf
  → DWriteCreateFactory → CreateFontFileReference → CreateFontFace
  → GetGdiInterop → CreateBitmapRenderTarget
  → Win__FontCreateAtlas (RVA 0x1bda40)
      → Read Unicode range table (11 entries)
      → For each range [start..end]:
          → GetGlyphIndices → glyph index array
          → DrawGlyphRun → render to DIB section
          → Copy pixels to OpenGL texture layer
      → Upload texture array to GPU
  → OpenGL shader: sampler2DArray → render text
```

## 3. Root Cause

The program maintains a **Unicode range table** at file offset `0x1e5610` (virtual address `DAT_1401e7010`, `.data` section). This table defines 11 "types" — each type covers a Unicode range and gets its own texture atlas layer.

The original table only covers Latin and Cyrillic ranges (types 0-10, ~1,128 characters total). CJK characters (U+4E00-U+9FFF) are not in any type's range → no glyphs rendered → display as `?`.

## 4. Patch Development

### 4.1 Table Structure

Each entry is 8 bytes: `uint32_t start_codepoint` + `uint32_t end_codepoint` (little-endian). 11 entries = 88 bytes total.

The font configuration structure has two arrays of 11 entries each (at offsets `0x270` and `0x2C8`), so the type count is **hardcoded to 11** — cannot be extended without restructuring the binary.

### 4.2 Experiments

| # | Approach | Result | Notes |
|---|----------|--------|-------|
| 1 | Replace "Segoe UI" → "SimHei" in binary | ❌ No effect | CreateFontW path only used for drag-drop window, not main rendering |
| 2 | Type 0: 0x0000-0xFFFF (full BMP) | ❌ Crash | 65,536 chars → atlas too large, VirtualAlloc fails |
| 3 | Types 4-9: 6 CJK sub-ranges | ✅ Works | 152 MB memory — too high |
| 4 | Type 0: 0x4E00-0x9FFF only | ❌ Blank | Single type too large, atlas creation fails |
| 5 | Types 4-5: 2 CJK ranges | ❌ Blank | Fewer than 4 CJK types → atlas not created |
| 6 | Type 0: 0x0020-0x9FFF | ✅ Works | 288 MB — type 0 uses largest font size |
| 7 | Types 4-8: 5 CJK ranges | ✅ Works | 98 MB — good balance |
| 8 | Types 4-8 + type 9 CJK punctuation | ✅ Works | 100 MB |
| 9 | Types 4-8 + type 9 Japanese + type 10 fullwidth | ✅ Works | 50 MB — best CJK-only |
| 10 | Merged Latin + Korean syllables | ❌ Atlas fail | Korean syllables (11,184 chars) cause atlas creation failure |

### 4.3 Key Findings

1. **Type count locked to 11**: The font config structure stores two arrays of 11 entries at adjacent offsets. Extending one overwrites the other.

2. **Minimum 4 CJK types needed**: With fewer than 4 types covering CJK ranges, the atlas creation silently fails (returns empty atlas). Likely related to atlas size calculation — the allocator may reject configurations where a single texture layer would be too large.

3. **Type 0 uses the largest font size**: Other types use offset/reduced sizes. Therefore, putting CJK in type 0 wastes the most memory.

4. **Korean Hangul syllables break atlas**: U+AC00-D7AF (11,184 chars) causes atlas creation to fail even when split across multiple types. This appears to be a hard limit in the atlas allocator — possibly a maximum texture dimension or total pixel count issue.

5. **On-demand rendering not feasible**: The shader uses `sampler2DArray` (fixed layer count), the render function is 980 lines with deep coupling, and there's no code cave for injection.

## 5. Final Patch

The stable patch replaces types 1-10 while keeping type 0 unchanged:

| Type | Original | Patched | Characters |
|------|----------|---------|------------|
| 0 | Basic Latin | *(unchanged)* | 96 |
| 1 | Latin-1 Supplement | *(unchanged)* | 128 |
| 2 | Latin Extended-A | *(unchanged)* | 128 |
| 3 | Latin Extended-B | *(unchanged)* | 208 |
| 4-8 | Greek/Cyrillic | CJK Ideographs (U+4E00-9FFF) | 20,992 |
| 9 | Cyrillic Ext-C | CJK Symbols + Kana (U+3000-30FF) | 256 |
| 10 | Combining Diacritical | Fullwidth Forms (U+FF00-FFEF) | 240 |

**Total: 22,048 characters** (was 1,128). Memory: ~50 MB (was ~18 MB).

## 6. Key Function Addresses

| Function | RVA | Description |
|----------|-----|-------------|
| Win__FontCreateAtlas | `0x1bda40` | Atlas creation core (325 lines) |
| Win_FontCreateAtlasFromFile | `0x1be350` | DWrite font file loading |
| Win_FontCreateAtlasFromBytes | `0x1be420` | DWrite font bytes loading |
| Atlas init entry | `0x1a7cd0` | Decides file vs bytes loading |
| Font config | `0xc7db0` | Allocates atlas structure, reads range table |
| Font config caller | `0x125580` | Type loop (0-10), calls font config for each |
| Main render function | `0x1923a0` | File list rendering (980 lines) |
| UTF-8→UTF-16 conversion | `0x187f00` | Text encoding conversion |

### Data References

| Address | Content |
|---------|---------|
| `0x1e5610` (file) | Unicode range table (patch target) |
| `0x1d2958` (file) | `L"Segoe UI"` string (CreateFontW, drag window only) |
| `0x1cd620` (file) | `"segoeui.ttf"` string (default config font name) |

## 7. Tools Used

- **Ghidra 11.3.2** — Decompilation and static analysis
- **JDK 21** — Required by Ghidra
- **Python 3.11** — Binary analysis scripts, runtime memory scanning
- **x64dbg** — Runtime debugging (memory scan verification)
- **pefile** — PE structure analysis
