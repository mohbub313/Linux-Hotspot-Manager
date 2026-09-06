#!/bin/sh
set -eu
echo "=== Linux Hotspot Manager hardware smoke test ==="
iw dev
echo
echo "--- NetworkManager ---"
nmcli -t -f DEVICE,TYPE,STATE dev
echo
echo "--- Wi-Fi AP capability ---"
if command -v iw >/dev/null 2>&1; then
  iw list | sed -n '/Supported interface modes:/,/Band /p' | head -80
fi
echo
echo "Verify manually: AP mode, 2.4 GHz, 5 GHz, WPA2-PSK, WPA3-SAE (if supported),"
echo "client association, DHCP, DNS filtering, NAT, quotas, portal login, and recovery."
