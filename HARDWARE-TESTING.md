# Hardware testing matrix

Before calling a release production-ready, test on real Wi-Fi adapters/drivers:

- 2.4 GHz AP mode
- 5 GHz AP mode
- WPA2-PSK
- WPA3-SAE when supported by NetworkManager + driver
- multiple simultaneous clients
- DHCP/DNS/NAT
- DNS filtering and DNS bypass behavior
- upload/download shaping
- per-client accounting
- quota block/unblock
- captive portal login/session expiry
- service restart and host reboot recovery

The application must report unsupported combinations instead of pretending that
all chipsets provide the same AP/band/security capabilities.
