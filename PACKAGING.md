# Packaging notes

Debian packaging uses debhelper, the standard Debian helper framework.

Arch packaging uses PKGBUILD/makepkg.

RPM packaging uses a noarch spec because the current implementation is Python-based.

Flatpak must use verified source checksums before release. The manifest deliberately leaves the checksum placeholder rather than pretending an unverified hash is trustworthy.

Package maintainers should build in clean environments and run the platform's lint/review tooling before publication.
