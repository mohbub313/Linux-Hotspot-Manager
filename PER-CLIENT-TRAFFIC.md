# Per-client traffic accounting

v2.2 adds nftables counters for hotspot clients.

- Upload: packets entering the hotspot interface from the client's MAC.
- Download: packets leaving the hotspot interface to the client's MAC.
- Counters are read from the Linux forwarding path.
- The GUI can calculate per-client rates from counter deltas.
- `ResetClientTraffic(interface, mac)` resets counters without deleting rules.

The exact meaning depends on the hotspot routing/bridge topology. Real forwarded
traffic should be tested on the target hardware before treating counters as
billing-grade measurements.
