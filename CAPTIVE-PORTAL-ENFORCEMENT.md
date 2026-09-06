# Captive portal session enforcement

v2.7 adds actual per-client portal session state.

Authenticated sessions are stored in `/var/lib/linux-hotspot-manager/portal-sessions.json`.
The privileged service creates a cryptographically random session token and
installs/removes MAC-scoped nftables forward rules.

Unauthenticated clients are blocked from forwarded traffic. Authentication
temporarily removes the managed portal block for that MAC until the session
expires or is revoked.

The design does not intercept HTTPS and does not forge certificates. A real
deployment should additionally provide DHCP/DNS captive-portal discovery and
carefully test the rule ordering with NAT, quota, and client-accounting rules.
