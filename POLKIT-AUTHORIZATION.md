# D-Bus caller authorization

v2.8 formalizes privileged action IDs in the polkit policy and adds a
conservative authorization-check API.

Privileged networking must be exposed through the host service rather than
the Flatpak GUI. The policy uses authentication-required defaults for network
and client management.

Before production release, the D-Bus service should bind the actual incoming
D-Bus sender unique name to its Unix credentials and pass those credentials
to `org.freedesktop.PolicyKit1.Authority.CheckAuthorization`; a process PID
must never be inferred from an untrusted client argument.
