# Installation

## Runtime dependencies

Typical host dependencies:
- NetworkManager
- nftables
- dnsmasq
- iproute2 (`tc`)
- polkit
- systemd
- Python 3 with PyGObject/dbus-next for the host service as packaged by the distribution

## Host service

```bash
sudo ./host-install.sh
sudo systemctl enable --now linux-hotspot-manager.service
```

## GUI development

Install GTK4/libadwaita/PyGObject for your distribution, then:

```bash
python3 src/main.py
```

## Flatpak

Build with a Flatpak-capable environment using:

```bash
flatpak-builder --user --install --force-clean build-dir com.shazid.LinuxHotspotManager.yml
flatpak run com.shazid.LinuxHotspotManager
```

The manifest uses a filtered system-bus policy. Flatpak documentation recommends minimum D-Bus permissions rather than unrestricted system-bus access.
