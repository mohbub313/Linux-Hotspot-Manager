# Automatic client quota enforcement

v2.6 adds persistent per-client byte quotas.

Quota usage is calculated from the nftables per-client accounting counters.
When usage reaches the configured byte quota, managed forward rules drop both
directions for that client.

The quota state is stored in `/var/lib/linux-hotspot-manager/quota-state.json`.
The host service exposes `SetClientQuota`, `GetClientQuota`,
`EnforceClientQuotas`, and `RemoveClientQuota`.

A scheduler/timer should call `EnforceClientQuotas` periodically. Counters and
quota enforcement are forwarding-path based and should be tested against the
actual hotspot topology before being used for billing.
