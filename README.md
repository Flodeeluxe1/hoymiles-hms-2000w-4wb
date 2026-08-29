# Hoymiles S-Miles Cloud — Home Assistant / HACS

Custom Home Assistant integration for monitoring Hoymiles S-Miles Cloud.

> **Read-only monitoring for the first release.** No inverter power-control/write commands are implemented.

## Features

- S-Miles Cloud authentication using the proven Argon2id challenge
- Dynamic station discovery
- Dynamic inverter discovery
- Near-realtime inverter power every 5 seconds
- PV1–PV4 power
- Station daily/monthly/yearly/total energy
- Station cloud real power
- Cloud inverter power
- AC voltage
- AC frequency
- Inverter temperature
- Graceful handling of an empty realtime URI when the inverter/DTU is offline
- Automatic refresh of the temporary realtime URI after failures

## Installation with HACS

1. Co install it through HACS, add the repository as a custom repository under HACS → Integrations
2. Upload the contents of this repository.
3. In Home Assistant, open **HACS → Integrations**.
4. Open the HACS menu and choose **Custom repositories**.
5. Enter the GitHub repository URL https://github.com/Flodeeluxe1/hoymiles-hms-2000w-4wb
6. Select **Integration** as the category.
7. Install **Hoymiles S-Miles Cloud**.
8. Restart Home Assistant.
9. Go to **Settings → Devices & services → Add integration**.
10. Search for **Hoymiles S-Miles Cloud**.
11. Enter your S-Miles email/password and data center.
12. Select the station.
13. Select the inverter.

## Important

Do not put your S-Miles password, token, station IDs, or inverter serial numbers into GitHub.

The integration discovers the station and inverter after login and stores the selected configuration in Home Assistant.

## Data update rates

- Realtime burst data: approximately every 5 seconds.
- Station cloud and Protobuf chart data: every 5 minutes.
- The realtime URI is short-lived and is refreshed after a failed request.
- An empty realtime URI is treated as an expected offline condition rather than a permanent configuration error.

## Energy units

The integration currently exposes the S-Miles `today_eq`, `month_eq`, `year_eq`, and `total_eq` values as kWh based on the current API testing. This should be verified against known production data before relying on the values for long-term energy accounting.

## Current scope

This release is deliberately read-only. Power-control functionality is not included until the write endpoint, payload, limits, authentication and safety behavior are positively confirmed.

## API reference

The implementation was developed from working S-Miles Cloud API testing and also uses the public ioBroker Hoymiles implementation as a reference:

https://github.com/Eistee82/ioBroker.hoymiles
