#!/bin/sh
set -eu
MANIFEST="${1:-com.shazid.LinuxHotspotManager.yml}"
[ -f "$MANIFEST" ] || { echo "Manifest not found: $MANIFEST" >&2; exit 1; }

python3 - "$MANIFEST" <<'PY'
import sys, re, pathlib
p=pathlib.Path(sys.argv[1])
s=p.read_text()
placeholders=re.findall(r'(?:sha256|sha256sum)\s*[:=]\s*["' + "'" + r']?([0-9a-fA-F]{8,})',s)
bad=[x for x in placeholders if len(x)!=64 or x == "0"*64 or "PLACEHOLDER" in x.upper()]
if bad:
    print("Unverified/placeholder checksums detected:", ", ".join(bad), file=sys.stderr)
    raise SystemExit(2)
print("All manifest checksum fields look fully specified.")
PY
