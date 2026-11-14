#!/usr/bin/env bash
# make-icons.sh - regenerate PNG/ICO icons from the SVG sources.
# Needs librsvg (rsvg-convert) or ImageMagick. Run after editing the SVGs:
#   ./scripts/make-icons.sh
# Sizes <= 32 use icon-small.svg (legible at tiny sizes); larger use icon.svg.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
A="$HERE/recordward/assets"
render() {  # render <svg> <size> <out>
    if command -v rsvg-convert >/dev/null 2>&1; then
        rsvg-convert -w "$2" -h "$2" "$1" -o "$3"
    elif command -v magick >/dev/null 2>&1; then
        magick -background none -density 768 "$1" -resize "${2}x${2}" "$3"
    else
        echo "need rsvg-convert or ImageMagick" >&2; exit 1
    fi
}
for s in 16 24 32; do render "$A/icon-small.svg" "$s" "$A/icon-$s.png"; done
for s in 48 64 128 256 512; do render "$A/icon.svg" "$s" "$A/icon-$s.png"; done
# Multi-size Windows .ico (also fine for other packagers).
magick "$A/icon-16.png" "$A/icon-24.png" "$A/icon-32.png" "$A/icon-48.png" \
       "$A/icon-64.png" "$A/icon-128.png" "$A/icon-256.png" "$A/icon.ico"
echo "icons written to $A"
