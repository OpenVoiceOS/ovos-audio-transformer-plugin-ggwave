# Pre-release quirks

Behavior changes since the last stable release, newest first. This file is
reset at each stable release; entries that remove or deprecate behavior
become the deprecation ledger for the next semver cycle.

## 1.0.0a1

- **Behavior change, not backward-compatible by default**: once the ggwave
  listener is enabled over the bus with `ovos.ggwave.enable`, it now
  auto-disables itself after `listen_timeout` seconds (default `300`, five
  minutes). Before this release, an enable stayed in effect indefinitely.
  The listener is a data-over-sound channel that can trigger opcodes such
  as `BUS:`, `PIP:`, and `GHS:` (install a skill from a GitHub URL), so an
  enable left running (forgotten, or triggered once for a legitimate
  reason) was exploitable to anyone in earshot for as long as it stayed on.
  A deployment that relies on the listener staying enabled indefinitely once
  turned on needs to opt out explicitly: set `listen_timeout` to `0` or a
  negative number in config. `start_enabled: true` (always-on from boot) is
  unaffected either way, since it is treated as an explicit operator
  decision and never arms the timer.
