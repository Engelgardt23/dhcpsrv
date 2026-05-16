# Security policy

Thanks for taking the time to look at this. Even small tools can introduce real
risk — this one binds a privileged UDP port and reconfigures a network adapter
on the host — so vulnerability reports are very welcome.

## Supported versions

Only the latest tagged release on GitHub is supported. Older versions will not
get fixes; please upgrade first.

## How to report a vulnerability

**Please do not open a public issue** for security-sensitive findings. Use one
of these private channels instead:

1. **Preferred:** GitHub's private security advisories.
   Go to the [Security tab](../../security/advisories/new) of this repo and
   click "Report a vulnerability". GitHub will route it to me privately.
2. **Email:** `engelgardt2024@gmail.com` with the subject prefix `[security]`.

Please include:
- The version of `dhcpsrv` you tested (output of the startup banner is enough).
- Steps to reproduce, ideally with a packet capture or a short script.
- An assessment of impact (LAN-only? remote? admin needed? etc.).

## What to expect

- Acknowledgement within **3 business days**.
- A first technical reply within **7 business days**.
- A fix and a public advisory once the issue is resolved. Reporters are
  credited unless they prefer to stay anonymous.

## Out of scope

- DoS by flooding the DHCP server on the local link (it's a small tool meant
  for direct-cable / single-switch use; flooding your own laptop is your call).
- Behavior when run **without** administrator privileges (the tool refuses to
  start in that case anyway).
- Issues that require the attacker to already control the user's machine.
