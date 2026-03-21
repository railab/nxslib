# Change Log

## 0.9.0 (23/02/2023)

- Initial release

## 0.9.1 (04/10/2023)

- intf: add support for RTT interface
- disable all enabled channels when disconnecting
- improve interfaces drop_all logic

## 1.0.0 (18/03/2026)

- breaking release!
- small improvements for RTT interface
- add interfaces to get nxscope state:
  * enabled channels
  * channel dividers
  * stream bitrate
  * stream status
  * stream capabilities
- fix busy loop for serial that causes 100% CPU usage on host simulator
- support divider for dummy dev
- various small fixes and improvements
- use context manager to handle objects cleanup
- support for UDP transport
- support for stream data as numpy data to improve performance
- make NumPy stream decode mode the default in `NxscopeHandler` and
  deprecate legacy per-sample stream decode mode
- add support for user defined protocol extensions
- improve parse/decoding logic
- add more channels to dummy dev

## 1.0.1 (21/03/2026)

- fix serial device cleanup
- add more channels to dummy dev
