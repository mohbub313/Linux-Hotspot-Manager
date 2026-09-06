#!/bin/sh
set -eu
PREFIX=${PREFIX:-/usr}
UNITDIR=${UNITDIR:-/etc/systemd/system}
systemctl disable --now linux-hotspot-manager-dnsmasq.service 2>/dev/null || true
systemctl disable --now linux-hotspot-manager-portal.service 2>/dev/null || true
systemctl disable --now linux-hotspot-manager.service 2>/dev/null || true
rm -f "$UNITDIR/linux-hotspot-manager-dnsmasq.service" \
      "$UNITDIR/linux-hotspot-manager-portal.service" \
      "$UNITDIR/linux-hotspot-manager.service"
rm -f "$PREFIX/bin/linux-hotspot-manager-service"
systemctl daemon-reload
echo "Linux Hotspot Manager host components removed."
