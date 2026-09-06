# NetworkManager D-Bus integration

v2.3 uses NetworkManager's native D-Bus API for device discovery and Wi-Fi AP
connection-profile creation/activation. `AddConnection2` is used with a
persistent connection profile, WPA-PSK security, IPv4 shared mode, and
disabled IPv6 for the hotspot profile.

A legacy nmcli implementation remains elsewhere in the service for compatibility
with older deployments; the new API is available to the GUI/service path.

NetworkManager exposes connection profiles through
`org.freedesktop.NetworkManager.Settings` and its D-Bus API supports
`AddConnection2` for persistent or in-memory profiles.
