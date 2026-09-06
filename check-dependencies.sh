#!/bin/sh
set -eu
for c in python3 nmcli nft dnsmasq systemctl pkcheck; do
  command -v "$c" >/dev/null 2>&1 || { echo "Missing dependency: $c" >&2; exit 1; }
done
python3 - <<'PY'
import importlib.util
try:
    import dbus_next
except Exception as e:
    raise SystemExit("Missing Python dependency: dbus-next")
print("Dependency check OK")
PY
