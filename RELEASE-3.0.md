# v3.0 release baseline

This release consolidates the project into a deployable Linux hotspot manager
baseline with:

- NetworkManager D-Bus AP creation
- nftables NAT/forwarding and client accounting
- DNS/domain filtering
- persistent client quotas
- captive-portal session enforcement
- polkit action policy and sender-aware authorization path
- hardware smoke-test tooling
- dependency/release validation
- host install/uninstall scripts

Production certification still requires running the hardware matrix on each
target distro/kernel/Wi-Fi chipset combination. Unsupported AP bands/security
features must be detected and reported rather than assumed.
