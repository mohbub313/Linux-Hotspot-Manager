# D-Bus API

Service name: `com.shazid.LinuxHotspotManager`

Object path: `/com/shazid/LinuxHotspotManager`

Interface: `com.shazid.LinuxHotspotManager`

## Core methods

| Method | Input | Output |
|---|---|---|
| `Ping` | none | `s` |
| `GetStatus` | none | `s` JSON |
| `StartHotspot` | `s connection`, `s password` | `s` |
| `StopHotspot` | `s connection` | `s` |
| `ListNetworkManagerDevices` | none | `s` JSON |
| `CreateAndActivateWifiAP` | `s interface`, `s ssid`, `s password`, `s band`, `u channel` | `s` JSON |
| `DeactivateNetworkManagerConnection` | `o active_path` | `b` |
| `ListInterfaces` | none | `s` JSON |
| `GetClients` | none | `s` JSON |
| `GetTrafficStats` | `s iface` | `s` JSON |

The source also contains client, firewall, domain-rule, quota, portal-session and traffic-accounting methods from the earlier production-oriented feature set.

## GUI naming

With the GLib proxy API, CamelCase D-Bus methods are converted to snake_case. For example:

```python
iface.call_get_status_sync()
iface.call_start_hotspot_sync("LinuxHotspot", "password")
```

See the dbus-next documentation for the proxy naming convention.
