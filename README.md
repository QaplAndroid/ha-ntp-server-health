# NTP Server Health 1.3.0

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

## Devices and upgrades

Each configured server is a separate Home Assistant device. Open
**Settings → Devices & services → NTP Server Health**, then select a server.
Its native device page contains Root dispersion, Root delay, Stratum, Health,
Problem, and Server time. Use **Add to dashboard** to add its entities to your own dashboard.
Device names and areas can be changed using Home Assistant's standard controls.

When upgrading from GUI versions 1.0.0, 1.1.0, or 1.2.0, update the integration files
and restart Home Assistant. Do not delete and re-add the integration or import
the configuration again: saved settings, existing entity IDs, and custom entity
names are retained. Devices are created automatically for existing servers.
Server names must remain unchanged to retain their existing identities.

The all-server Problem aggregate remains integration-wide and is not assigned
to an individual server device. Removing a server in the integration's options
removes its device and entities without affecting the remaining servers.

## Sensors

Each server has six entities:

| Entity | Value |
| --- | --- |
| Root dispersion | milliseconds; measurement statistics |
| Root delay | milliseconds; measurement statistics |
| Stratum | numeric stratum |
| Health | `OK`, `WARNING`, or `CRITICAL` |
| Problem | on for warnings, critical results, and communication failures |
| Server time | timezone-aware timestamp from the server's NTP response |

Example entity ID: `sensor.ntp_pool_ntp_org_root_dispersion`. Actual entity IDs
may differ if a name is already taken or has been customized.
Health attributes include the reason, remote address, leap indicator, NTP
version, and hexadecimal reference ID.

On a timeout, DNS failure, or invalid response, numeric and server-time sensors become
`unavailable` rather than reporting zero or keeping stale measurements. Health
reports `CRITICAL`, and Problem is on. Valid responses restore measurements.
A leap alarm or excessive stratum retains the available measurements with an alarm.

Root dispersion is the server's reported uncertainty relative to its reference
source. It is not the measured clock offset between Home Assistant and the server.
This integration does not change clocks or configure NTP synchronization.

### Server time

**Server time** is the transmit timestamp supplied by the NTP server, including
fractional seconds, not a copy of Home Assistant's clock. It uses the same NTP
request as the other measurements and refreshes at the configured polling interval.
It is a snapshot of the last valid response, not a clock ticking every second.

Home Assistant receives a UTC timestamp and formats it using its time-zone and
display settings. A timestamp may be shown relatively; open the entity to inspect
the exact time. Home Assistant stores timestamp sensor states at whole-second
precision, for example `2026-10-26T12:34:56+00:00`. A failed poll makes it `unavailable` instead of
retaining an old time. A valid response with a health warning still reports the
server's time; check Health and Problem to decide whether the source is healthy.
The NTP timestamp's 2036 era rollover is handled using the request's clock as the
era reference.


## Aggregate problem group

Version 1.1.0 adds one integration-wide binary sensor:
`binary_sensor.ntp_server_health_problem` (name: **NTP Server Health Problem**).
It is created automatically; no YAML configuration or manual group membership is needed.
Existing per-server sensors and their unique IDs remain unchanged.

- **off**: every configured server reports OK.
- **on**: any server reports WARNING, CRITICAL, or an unavailable monitoring update.
- A failed update never reuses a stale healthy result to mark the group healthy.
- The aggregate stays available to report failed members. Its state is based on
  shared coordinator results, not on the formatting of entity names.
- GUI changes and JSON imports rebuild membership automatically on reload.
- The group does not send extra NTP queries.

This is an aggregate problem sensor, not a separately editable HA Group helper.
Its attributes expose group-style membership and current problem details:

| Attribute | Meaning |
| --- | --- |
| `entity_id` | Actual registry IDs of all per-server Problem sensors |
| `server_count` | Number of configured servers |
| `problem_count` | Number of servers with a problem, not the number of measurement entities |
| `problems` | Server, status, reason, dispersion in ms, stratum, and actual Health entity ID |

Member entity renames are resolved through the entity registry. Communication
failures retain their original reason (such as timed out); an unavailable
coordinator update uses status UNAVAILABLE and clears stale measurements in the summary.
Five configured servers now have 25 per-server entities plus this one aggregate.

After upgrading the integration files, restart HA once to load the new code.
Do not remove and re-add the integration or re-import saved settings just for this update.

## Dashboard examples

Copy the contents of `dashboard/status.yaml` into a dashboard **Manual** card.
It shows a green all-OK heading, or a red table listing only affected servers
with status, reason, dispersion, stratum, and the Health state's last-change time.
An absent/unavailable aggregate is shown as an error, never as all OK.
The background colors require **card-mod**; the Markdown content itself uses a native card.

`dashboard/history.yaml` uses **auto-entities** and a native Logbook card.
Its group filter follows the aggregate's `entity_id` list automatically.
It displays changes of the aggregate and individual Problem on/off states over 48 hours.
History must be enabled and must not exclude these entities. A WARNING-to-CRITICAL
transition can leave Problem on; current severity and reasons remain visible in
the status card, but that transition is not promised as a separate Problem logbook event.

If you rename the aggregate itself, update its ID in both dashboard examples.
No hostnames or private server lists are embedded in the dashboard configuration.


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

## Publishing a new GitHub release

1. Open the existing integration repository on GitHub and select its **Code** tab.
2. In the repository root, select **Add file → Upload files**.
3. Open the local `v1.3.0` folder and drag its **contents**, not the enclosing
   `v1.3.0` folder, into the upload area. Upload only this public release folder,
   never the parent project, private configuration, or Home Assistant's `.storage`.
4. Check that the root contains `custom_components/ntp_server_health`,
   `dashboard`, `tests`, `README.md`, `hacs.json`, and `.gitignore`.
5. Enter commit message `Release 1.3.0` and commit the upload to `main`.
6. Open **Releases → Draft a new release** (or **Create a new release**).
7. Choose a new tag **v1.3.0**, target **main**, and title **NTP Server Health 1.3.0**.
8. Describe the new Server time entity, leave **pre-release** disabled, and publish.
   No manually created ZIP or release attachment is needed.
9. In Home Assistant, refresh the repository information in HACS, install/update
   **NTP Server Health** to **1.3.0**, and restart Home Assistant.
10. Open a server device and check its new **Server time** entity. Existing settings
    and entity IDs are retained; do not remove the integration or re-import settings.

## Development

From the repository root:

```sh
python -B -m unittest discover -s tests -v
```

Protocol tests use real loopback UDP sockets. Configuration tests cover JSON
roundtrips, validation, thresholds, server normalization, and malformed input.
Aggregate tests cover warning/critical conditions, unavailable results, recovery,
and removing failed servers.

The GUI/config-entry backend was previously exercised on HA Core 2026.10.4,
including reload, entity removal, and initial and options JSON imports. Full
visual GUI verification was limited by missing voice dependencies in the
Windows development runtime. HACS installation from the public repository must
be verified after the repository has been created and uploaded.

Version 1.1.0 was additionally exercised with native HA Core 2026.10.4 entity
platforms, coordinators, registry, state machine, and template renderer.
Loopback NTP responses drove OK, WARNING, and CRITICAL transitions; failed updates,
recovery, member entity renames, and listener cleanup on unload were checked.
The status card template rendered a valid Markdown table against those real HA states.
Full browser rendering of the dashboard cards on a user's HA instance is not verified.

Version 1.2.0 was exercised on native HA Core 2026.10.4 across separate legacy
and upgraded processes with persistent registries. The upgrade preserved entity
IDs and custom names, linked exactly five entities to each server device, kept
the aggregate device-independent, and removed only the deleted server's device
and entities on options reload. A real frontend browser run confirmed the
integration's device list and the server's native page with all five entities.

Version 1.3.0 passed 29 tests, including loopback replies whose server time
differs from the client clock, fractional seconds, invalid responses, timeouts,
and both sides of the 2036 era boundary. A live `pool.ntp.org` query returned
a UTC transmit time. Native HA Core 2026.10.4 upgrade verification preserved
the six pre-existing entity IDs and custom Health name, added the sixth
per-server entity, and checked its unavailable/recovery behavior and persistence
through reload. Browser verification confirmed Server time on the device page
and the absolute local date/time in its entity details.

## Changelog

### 1.3.0

- Add a Server time timestamp entity to every server device.
- Decode the server's transmit time with UTC timezone and fractional seconds.
- Handle the 2036 NTP era rollover without interpreting the time as 1900.
- Share the existing polling request and mark failed time readings unavailable.
- Retain all existing entities, devices, configuration, and aggregate behavior.

### 1.2.0

- Represent each NTP server as a separate device with its five existing entities.
- Show short entity labels on the native device page; retain existing unique IDs.
- Preserve saved configuration, entity IDs, custom entity names, and device names.
- Remove obsolete server devices when configuration changes.
- Keep the all-server Problem aggregate independent of individual server devices.

### 1.1.0

- Added an automatic all-server Problem aggregate with live member IDs and problem reasons.
- Count WARNING, CRITICAL, and unavailable updates as problems; clear details after recovery.
- Added dynamic status and 48-hour Logbook dashboard examples without private configuration.
- Retained existing config entries, entity IDs, per-server polling, and JSON import format.


### 1.0.0

- Initial public release with GUI setup and configuration editing.
- Versioned JSON copy/paste import/export.
- Root dispersion, root delay, stratum, health, and problem sensors.
- English and Croatian GUI translations.
- HACS metadata, repository links, and an original metadata-free brand icon.
- Public NTP default and reserved documentation addresses in tests; no personal server list.
- Configuration changes reload the integration without restarting Home Assistant.
