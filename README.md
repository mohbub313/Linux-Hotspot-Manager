# Linux Hotspot Manager v4.1.0 GUI

A robust graphical user interface and background service manager designed to deploy secure public Wi-Fi access points and captive portals on Linux systems. 

## Features
* **Captive Portal Enforcement:** Secure user isolation and customizable landing authentication pages.
* **Bandwidth & Quota Management:** Per-client real-time traffic tracking and data limits.
* **Advanced DNS Filtering:** Domain-level filtering and access restriction capabilities.
* **Polkit Authorization:** Secure root-level operations integrated directly into user space.
* **Multiple Packaging Options:** Supports Debian (`.deb`), Red Hat (`.rpm`), Arch Linux (`PKGBUILD`), and Flatpak builds.

## Installation

### Method 1: Using the Pre-compiled Debian Package (Recommended)
Download the latest `.deb` release installer from the **Releases** tab on the right side of this page. Once downloaded, install it using your terminal:

```bash
sudo apt update
sudo apt install ./linux-hotspot-manager_4.1.0_all.deb
```

### Method 2: Manual Installation from Source
If you prefer to deploy the application manually directly from the source code, run the automated deployment script provided in the root directory:

```bash
sudo chmod +x install-host.sh
sudo ./install-host.sh
```

## Running the Application
Once the package deployment finishes, launch the graphical panel from your system desktop application menu or fire up the background automation component manually via systemd:

```bash
sudo systemctl start linux-hotspot-manager.service
```

## Uninstallation
To completely purge the software configuration components and clean the active system daemon files, run:
```bash
sudo chmod +x uninstall-host.sh
sudo ./uninstall-host.sh
```
