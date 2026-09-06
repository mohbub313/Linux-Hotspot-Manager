# Architecture

## Trust boundary

The GUI is unprivileged. It communicates with one narrowly scoped system D-Bus service.

The host service validates arguments and performs privileged actions through explicit subprocess argument arrays.

## State

SQLite stores:
- hotspot profiles
- users
- sessions
- usage snapshots
- firewall/domain rules
- portal configuration

Runtime state is under `/var/lib/linux-hotspot-manager/`.

## Networking

NetworkManager owns the connection/AP profile. nftables owns filtering and accounting. tc owns per-client shaping. dnsmasq provides DHCP/DNS where configured.

No HTTPS interception is performed.
