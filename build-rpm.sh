#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
OUT="${1:-$ROOT/dist}"
mkdir -p "$OUT"
command -v rpmbuild >/dev/null 2>&1 || { echo "rpmbuild required" >&2; exit 2; }
TOP=$(mktemp -d)
mkdir -p "$TOP"/{BUILD,RPMS,SOURCES,SPECS,SRPMS}
tar czf "$TOP/SOURCES/linux-hotspot-manager-3.2.0.tar.gz" -C "$ROOT" .
cp "$ROOT/packaging/rpm/linux-hotspot-manager.spec" "$TOP/SPECS/"
sed -i 's/^Version:.*/Version: 3.2.0/' "$TOP/SPECS/linux-hotspot-manager.spec"
rpmbuild --define "_topdir $TOP" -ba "$TOP/SPECS/linux-hotspot-manager.spec"
find "$TOP/RPMS" -type f -name '*.rpm' -exec cp {} "$OUT/" \;
rm -rf "$TOP"
