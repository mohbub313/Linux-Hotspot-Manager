#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
OUT="${1:-$ROOT/dist}"
mkdir -p "$OUT"
command -v flatpak-builder >/dev/null 2>&1 || { echo "flatpak-builder required" >&2; exit 2; }
flatpak-builder --force-clean --repo="$OUT/repo" "$OUT/build-dir" "$ROOT/com.shazid.LinuxHotspotManager.yml"
flatpak build-bundle "$OUT/repo" "$OUT/Linux-Hotspot-Manager-3.2.0.flatpak" com.shazid.LinuxHotspotManager 3.2.0
