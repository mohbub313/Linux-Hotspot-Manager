#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
makepkg -f packaging/arch/PKGBUILD
