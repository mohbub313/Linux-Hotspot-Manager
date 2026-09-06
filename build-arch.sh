#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
OUT="${1:-$ROOT/dist}"
mkdir -p "$OUT"
command -v makepkg >/dev/null 2>&1 || { echo "makepkg required" >&2; exit 2; }
TMP=$(mktemp -d)
cp "$ROOT/packaging/arch/PKGBUILD" "$TMP/PKGBUILD"
sed -i 's/^pkgver=.*/pkgver=3.2.0/' "$TMP/PKGBUILD"
cd "$TMP"
makepkg --clean --force --syncdeps --noconfirm
cp ./*.pkg.tar.* "$OUT/"
rm -rf "$TMP"
