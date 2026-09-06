# Real-time traffic statistics

v2.1 adds a host-side `GetTrafficStats(interface)` D-Bus API.

It reads Linux kernel interface byte counters from:

`/sys/class/net/<interface>/statistics/rx_bytes`

`/sys/class/net/<interface>/statistics/tx_bytes`

The GUI polls once per second and calculates instantaneous upload/download rates from counter deltas.

This is interface-level traffic, not yet per-client accounting. Per-client accounting will be implemented separately using dedicated nftables counters/sets in a later step.

The GUI never reads `/sys` directly from the Flatpak.
