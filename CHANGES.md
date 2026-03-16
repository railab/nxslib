# Change Log

## 0.9.0 (23/02/2023)

- Initial release

## 0.9.1 (04/10/2023)

- intf: add support for RTT interface
- disable all enabled channels when disconnecting
- improve interfaces drop_all logic

## 1.0.0 (18/03/2026)

- breacking release!
- small improvements for RTT interface
- add interfaces to get nxscope state:
  * enabled channels
  * channels div
  * stream bitrate
  * stream status
  * stream capabilites
- fix busy loop for serial that cause 100% CPU usage on host simulator
- support divider for dummy dev
- various small fixes and improvements
- use contex manager to handle objects cleanup
- support for UDP transport
- support for stream data as numpy data to improve performances
- make NumPy stream decode mode the default in `NxscopeHandler` and
  deprecate legacy per-sample stream decode mode
- add support for user defined protocol extentions
- improve parse/decoding logic
- add more channels to dummy dev
