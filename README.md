# NTP Server Health 1.0.0

Home Assistant custom integration for monitoring NTP server health over UDP.
Configuration, editing, and JSON import/export use the Home Assistant GUI.
No PowerShell, MQTT, external polling service, or YAML settings are required.

Requires **Home Assistant Core 2026.10.0 or newer**.

## Install with HACS

Public repository: `https://github.com/QaplAndroid/ha-ntp-server-health`.

1. In HACS open **Custom repositories**.
2. Add the repository URL above with type **Integration**.
3. Find **NTP Server Health** in HACS and download it.
4. Restart Home Assistant.
5. Open **Settings → Devices & services → Add integration → NTP Server Health**.
6. Enter the servers you want to monitor and save.

One integration instance can monitor multiple servers. The initial form suggests
only the public hostname `pool.ntp.org`. Replace or extend it with your own
servers in the GUI. Existing saved settings are not replaced during an upgrade.

For manual installation, copy only `custom_components/ntp_server_health` into
the Home Assistant configuration directory's `custom_components` directory,
then restart Home Assistant and add the integration as above. Do not create an
extra nested `custom_components` directory.

If upgrading from an earlier YAML-based installation, remove its `ntp_server_health:`
section from `configuration.yaml` before restarting and configure it in the GUI.
Entity unique IDs for unchanged server names are preserved.

The Home Assistant host needs network access to UDP port 123 on each server,
and working DNS for hostnames. Hostname lookups use the operating system's
resolver timeout, independently of the socket timeout.

## Sensors

Each server has five entities:

| Entity | Value |
| --- | --- |
| Root dispersion | milliseconds; measurement statistics |
| Root delay | milliseconds; measurement statistics |
| Stratum | numeric stratum |
| Health | `OK`, `WARNING`, or `CRITICAL` |
| Problem | on for warnings, critical results, and communication failures |

Example entity ID: `sensor.ntp_pool_ntp_org_root_dispersion`. Actual entity IDs
may differ if a name is already taken or has been customized.
Health attributes include the reason, remote address, leap indicator, NTP
version, and hexadecimal reference ID.

On a timeout, DNS failure, or invalid response, numeric sensors become
`unavailable` rather than reporting zero or keeping stale measurements. Health
reports `CRITICAL`, and Problem is on. Valid responses restore measurements.
A leap alarm or excessive stratum retains the available measurements with an alarm.

Root dispersion is the server's reported uncertainty relative to its reference
source. It is not the measured clock offset between Home Assistant and the server.
This integration does not change clocks or configure NTP synchronization.

## Settings

Open **Configure** on the integration. Enter one hostname or IP address per line.
Saving settings automatically reloads monitoring; a full HA restart is not needed.
Removing a server also removes its entities from the entity registry.

| Setting | Default | Rule |
| --- | --- | --- |
| Polling interval | 60 seconds | at least 10 seconds |
| Socket timeout | 3 seconds | 0.1 to 30 seconds |
| Warning dispersion | 0.100 seconds | warning at or above threshold |
| Critical dispersion | 1.000 seconds | critical at or above threshold |
| Warning stratum | 10 | warning above threshold |
| Critical stratum | 15 | critical above threshold |

Dispersion thresholds use **seconds**, while measurement sensors use
**milliseconds**. Warning thresholds must be strictly lower than critical
thresholds. Stratum thresholds range from 1 to 15. Server entries must be unique.
All five entities for a server share one query per polling cycle.

Critical conditions take precedence over warnings. Leap indicator 3, stratum 0
(Kiss-o-Death), unsupported NTP version, invalid server mode, short responses,
missing transmit timestamps, and mismatched originate timestamps are critical.
The client sends NTP v4 requests and accepts NTP v3 and v4 server responses.
Root delay is decoded as a signed NTP 16.16 value.

## JSON import and export

- **Configure → Export JSON configuration** displays the current complete JSON
  configuration. Copy it and store it privately. Export does not change settings.
- **Configure → Import JSON configuration** accepts a pasted export. A valid
  import replaces all servers and thresholds and reloads monitoring. Invalid
  input leaves the active settings unchanged.
- JSON import is also available when first adding the integration.

This is copy/paste import/export, not automatic file download or upload.
The document has `format: ntp_server_health`, `version: 1`, and a complete
`settings` object. It does not include entity IDs, dashboards, or sensor history.

## Privacy and publishing

Server lists and exported JSON can reveal private network details. Keep real
configuration exports, HA configuration files, logs, screenshots, databases,
backups, credentials, and keys out of public repositories and issue reports.
The integration does not upload settings or NTP results to GitHub.

The source contains only a public NTP default, loopback addresses for local UDP
tests, and reserved documentation addresses in configuration tests. No personal
server list is bundled. `.gitignore` helps normal Git workflows, but does not
prevent a manual web upload of a sensitive file. Review uploads explicitly.

Deleting a sensitive file from the latest commit does not remove it from Git
history. Publish sanitized files into a new repository without private history.

## Development

From the repository root:

```sh
python -B -m unittest discover -s tests -v
```

Protocol tests use real loopback UDP sockets. Configuration tests cover JSON
roundtrips, validation, thresholds, server normalization, and malformed input.

The GUI/config-entry backend was previously exercised on HA Core 2026.10.4,
including reload, entity removal, and initial and options JSON imports. Full
visual GUI verification was limited by missing voice dependencies in the
Windows development runtime. HACS installation from the public repository must
be verified after the repository has been created and uploaded.

## Changelog

### 1.0.0

- Initial public release with GUI setup and configuration editing.
- Versioned JSON copy/paste import/export.
- Root dispersion, root delay, stratum, health, and problem sensors.
- English and Croatian GUI translations.
- HACS metadata, repository links, and an original metadata-free brand icon.
- Public NTP default and reserved documentation addresses in tests; no personal server list.
- Configuration changes reload the integration without restarting Home Assistant.
