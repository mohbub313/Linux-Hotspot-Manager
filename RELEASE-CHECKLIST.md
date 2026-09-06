# Release checklist

- [ ] Run source tests.
- [ ] Build Debian package in a clean Debian/Ubuntu environment.
- [ ] Build Arch package with makepkg and run namcap.
- [ ] Build RPM and run rpmlint.
- [ ] Build Flatpak with verified source checksums.
- [ ] Test NetworkManager AP mode on supported adapters.
- [ ] Verify polkit authorization as a non-admin user.
- [ ] Verify nftables cleanup on stop/uninstall.
- [ ] Verify tc cleanup on client removal/stop.
- [ ] Verify captive portal does not intercept HTTPS.
- [ ] Verify passwords never appear in logs.
- [ ] Tag the Git commit and publish signed checksums.
