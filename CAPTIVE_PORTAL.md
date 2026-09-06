# Captive portal

The portal is a local HTTP service used for guest login and terms acceptance.

Flow:
1. Client receives DHCP configuration.
2. DNS can resolve portal hostname to the hotspot gateway.
3. HTTP captive checks can be redirected to the portal.
4. User accepts terms or authenticates.
5. The host service records a session and can apply quotas.

HTTPS traffic is not decrypted or transparently MITM'd. Modern browsers may show certificate/privacy errors if an implementation attempts HTTPS interception, so this project intentionally avoids it.
