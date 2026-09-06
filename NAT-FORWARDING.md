# NAT and forwarding topology

v2.4 adds an explicit hotspot-to-uplink forwarding topology.

`ConfigureNatForwarding(hotspot_interface, uplink_interface)`:

1. Creates the managed nftables inet table/chains.
2. Accepts client -> uplink forwarding.
3. Accepts established/related uplink -> client forwarding.
4. Applies masquerade on traffic leaving the selected uplink.
5. Enables IPv4 forwarding.

Rules are tagged with `lhm:nat:` so they can be removed without deleting
unrelated nftables rules.

`CleanupNatForwarding()` removes only the tagged rules and can restore the
previous IPv4 forwarding state.

The service deliberately does not flush the host firewall. Existing firewall
configuration remains outside the application's managed rule set.
