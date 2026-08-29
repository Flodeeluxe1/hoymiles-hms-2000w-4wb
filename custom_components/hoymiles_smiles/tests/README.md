# Testing

The first target is installation and runtime testing in a real Home Assistant instance.

Before publishing a release:

- Validate the Python syntax.
- Install through HACS.
- Add the integration through the UI.
- Verify station/inverter discovery.
- Verify realtime power and PV1–PV4.
- Verify cloud energy, voltage, frequency and temperature.
- Test with the inverter producing.
- Test again when the inverter/DTU is offline and confirm realtime entities become unavailable and recover later.
