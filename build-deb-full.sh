#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
OUT="${1:-$ROOT/dist}"
VER=$(cat "$ROOT/VERSION")
mkdir -p "$OUT"
command -v dpkg-deb >/dev/null 2>&1 || { echo "dpkg-deb is required" >&2; exit 2; }
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/DEBIAN" \
  "$TMP/usr/bin" "$TMP/usr/lib/linux-hotspot-manager" \
  "$TMP/usr/share/applications" "$TMP/usr/share/icons/hicolor/scalable/apps" \
  "$TMP/usr/share/dbus-1/system-services" "$TMP/etc/dbus-1/system.d" \
  "$TMP/etc/polkit-1/actions" "$TMP/etc/linux-hotspot-manager" "$TMP/usr/share/metainfo" \
  "$TMP/usr/share/linux-hotspot-manager/lang" \
  "$TMP/lib/systemd/system" "$TMP/var/lib/linux-hotspot-manager"

# Code & Libs
cp "$ROOT/src/main.py" "$TMP/usr/lib/linux-hotspot-manager/main.py"
cp "$ROOT/src/i18n.py" "$TMP/usr/lib/linux-hotspot-manager/i18n.py"
cp "$ROOT/host/linux-hotspot-manager-service.py" "$TMP/usr/lib/linux-hotspot-manager/linux-hotspot-manager-service.py"
cp "$ROOT/portal/server.py" "$TMP/usr/lib/linux-hotspot-manager/portal-server.py"

# Translations
cp -r "$ROOT/data/lang/"* "$TMP/usr/share/linux-hotspot-manager/lang/"

# Configs & Service Files
cp "$ROOT/host/dnsmasq.conf" "$TMP/etc/linux-hotspot-manager/dnsmasq.conf"
cp "$ROOT/host/com.shazid.LinuxHotspotManager.service" "$TMP/usr/share/dbus-1/system-services/"
cp "$ROOT/dbus/com.shazid.LinuxHotspotManager.conf" "$TMP/etc/dbus-1/system.d/"
cp "$ROOT/polkit/com.shazid.LinuxHotspotManager.policy" "$TMP/etc/polkit-1/actions/"
cp "$ROOT/systemd/linux-hotspot-manager.service" "$TMP/lib/systemd/system/"
cp "$ROOT/systemd/linux-hotspot-manager-portal.service" "$TMP/lib/systemd/system/"
cp "$ROOT/systemd/linux-hotspot-manager-dnsmasq.service" "$TMP/lib/systemd/system/"

# Desktop & Icon
cp "$ROOT/data/icon.svg" "$TMP/usr/share/icons/hicolor/scalable/apps/com.shazid.LinuxHotspotManager.svg"
cp "$ROOT/data/com.shazid.LinuxHotspotManager.metainfo.xml" "$TMP/usr/share/metainfo/"
cp "$ROOT/data/com.shazid.LinuxHotspotManager.desktop" "$TMP/usr/share/applications/"

# Launcher wrapper
cat > "$TMP/usr/bin/linux-hotspot-manager" <<'LAUNCHER'
#!/bin/sh
exec /usr/bin/python3 /usr/lib/linux-hotspot-manager/main.py "$@"
LAUNCHER
chmod 755 "$TMP/usr/bin/linux-hotspot-manager"

# Control file
cat > "$TMP/DEBIAN/control" <<CONTROL
Package: linux-hotspot-manager
Version: $VER
Section: net
Priority: optional
Architecture: all
Maintainer: Linux Hotspot Manager Contributors
Depends: python3 (>= 3.11), python3-dbus-next (>= 0.2.3), python3-gi, gir1.2-gtk-4.0, gir1.2-adw-1, network-manager, nftables, dnsmasq, iproute2, dbus, polkitd, systemd
Description: Linux Wi-Fi Hotspot Manager (MyPublicWiFi Clone)
 Full-featured Wi-Fi hotspot management console for Linux with bandwidth control,
 DNS-level adblocking, P2P/torrent filtering, captive portal with vouchers,
 and real-time client traffic monitoring. Built for Parrot OS, Debian, and KDE.
CONTROL

# Pre-removal script
cat > "$TMP/DEBIAN/prerm" <<'PRERM'
#!/bin/sh
set -e
if [ "$1" = "remove" ] || [ "$1" = "deconfigure" ]; then
    systemctl stop linux-hotspot-manager.service 2>/dev/null || true
    systemctl stop linux-hotspot-manager-portal.service 2>/dev/null || true
    systemctl disable linux-hotspot-manager.service 2>/dev/null || true
fi
exit 0
PRERM
chmod 755 "$TMP/DEBIAN/prerm"

# Post-installation script
cat > "$TMP/DEBIAN/postinst" <<'POSTINST'
#!/bin/sh
set -e
mkdir -p /var/lib/linux-hotspot-manager
chmod 750 /var/lib/linux-hotspot-manager

if ! id -u linux-hotspot-manager >/dev/null 2>&1; then
    useradd -r -s /usr/sbin/nologin -d /var/lib/linux-hotspot-manager linux-hotspot-manager || true
fi

systemctl daemon-reload || true
systemctl reload dbus.service 2>/dev/null || true
systemctl enable linux-hotspot-manager.service || true
systemctl restart linux-hotspot-manager.service || true
exit 0
POSTINST
chmod 755 "$TMP/DEBIAN/postinst"

dpkg-deb --build "$TMP" "$OUT/linux-hotspot-manager_${VER}_all.deb" >/dev/null
echo "$OUT/linux-hotspot-manager_${VER}_all.deb"
