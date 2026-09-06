# Security design

- GUI is sandboxed.
- System D-Bus access is filtered.
- Privileged API validates MAC/IP/interface/port values.
- Passwords are stored using salted scrypt hashes.
- No passwords are written to logs.
- Firewall state is rebuilt from persistent configuration.
- User-controlled strings are passed as subprocess arguments, never concatenated into shell commands.
- Captive portal does not perform HTTPS interception.
