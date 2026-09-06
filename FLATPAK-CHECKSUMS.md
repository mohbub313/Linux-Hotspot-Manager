# Flatpak source checksum policy

The release pipeline must never ship a fabricated checksum.

For each network source in the Flatpak manifest:

1. Resolve the exact immutable source revision.
2. Download the source archive through a trusted build environment.
3. Calculate its SHA-256 digest.
4. Put the full 64-character digest in the manifest.
5. Re-run the verification script and Flatpak builder before release.

If a dependency is not yet verified, the release checklist must keep it marked
pending rather than silently substituting a fake digest.
