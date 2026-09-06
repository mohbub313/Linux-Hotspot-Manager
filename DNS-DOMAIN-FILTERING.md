# DNS/domain filtering

v2.5 adds actual DNS-layer domain enforcement through the managed dnsmasq
instance.

The service writes a runtime include under `/run/linux-hotspot-manager/` and
reloads the managed dnsmasq service. Blocked domains are answered with the
dnsmasq `address=/domain/` rule, while allowed upstream routing can be
configured separately.

This is DNS filtering, not HTTPS interception. Clients using their own
encrypted DNS resolver (DoH/DoT) can bypass a DNS-only filter unless the
network topology also enforces the approved DNS path. The application does
not install forged certificates or perform TLS interception.
