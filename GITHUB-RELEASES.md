# GitHub releases

Push a version tag such as `v3.2.0`. The GitHub Actions release workflow builds
and publishes:

- Debian `.deb`
- Arch Linux `.pkg.tar.*`
- Fedora/RHEL-compatible `.rpm`
- Flatpak `.flatpak`

GitHub Releases are the public download surface for binary assets; the source
repository remains the canonical open-source codebase.
