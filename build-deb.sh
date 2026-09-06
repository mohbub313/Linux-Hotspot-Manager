#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
OUT="${1:-$ROOT/dist}"
mkdir -p "$OUT"
if command -v dpkg-deb >/dev/null 2>&1; then
  TMP=$(mktemp -d)
  mkdir -p "$TMP/DEBIAN" "$TMP/usr/bin" "$TMP/etc/linux-hotspot-manager"
  cp "$ROOT/host/linux-hotspot-manager-service.py" "$TMP/usr/bin/linux-hotspot-manager-service"
  cp "$ROOT/host/dnsmasq.conf" "$TMP/etc/linux-hotspot-manager/dnsmasq.conf"
  cat > "$TMP/DEBIAN/control" <<EOF
Package: linux-hotspot-manager
Version: 3.2.0
Section: net
Priority: optional
Architecture: all
Maintainer: Linux Hotspot Manager Contributors
Depends: python3, network-manager, nftables, dnsmasq, polkitd
Description: Linux hotspot manager
 NetworkManager/nftables/dnsmasq based hotspot management application.
EOF
  dpkg-deb --build "$TMP" "$OUT/linux-hotspot-manager_3.2.0_all.deb"
  rm -rf "$TMP"
else
  echo "dpkg-deb not installed; run this script on Debian/Ubuntu or install dpkg." >&2
  exit 2
fi
