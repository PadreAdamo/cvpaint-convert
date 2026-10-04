# cvpaint-convert

Convert JPG, PNG, and other common image formats into ColecoVision CV Paint / PATCOL `.PC` image files.

The primary use case is preparing box art and screenshots for the AtariMax ColecoVision Ultimate SD cartridge, but the generated files are standard raw CV Paint-style TMS9918 Graphics II images and may be useful in other ColecoVision workflows.

## Features

- Converts JPG, PNG, BMP, GIF, and WebP images
- Outputs AtariMax-compatible `.PC` files
- Supports batch conversion
- Generates optional PNG previews
- Resizes artwork to the ColecoVision's 256×192 display
- Preserves aspect ratio with `contain` mode
- Uses an optimized per-image TMS9918 palette
- Respects the TMS9918 Graphics II two-color-per-8-pixel-row restriction

## Requirements

- Python 3
- Pillow

Install Pillow with:

```bash
python3 -m pip install Pillow
```

On distributions that use externally managed Python environments, such as openSUSE Tumbleweed, install Pillow through your package manager or use a virtual environment.

Example for openSUSE:

```bash
sudo zypper install python313-Pillow
```

## Usage

### Convert a single image

```bash
python3 cvpaint-convert.py input.jpg output.pc
```

### Convert an entire directory

```bash
python3 cvpaint-convert.py \
  ./images \
  ./boxes-pc \
  --preview-dir ./boxes-previews \
  --fit contain \
  --global-colors 8
```

The output directory will contain `.pc` files with the same base filenames as the source images.

Example:

```text
images/
├── antarctic-adventure-1984.jpg
├── alphabet-zoo-1984.jpg
└── amazing-bumpman-1986.jpg
```

becomes:

```text
boxes-pc/
├── antarctic-adventure-1984.pc
├── alphabet-zoo-1984.pc
└── amazing-bumpman-1986.pc
```

## Recommended AtariMax Layout

For AtariMax Ultimate SD box art:

```text
COLECO/
├── A-D/
│   ├── antarctic-adventure-1984.rom
│   └── alphabet-zoo-1984.rom
├── E-H/
├── I-L/
├── M-P/
├── Q-T/
├── U-Z/
├── Boxes/
│   ├── antarctic-adventure-1984.pc
│   └── alphabet-zoo-1984.pc
├── Images/
├── Manuals/
└── cvsdos.sto
```

The `.pc` filename must match the ROM filename exactly, excluding the extension.

Example:

```text
antarctic-adventure-1984.rom
antarctic-adventure-1984.pc
```

On the AtariMax menu, highlight the ROM and press `7` to display box art.

## Recommended Settings

For box art, the current recommended settings are:

```bash
python3 cvpaint-convert.py \
  ./images \
  ./boxes-pc \
  --preview-dir ./boxes-previews \
  --fit contain \
  --global-colors 8
```

### `--fit`

Available modes:

```text
contain
crop
stretch
```

`contain` is recommended for box art because it preserves the full cover and adds black borders where necessary.

### `--global-colors`

Controls how many TMS9918 colors are available to the image.

Recommended:

```text
8
```

Higher values may preserve more colors, but can also introduce more visually inconsistent color changes between small image regions.

## Preview Files

Use:

```bash
--preview-dir ./boxes-previews
```

to generate PNG previews of the converted `.PC` files.

This is useful for reviewing image quality before copying files to an SD card.

## `.PC` File Format

The generated files are raw 12,288-byte ColecoVision Graphics II images.

Layout:

```text
Offset 0x0000 - 0x17FF
6144 bytes of TMS9918 pattern data

Offset 0x1800 - 0x2FFF
6144 bytes of TMS9918 color data
```

Total:

```text
12288 bytes
```

There is no file header.

Each 8-pixel horizontal segment contains:

- one pattern byte
- one color byte
- one foreground color
- one background color

This reflects the hardware limitations of the TMS9918A Graphics II mode used by the ColecoVision.

## Image Quality

Modern box art contains far more color and detail than the ColecoVision display hardware can represent.

The TMS9918 Graphics II mode is limited to:

- 256×192 resolution
- a fixed 16-color palette
- only two colors per 8-pixel horizontal segment

Because of this, some covers convert better than others.

Simple artwork, logos, and high-contrast covers generally work best.

Dark paintings, gradients, detailed illustrations, and photographic artwork may show:

- color substitution
- block-level color changes
- reduced detail
- simplified gradients

This is expected behavior rather than a file-format error.

## Project Status

The converter currently produces valid `.PC` files that have been tested successfully on real AtariMax ColecoVision Ultimate SD hardware.

The conversion algorithm is still open to improvement, especially around palette selection and difficult source artwork.

Contributions and experimentation are welcome.

## License

MIT License

Copyright (c) 2026 Adam J. Girardo
