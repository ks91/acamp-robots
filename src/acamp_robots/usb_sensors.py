from __future__ import annotations

import array
import math
import subprocess
from pathlib import Path
from typing import Any, Callable

from .errors import RobotError


OMRON_USB_VID = 0x0590
OMRON_USB_PID = 0x00D4
OMRON_LATEST_LONG = bytes((0x52, 0x42, 0x05, 0x00, 0x01, 0x21, 0x50))


def crc16_modbus(data: bytes) -> bytes:
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            crc = (crc >> 1) ^ (0xA001 if crc & 1 else 0)
    return bytes((crc & 0xFF, crc >> 8))


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _s16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little", signed=True)


def parse_2jciebu_latest(data: bytes) -> dict[str, Any]:
    if len(data) < 57:
        raise RobotError(f"2JCIE-BU01 returned {len(data)} bytes; expected at least 57")
    if data[:2] != b"RB":
        raise RobotError("2JCIE-BU01 response has an invalid header")
    if crc16_modbus(data[:-2]) != data[-2:]:
        raise RobotError("2JCIE-BU01 response failed its CRC check")
    return {
        "sensor": "2JCIE-BU01",
        "temperature_c": _s16(data, 8) / 100,
        "relative_humidity_percent": _u16(data, 10) / 100,
        "ambient_light_lx": _u16(data, 12),
        "barometric_pressure_hpa": int.from_bytes(data[14:18], "little") / 1000,
        "sound_noise_db": _u16(data, 18) / 100,
        "etvoc_ppb": _u16(data, 20),
        "eco2_ppm": _u16(data, 22),
        "discomfort_index": _u16(data, 24) / 100,
        "heat_stroke_c": _s16(data, 26) / 100,
        "vibration_information": data[28],
        "si_value": _u16(data, 29) / 10,
        "pga_gal": _u16(data, 31) / 10,
        "seismic_intensity": _u16(data, 33) / 1000,
    }


def environment_read(
    port: str | None = None,
    *,
    serial_factory: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    try:
        if serial_factory is None:
            import serial
            from serial.tools import list_ports

            serial_factory = serial.Serial
            if port is None:
                matches = [
                    item.device
                    for item in list_ports.comports()
                    if item.vid == OMRON_USB_VID and item.pid == OMRON_USB_PID
                ]
                port = matches[0] if len(matches) == 1 else None
    except ImportError as exc:
        raise RobotError("pyserial is required for the 2JCIE-BU01 USB sensor") from exc
    if not port:
        raise RobotError(
            "2JCIE-BU01 USB serial port was not found; verify USB ID 0590:00d4 "
            "and the ftdi_sio driver"
        )
    command = OMRON_LATEST_LONG + crc16_modbus(OMRON_LATEST_LONG)

    def read_exact(connection, size: int) -> bytes:
        received = bytearray()
        while len(received) < size:
            chunk = connection.read(size - len(received))
            if not chunk:
                break
            received.extend(chunk)
        return bytes(received)

    try:
        with serial_factory(port, 115200, timeout=1.0) as connection:
            connection.reset_input_buffer()
            connection.write(command)
            header = read_exact(connection, 4)
            if len(header) != 4:
                raise RobotError("2JCIE-BU01 response timed out before its length field")
            remaining = int.from_bytes(header[2:4], "little")
            if not 2 <= remaining <= 512:
                raise RobotError(f"2JCIE-BU01 returned invalid frame length {remaining}")
            data = header + read_exact(connection, remaining)
    except (OSError, ValueError) as exc:
        raise RobotError(f"Could not read 2JCIE-BU01 on {port}: {exc}") from exc
    result = parse_2jciebu_latest(bytes(data))
    result["port"] = port
    return result


def _default_microphone_device(cards_path: Path = Path("/proc/asound/cards")) -> str:
    try:
        lines = cards_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return "default"
    for line in lines:
        if "USB-Audio" in line and line.lstrip()[:1].isdigit():
            return f"plughw:{int(line.split()[0])},0"
    return "default"


def microphone_level(
    duration_seconds: float = 1.0,
    device: str | None = None,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    duration_seconds = float(duration_seconds)
    if not 0.1 <= duration_seconds <= 5.0:
        raise ValueError("duration_seconds must be between 0.1 and 5.0")
    rate = 16000
    device = device or _default_microphone_device()
    command = [
        "arecord", "-q", "-D", device, "-t", "raw", "-f", "S16_LE",
        "-c", "1", "-r", str(rate), "-d", str(math.ceil(duration_seconds)),
    ]
    try:
        completed = runner(command, capture_output=True, timeout=duration_seconds + 2)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RobotError(f"Could not capture USB microphone level: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        raise RobotError(f"USB microphone capture failed: {detail or 'arecord error'}")
    samples = array.array("h")
    samples.frombytes(completed.stdout[: int(rate * duration_seconds) * 2])
    if not samples:
        raise RobotError("USB microphone returned no samples")
    square_mean = sum(value * value for value in samples) / len(samples)
    rms = math.sqrt(square_mean)
    peak = max(abs(value) for value in samples)

    def dbfs(value: float) -> float:
        return -120.0 if value <= 0 else 20 * math.log10(value / 32768)

    return {
        "sensor": "CGS-M3C",
        "device": device,
        "duration_seconds": duration_seconds,
        "sample_rate_hz": rate,
        "sample_count": len(samples),
        "rms_dbfs": round(dbfs(rms), 2),
        "peak_dbfs": round(dbfs(peak), 2),
    }
