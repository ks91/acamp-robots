import array
from types import SimpleNamespace

import pytest

from acamp_robots.errors import RobotError
from acamp_robots.usb_sensors import (
    OMRON_LATEST_LONG,
    crc16_modbus,
    environment_read,
    microphone_level,
    parse_2jciebu_latest,
)


def make_environment_response():
    data = bytearray(58)
    data[:2] = b"RB"
    data[2:4] = (54).to_bytes(2, "little")
    values = {
        (8, 2): (2345).to_bytes(2, "little", signed=True),
        (10, 2): (4567).to_bytes(2, "little"),
        (12, 2): (321).to_bytes(2, "little"),
        (14, 4): (101325).to_bytes(4, "little"),
        (18, 2): (3875).to_bytes(2, "little"),
        (20, 2): (120).to_bytes(2, "little"),
        (22, 2): (650).to_bytes(2, "little"),
        (24, 2): (7210).to_bytes(2, "little"),
        (26, 2): (2550).to_bytes(2, "little", signed=True),
        (29, 2): (12).to_bytes(2, "little"),
        (31, 2): (34).to_bytes(2, "little"),
        (33, 2): (567).to_bytes(2, "little"),
    }
    for (offset, size), value in values.items():
        data[offset : offset + size] = value
    data[28] = 1
    data[-2:] = crc16_modbus(data[:-2])
    return bytes(data)


def test_environment_packet_is_crc_checked_and_decoded():
    result = parse_2jciebu_latest(make_environment_response())
    assert result["temperature_c"] == 23.45
    assert result["relative_humidity_percent"] == 45.67
    assert result["barometric_pressure_hpa"] == 101.325
    assert result["sound_noise_db"] == 38.75
    assert result["eco2_ppm"] == 650
    broken = bytearray(make_environment_response())
    broken[8] ^= 1
    with pytest.raises(RobotError, match="CRC"):
        parse_2jciebu_latest(bytes(broken))


def test_environment_read_sends_the_official_latest_long_command():
    observed = {}

    class FakeSerial:
        def __init__(self, port, baudrate, timeout):
            observed.update(port=port, baudrate=baudrate, timeout=timeout)
            self.response = make_environment_response()
            self.offset = 0
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def reset_input_buffer(self): observed["reset"] = True
        def write(self, data): observed["command"] = data
        def read(self, size):
            observed.setdefault("sizes", []).append(size)
            chunk = self.response[self.offset : self.offset + size]
            self.offset += len(chunk)
            return chunk

    result = environment_read("/dev/ttyUSB7", serial_factory=FakeSerial)
    assert result["port"] == "/dev/ttyUSB7"
    assert observed["baudrate"] == 115200
    assert observed["command"] == OMRON_LATEST_LONG + crc16_modbus(OMRON_LATEST_LONG)
    assert observed["sizes"] == [4, 54]


def test_microphone_returns_levels_without_writing_audio():
    samples = array.array("h", [0, 1000, -1000, 2000, -2000] * 3200)
    observed = {}

    def run(command, **kwargs):
        observed["command"] = command
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=samples.tobytes(), stderr=b"")

    result = microphone_level(0.5, "plughw:2,0", runner=run)
    assert result["sensor"] == "CGS-M3C"
    assert result["sample_count"] == 8000
    assert result["peak_dbfs"] == pytest.approx(-24.29, abs=0.01)
    assert "-D" in observed["command"]
    assert observed["capture_output"] is True


def test_microphone_duration_is_bounded():
    with pytest.raises(ValueError):
        microphone_level(5.1)
