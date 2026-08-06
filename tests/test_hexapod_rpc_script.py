import os
import json
import socket
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]


def make_fake_server(path, marker):
    path.mkdir()
    (path / "main.py").write_text("# required vendor entrypoint\n")
    (path / "point.txt").write_text("calibration\n")
    (path / "control.py").write_text(
        "import os, threading\n"
        "assert open('point.txt').read().strip() == 'calibration'\n"
        "class Part:\n"
        "    def on(self): pass\n"
        "    def off(self): pass\n"
        "    def set_servo_angle(self, channel, angle): pass\n"
        "class Control:\n"
        "    def __init__(self):\n"
        f"        open({str(marker)!r}, 'w').write('initialized')\n"
        "        self.condition_thread = threading.Thread(target=lambda: None)\n"
        "        self.servo_power_disable = Part()\n"
        "        self.servo = Part()\n"
        "        self.command_queue = []\n"
        "        self.timeout = 0\n"
    )


def rpc_call(path, method, *args):
    request = {"id": "test", "method": method, "args": list(args), "kwargs": {}}
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.connect(path)
        client.sendall(json.dumps(request).encode() + b"\n")
        return json.loads(client.recv(4096).split(b"\n", 1)[0])


def test_rpc_script_waits_for_a_real_health_response(tmp_path):
    server_dir = tmp_path / "Server"
    marker = tmp_path / "hardware-initialized"
    make_fake_server(server_dir, marker)
    stem = f"acamp-rpc-{os.getpid()}"
    env = os.environ | {
        "HEXAPOD_SERVER_DIR": str(server_dir),
        "HEXAPOD_RPC_SOCKET": f"/tmp/{stem}.sock",
        "HEXAPOD_RPC_PID_FILE": f"/tmp/{stem}.pid",
        "HEXAPOD_RPC_LOG": f"/tmp/{stem}.log",
    }
    script = ROOT / "scripts" / "hexapod-rpc.sh"
    try:
        started = subprocess.run([script, "start"], env=env, text=True, capture_output=True)
        assert started.returncode == 0, started.stderr
        assert "has started" in started.stdout
        assert not marker.exists(), "starting the bridge must not initialize hardware"
        status = subprocess.run([script, "status"], env=env, text=True, capture_output=True)
        assert status.returncode == 0
        assert "is running" in status.stdout
        before_power = rpc_call(env["HEXAPOD_RPC_SOCKET"], "status")
        assert before_power["result"]["initialized"] is False
        rejected = rpc_call(env["HEXAPOD_RPC_SOCKET"], "move", 1, 5, 0, 0)
        assert rejected["ok"] is False
        assert not marker.exists()
        enabled = rpc_call(env["HEXAPOD_RPC_SOCKET"], "servopower", True)
        assert enabled["ok"] is True
        assert marker.read_text() == "initialized"
    finally:
        subprocess.run([script, "stop"], env=env, check=False)
