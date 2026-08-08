# USB Research Sensors

This document records Raspberry Pi host setup for USB sensors supported by
`acamp_robots`. Keep device-specific driver and diagnostic instructions here as
new research sensors are added. Robot motion is not required for any procedure
on this page.

## Supported devices

| Device | Purpose | Linux interface | Public primitive |
| --- | --- | --- | --- |
| OMRON 2JCIE-BU01(F1) | Environmental measurements | USB serial, `0590:00d4` | `environment_read` |
| CGS-M3C | Sound-level experiments | USB Audio / ALSA | `microphone_level` |

Run initial acceptance tests on an externally powered DOFBOT Raspberry Pi.
Before moving a sensor to a battery-powered Hexapod, stop both robots and have
staff move the USB device. On the Hexapod, compare `vcgencmd get_throttled`
before and after one short reading. Stop testing after a disconnect, reset,
undervoltage indication, unstable reading, or unusual hardware behavior.

## OMRON 2JCIE-BU01(F1)

The Python dependency `pyserial` is installed by:

```bash
./scripts/setup.sh --robot arm
# or
./scripts/setup.sh --robot hexapod
```

### Detect the USB device

```bash
lsusb
ls -l /dev/ttyUSB* 2>/dev/null
```

The expected USB ID is `0590:00d4`. If that ID appears in `lsusb` but no
`/dev/ttyUSB*` device exists, load the FTDI USB-serial driver and register the
OMRON ID:

```bash
sudo modprobe ftdi_sio
echo '0590 00d4' | sudo tee /sys/bus/usb-serial/drivers/ftdi_sio/new_id
```

Do not use `sudo echo ... > new_id`: shell redirection would still run without
the required privilege. Do not make the sysfs control file world-writable.

Registration through `new_id` is runtime state and may need to be repeated
after reboot. If registration reports that the ID already exists, unplug and
reconnect the sensor, then check `/dev/ttyUSB*` again. Staff should perform the
driver registration before participant work begins.

### Read the sensor

Automatic USB-ID detection:

```bash
.venv/bin/acamp-robot call environment_read
```

Explicit serial device when needed:

```bash
.venv/bin/acamp-robot call environment_read /dev/ttyUSB0
```

If `lsusb` does not show `0590:00d4`, check the local USB connection, port, and
power with staff. Do not scan the network or another robot for the device.

## CGS-M3C USB microphone

`microphone_level` requires ALSA's `arecord`, normally supplied by the
`alsa-utils` operating-system package. Check the command and list local capture
devices:

```bash
command -v arecord
arecord -l
```

The primitive selects the first USB Audio card when possible. It analyzes PCM
in memory and returns RMS and peak dBFS; it does not create an audio file.

```bash
.venv/bin/acamp-robot call microphone_level 1.0
```

An explicit ALSA device can be supplied after the bounded duration:

```bash
.venv/bin/acamp-robot call microphone_level 1.0 plughw:2,0
```

Durations are limited to 0.1–5.0 seconds. Do not record or retain participant
voices or other identifiable audio.

## Adding another USB sensor

For each new device, add all of the following:

1. Its model, purpose, USB vendor/product IDs, Linux interface, and power notes
   to the table above.
2. A bounded public primitive that returns structured data and does not require
   robot motion.
3. Offline protocol, parsing, timeout, and failure tests using a test double.
4. Setup dependencies and a non-destructive device-detection procedure.
5. A DOFBOT acceptance trial followed by a separate Hexapod power trial.
6. Privacy rules for any captured image, audio, identifier, or experiment data.

Do not copy vendor libraries into this repository unless their license clearly
permits redistribution. Prefer a small adapter around a documented interface.
