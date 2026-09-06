# User Guide

## Launch

After installation, launch **Linux Hotspot Manager** from the desktop application menu or run:

```bash
linux-hotspot-manager
```

## Dashboard

The Dashboard checks the privileged host service over the system D-Bus. Use **Refresh** to re-read service status. **Start Hotspot** and **Stop Hotspot** invoke the host service lifecycle methods.

The current demonstration GUI uses baseline hotspot values. A production UI should expose validated profile editing before enabling unattended deployment.

## Troubleshooting

Check the service:

```bash
sudo systemctl status linux-hotspot-manager --no-pager -l
```

View recent logs:

```bash
sudo journalctl -u linux-hotspot-manager -n 100 --no-pager
```

Check D-Bus introspection:

```bash
gdbus introspect --system --dest com.shazid.LinuxHotspotManager --object-path /com/shazid/LinuxHotspotManager
```

Check NetworkManager:

```bash
nmcli device status
nmcli general status
```

If the GUI reports a D-Bus proxy method error, verify that the D-Bus member is exposed and that the Python proxy call uses snake_case as documented by dbus-next.
