# Linux Hotspot Manager 3.2.0-8

This source snapshot matches the Parrot/Debian test package used during the v3.2.0-8 troubleshooting cycle.

## Included runtime fixes

- GTK4/libadwaita GUI uses `dbus_next.glib.MessageBus`.
- GUI calls D-Bus proxy methods using the documented snake_case convention (for example `GetStatus` -> `call_get_status_sync`).
- The host D-Bus service uses explicit D-Bus type annotations on service methods.
- systemd uses `Type=dbus` and `BusName=com.shazid.LinuxHotspotManager` so service readiness is tied to D-Bus name acquisition.
- The system D-Bus policy file permits the GUI to address the service name; privileged authorization should still be tightened and audited before broad production deployment.
- Runtime state is stored under `/var/lib/linux-hotspot-manager`.

## Verification performed

- Python bytecode compilation of GUI, host service and portal server.
- Static inspection of D-Bus method annotations.
- Debian package contents inspection.

## Important limitation

This release is production-oriented, not a claim of universal production certification. Wi-Fi AP support, WPA3, channel/band behavior, NetworkManager versions, drivers, kernel versions and distro packaging vary. Real hardware and clean-build validation remain required before a public stable release.
