#!/bin/sh
set -eu
PREFIX=${PREFIX:-/usr}
SYSCONFDIR=${SYSCONFDIR:-/etc}
UNITDIR=${UNITDIR:-/etc/systemd/system}
PKGDIR="$SYSCONFDIR/linux-hotspot-manager"
mkdir -p "$PKGDIR" "$UNITDIR"
cp -f "$(dirname "$0")/../host/dnsmasq.conf" "$PKGDIR/dnsmasq.conf"
cp -f "$(dirname "$0")/../host/linux-hotspot-manager-service.py" "$PREFIX/bin/linux-hotspot-manager-service"
chmod 0755 "$PREFIX/bin/linux-hotspot-manager-service"
if [ -f "$(dirname "$0")/../systemd/linux-hotspot-manager-dnsmasq.service" ]; then
  cp -f "$(dirname "$0")/../systemd/linux-hotspot-manager-dnsmasq.service" "$UNITDIR/"
fi
if [ -f "$(dirname "$0")/../systemd/linux-hotspot-manager.service" ]; then
  cp -f "$(dirname "$0")/../systemd/linux-hotspot-manager.service" "$UNITDIR/"
fi
if [ -f "$(dirname "$0")/../systemd/linux-hotspot-manager-portal.service" ]; then
  cp -f "$(dirname "$0")/../systemd/linux-hotspot-manager-portal.service" "$UNITDIR/"
fi
systemctl daemon-reload
echo "Linux Hotspot Manager host components installed."
