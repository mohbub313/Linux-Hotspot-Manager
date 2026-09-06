# Security and Release Notes

## Privilege boundary

The GUI is intended to run unprivileged. Privileged networking is delegated to a root host service over system D-Bus.

## D-Bus policy

The included policy allows the desktop client to send messages to the service name. This is a functional baseline, not a final least-privilege policy. Before public production release, every privileged method should be mapped to an explicit polkit action and the D-Bus policy should be reduced accordingly.

## Network safety

- Privileged subprocesses are executed with argument arrays rather than `shell=True`.
- Interface, MAC, IPv4 and domain inputs are validated.
- User passwords use salted scrypt hashes for stored guest credentials.
- The project deliberately does not perform HTTPS interception.

## Validation status

Hardware-dependent behavior still needs testing on the target Wi-Fi adapters and distributions. Package reproducibility and Flatpak dependency checksum verification should be completed in a clean build environment.
